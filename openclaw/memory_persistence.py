"""BM25 <-> SQLite synchronization for FinancialSituationMemory.

Persist in-memory BM25 stores to the ``memories`` table and reload them
on startup so agent memories survive across sessions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict

from openclaw.memory import FinancialSituationMemory

from openclaw.database import get_db

logger = logging.getLogger(__name__)


def persist_memories(
    memories_dict: Dict[str, FinancialSituationMemory],
    db_path: str,
    run_id: str,
) -> int:
    """Write BM25 entries to SQLite, deduplicating against existing rows.

    For each agent memory store, inserts only (situation, recommendation)
    pairs that do not already exist in the database for that agent.

    Args:
        memories_dict: Mapping of agent_name -> FinancialSituationMemory.
        db_path: Path to the SQLite database file.
        run_id: The run that produced these memories.

    Returns:
        Number of new rows inserted.
    """
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with get_db(db_path) as conn:
        for agent_name, mem in memories_dict.items():
            # Fetch existing (situation, recommendation) pairs for this agent
            cursor = conn.execute(
                "SELECT situation, recommendation FROM memories WHERE agent_name = ?",
                (agent_name,),
            )
            existing = {(row["situation"], row["recommendation"]) for row in cursor}

            for i in range(len(mem.documents)):
                situation = mem.documents[i]
                recommendation = mem.recommendations[i] if i < len(mem.recommendations) else ""
                pair = (situation, recommendation)

                if pair in existing:
                    continue

                conn.execute(
                    "INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (agent_name, situation, recommendation, run_id, now),
                )
                existing.add(pair)
                inserted += 1

        conn.commit()

    logger.info("Persisted %d new memories for run %s", inserted, run_id)
    return inserted


def hydrate_memories(
    memories_dict: Dict[str, FinancialSituationMemory],
    db_path: str,
) -> int:
    """Load memories from SQLite into BM25 stores.

    Clears each memory instance first, then populates from database rows.

    Args:
        memories_dict: Mapping of agent_name -> FinancialSituationMemory.
        db_path: Path to the SQLite database file.

    Returns:
        Total number of memories loaded.
    """
    total = 0

    with get_db(db_path) as conn:
        for agent_name, mem in memories_dict.items():
            mem.clear()

            cursor = conn.execute(
                "SELECT situation, recommendation FROM memories "
                "WHERE agent_name = ? ORDER BY created_at ASC",
                (agent_name,),
            )
            rows = cursor.fetchall()

            pairs = [
                (row["situation"] or "", row["recommendation"] or "")
                for row in rows
                if (row["situation"] or row["recommendation"])
            ]

            if pairs:
                mem.add_situations(pairs)

            total += len(pairs)

    logger.info("Hydrated %d total memories across %d agents", total, len(memories_dict))
    return total
