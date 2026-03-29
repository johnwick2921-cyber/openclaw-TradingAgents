"""Bridge between SQLite persistence and in-memory FinancialSituationMemory.

Manages the five agent memory namespaces used by the OpenClaw trading engine
and synchronizes them with the unified ``memories`` table in SQLite.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from openclaw.memory import FinancialSituationMemory
from dashboard.web.backend.database import get_db

logger = logging.getLogger(__name__)

AGENT_MEMORY_NAMES: List[str] = [
    "bull",
    "bear",
    "trader",
    "invest_judge",
    "portfolio_manager",
]

_MEMORY_INSTANCE_NAMES: Dict[str, str] = {
    name: f"{name}_memory" for name in AGENT_MEMORY_NAMES
}


class MemoryBridge:
    """Bridges SQLite persistence with in-memory FinancialSituationMemory."""

    def __init__(self) -> None:
        self._memories: Dict[str, FinancialSituationMemory] = {
            agent_name: FinancialSituationMemory(_MEMORY_INSTANCE_NAMES[agent_name])
            for agent_name in AGENT_MEMORY_NAMES
        }

    def get_memory(self, agent_name: str) -> FinancialSituationMemory:
        if agent_name not in self._memories:
            raise KeyError(
                f"Unknown agent '{agent_name}'. Valid agents: {', '.join(AGENT_MEMORY_NAMES)}"
            )
        return self._memories[agent_name]

    async def load_from_db(self) -> None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT agent_name, situation, recommendation FROM memories ORDER BY created_at ASC"
            )
            rows = await cursor.fetchall()

        grouped: Dict[str, List[Tuple[str, str]]] = {name: [] for name in AGENT_MEMORY_NAMES}
        for row in rows:
            agent = row["agent_name"]
            if agent in grouped:
                situation = row["situation"] or ""
                recommendation = row["recommendation"] or ""
                if situation or recommendation:
                    grouped[agent].append((situation, recommendation))

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
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0

        async with get_db() as db:
            for agent_name in AGENT_MEMORY_NAMES:
                before_count = memories_before.get(agent_name, 0)
                after_count = memories_after.get(agent_name, 0)
                if after_count <= before_count:
                    continue

                mem = self._memories[agent_name]
                for idx in range(before_count, after_count):
                    situation = mem.documents[idx] if idx < len(mem.documents) else ""
                    recommendation = mem.recommendations[idx] if idx < len(mem.recommendations) else ""
                    await db.execute(
                        "INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at) VALUES (?, ?, ?, ?, ?)",
                        (agent_name, situation, recommendation, run_id, now),
                    )
                    inserted += 1
            await db.commit()

        logger.info("Saved %d new memories for run %s", inserted, run_id)
        return inserted

    def snapshot_counts(self) -> Dict[str, int]:
        return {name: len(mem.documents) for name, mem in self._memories.items()}

    async def delete_memory(self, agent_name: str, memory_id: int) -> bool:
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
        if agent_name not in self._memories:
            raise KeyError(f"Unknown agent '{agent_name}'")

        async with get_db() as db:
            cursor = await db.execute(
                "DELETE FROM memories WHERE agent_name = ?",
                (agent_name,),
            )
            await db.commit()
            count = cursor.rowcount

        self._memories[agent_name].clear()
        logger.info("Cleared %d memories for agent %s", count, agent_name)
        return count

    async def get_all_memories_from_db(self, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
        async with get_db() as db:
            if agent_name:
                if agent_name not in AGENT_MEMORY_NAMES:
                    raise KeyError(f"Unknown agent '{agent_name}'")
                cursor = await db.execute(
                    "SELECT id, agent_name, situation, recommendation, run_id, created_at FROM memories WHERE agent_name = ? ORDER BY created_at DESC",
                    (agent_name,),
                )
            else:
                cursor = await db.execute(
                    "SELECT id, agent_name, situation, recommendation, run_id, created_at FROM memories ORDER BY created_at DESC"
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

    async def search_memories(self, agent_name: str, query: str, n_matches: int = 10) -> List[Dict[str, Any]]:
        if agent_name not in self._memories:
            raise KeyError(f"Unknown agent '{agent_name}'")

        mem = self._memories[agent_name]
        matches = mem.get_memories(query, n_matches=n_matches)
        return [
            {
                "matched_situation": m["matched_situation"],
                "recommendation": m["recommendation"],
                "similarity_score": m["similarity_score"],
            }
            for m in matches
        ]

    async def _rebuild_agent_memory(self, agent_name: str) -> None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT situation, recommendation FROM memories WHERE agent_name = ? ORDER BY created_at ASC",
                (agent_name,),
            )
            rows = await cursor.fetchall()

        mem = self._memories[agent_name]
        mem.clear()
        pairs = [((row["situation"] or ""), (row["recommendation"] or "")) for row in rows]
        if pairs:
            mem.add_situations(pairs)


memory_bridge = MemoryBridge()
