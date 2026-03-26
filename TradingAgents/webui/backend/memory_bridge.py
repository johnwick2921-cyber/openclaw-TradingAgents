"""Bridge between SQLite persistence and in-memory FinancialSituationMemory.

Manages five FinancialSituationMemory instances (one per agent) and
synchronizes them with the ``memories`` table in SQLite.  Provides
CRUD operations and simple text search.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.agents.utils.memory import FinancialSituationMemory
from tradingagents.default_config import DEFAULT_CONFIG
from webui.backend.database import get_db

logger = logging.getLogger(__name__)

# The five agent memory namespaces, matching TradingAgentsGraph.__init__
AGENT_MEMORY_NAMES: List[str] = [
    "bull",
    "bear",
    "trader",
    "invest_judge",
    "portfolio_manager",
]

# Map from short agent name to the FinancialSituationMemory "name" field
# used in TradingAgentsGraph (e.g., "bull_memory")
_MEMORY_INSTANCE_NAMES: Dict[str, str] = {
    name: f"{name}_memory" for name in AGENT_MEMORY_NAMES
}


class MemoryBridge:
    """Bridges SQLite persistence with in-memory FinancialSituationMemory.

    Holds five independent memory instances, one per agent role.  On startup,
    ``load_from_db()`` populates them from SQLite.  After each run,
    ``save_new_memories()`` diffs before/after snapshots and inserts new
    entries.
    """

    def __init__(self) -> None:
        self._memories: Dict[str, FinancialSituationMemory] = {}
        for agent_name in AGENT_MEMORY_NAMES:
            instance_name = _MEMORY_INSTANCE_NAMES[agent_name]
            self._memories[agent_name] = FinancialSituationMemory(
                instance_name, DEFAULT_CONFIG
            )

    # -- Public accessors -----------------------------------------------------

    def get_memory(self, agent_name: str) -> FinancialSituationMemory:
        """Return the FinancialSituationMemory instance for an agent.

        Args:
            agent_name: One of the AGENT_MEMORY_NAMES (e.g. ``"bull"``).

        Raises:
            KeyError: If *agent_name* is not a valid agent.
        """
        if agent_name not in self._memories:
            raise KeyError(
                f"Unknown agent '{agent_name}'. "
                f"Valid agents: {', '.join(AGENT_MEMORY_NAMES)}"
            )
        return self._memories[agent_name]

    # -- Bulk load / save -----------------------------------------------------

    async def load_from_db(self) -> None:
        """Read all memories from SQLite, group by agent, and populate
        the in-memory FinancialSituationMemory instances.

        This should be called once at application startup.
        """
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT agent_name, situation, recommendation FROM memories "
                "ORDER BY created_at ASC"
            )
            rows = await cursor.fetchall()

        # Group rows by agent
        grouped: Dict[str, List[Tuple[str, str]]] = {
            name: [] for name in AGENT_MEMORY_NAMES
        }
        for row in rows:
            agent = row["agent_name"]
            if agent in grouped:
                situation = row["situation"] or ""
                recommendation = row["recommendation"] or ""
                if situation or recommendation:
                    grouped[agent].append((situation, recommendation))

        # Populate each memory instance
        for agent_name, pairs in grouped.items():
            mem = self._memories[agent_name]
            mem.clear()
            if pairs:
                mem.add_situations(pairs)

        total = sum(len(v) for v in grouped.values())
        logger.info("Loaded %d memories from database across %d agents", total, len(AGENT_MEMORY_NAMES))

    async def save_new_memories(
        self,
        run_id: str,
        memories_before: Dict[str, int],
        memories_after: Dict[str, int],
    ) -> int:
        """Diff before/after document counts and insert new memories to SQLite.

        Args:
            run_id: The run that produced these memories.
            memories_before: ``{agent_name: doc_count}`` snapshot taken before
                the run.
            memories_after: ``{agent_name: doc_count}`` snapshot taken after
                the run.

        Returns:
            The number of new memories inserted.
        """
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0

        async with get_db() as db:
            for agent_name in AGENT_MEMORY_NAMES:
                before_count = memories_before.get(agent_name, 0)
                after_count = memories_after.get(agent_name, 0)

                if after_count <= before_count:
                    continue

                mem = self._memories[agent_name]
                # New documents are appended at the end
                for idx in range(before_count, after_count):
                    situation = mem.documents[idx] if idx < len(mem.documents) else ""
                    recommendation = mem.recommendations[idx] if idx < len(mem.recommendations) else ""
                    await db.execute(
                        """
                        INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (agent_name, situation, recommendation, run_id, now),
                    )
                    inserted += 1

            await db.commit()

        logger.info("Saved %d new memories for run %s", inserted, run_id)
        return inserted

    def snapshot_counts(self) -> Dict[str, int]:
        """Return a snapshot of document counts per agent.

        Used before a run to establish a baseline for ``save_new_memories()``.
        """
        return {
            name: len(mem.documents)
            for name, mem in self._memories.items()
        }

    # -- CRUD operations ------------------------------------------------------

    async def delete_memory(self, agent_name: str, memory_id: int) -> bool:
        """Remove a single memory from SQLite and rebuild the agent's
        in-memory index.

        Args:
            agent_name: The agent whose memory to delete from.
            memory_id: The SQLite row ``id``.

        Returns:
            True if a row was deleted, False if not found.
        """
        if agent_name not in self._memories:
            raise KeyError(f"Unknown agent '{agent_name}'")

        async with get_db() as db:
            cursor = await db.execute(
                "DELETE FROM memories WHERE id = ? AND agent_name = ?",
                (memory_id, agent_name),
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            await self._rebuild_agent_memory(agent_name)
            logger.info("Deleted memory %d for agent %s", memory_id, agent_name)

        return deleted

    async def clear_agent_memories(self, agent_name: str) -> int:
        """Clear all SQLite rows for an agent and create a fresh empty memory.

        Args:
            agent_name: The agent to clear.

        Returns:
            Number of rows deleted.
        """
        if agent_name not in self._memories:
            raise KeyError(f"Unknown agent '{agent_name}'")

        async with get_db() as db:
            cursor = await db.execute(
                "DELETE FROM memories WHERE agent_name = ?", (agent_name,)
            )
            await db.commit()
            count = cursor.rowcount

        # Reset in-memory instance
        self._memories[agent_name].clear()
        logger.info("Cleared %d memories for agent %s", count, agent_name)
        return count

    async def get_all_memories_from_db(
        self, agent_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query SQLite and return memories as a list of dicts.

        Args:
            agent_name: If provided, filter to this agent only.

        Returns:
            List of dicts with keys: id, agent_name, situation,
            recommendation, run_id, created_at.
        """
        async with get_db() as db:
            if agent_name:
                if agent_name not in AGENT_MEMORY_NAMES:
                    raise KeyError(f"Unknown agent '{agent_name}'")
                cursor = await db.execute(
                    "SELECT id, agent_name, situation, recommendation, run_id, created_at "
                    "FROM memories WHERE agent_name = ? ORDER BY created_at DESC",
                    (agent_name,),
                )
            else:
                cursor = await db.execute(
                    "SELECT id, agent_name, situation, recommendation, run_id, created_at "
                    "FROM memories ORDER BY created_at DESC"
                )
            rows = await cursor.fetchall()

        return [
            {
                "id": row["id"],
                "agent_name": row["agent_name"],
                "situation": row["situation"],
                "recommendation": row["recommendation"],
                "run_id": row["run_id"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def search_memories(
        self, agent_name: str, query: str
    ) -> List[Dict[str, Any]]:
        """Simple text search across situation and recommendation fields.

        Performs a case-insensitive SQL LIKE search.  For BM25-based
        semantic search, use ``get_memory(agent_name).get_memories(query)``.

        Args:
            agent_name: Agent to search within.
            query: Search text (matched with SQL LIKE ``%query%``).

        Returns:
            List of matching memory dicts.
        """
        if agent_name not in AGENT_MEMORY_NAMES:
            raise KeyError(f"Unknown agent '{agent_name}'")

        # Escape SQL LIKE wildcards
        escaped = query.replace("%", "\\%").replace("_", "\\_")
        search_pattern = f"%{escaped}%"
        async with get_db() as db:
            cursor = await db.execute(
                """
                SELECT id, agent_name, situation, recommendation, run_id, created_at
                FROM memories
                WHERE agent_name = ?
                  AND (situation LIKE ? ESCAPE '\\' OR recommendation LIKE ? ESCAPE '\\')
                ORDER BY created_at DESC
                """,
                (agent_name, search_pattern, search_pattern),
            )
            rows = await cursor.fetchall()

        return [
            {
                "id": row["id"],
                "agent_name": row["agent_name"],
                "situation": row["situation"],
                "recommendation": row["recommendation"],
                "run_id": row["run_id"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # -- Internal helpers -----------------------------------------------------

    async def _rebuild_agent_memory(self, agent_name: str) -> None:
        """Reload a single agent's in-memory index from SQLite."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT situation, recommendation FROM memories "
                "WHERE agent_name = ? ORDER BY created_at ASC",
                (agent_name,),
            )
            rows = await cursor.fetchall()

        mem = self._memories[agent_name]
        mem.clear()

        pairs = [
            (row["situation"] or "", row["recommendation"] or "")
            for row in rows
            if (row["situation"] or row["recommendation"])
        ]
        if pairs:
            mem.add_situations(pairs)

        logger.debug(
            "Rebuilt memory for agent %s with %d entries", agent_name, len(pairs)
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

memory_bridge = MemoryBridge()
