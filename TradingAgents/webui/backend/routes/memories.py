from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from webui.backend.database import get_db

router = APIRouter(prefix="/api")

# Valid agent names (must match what the trading system uses)
VALID_AGENTS = {"bull", "bear", "trader", "invest_judge", "portfolio_manager"}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MemoryItem(BaseModel):
    agent_name: str
    situation: Optional[str] = None
    recommendation: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None


class MemoriesImport(BaseModel):
    memories: List[MemoryItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_agent(agent: str) -> None:
    """Raise 422 if the agent name is not recognized."""
    if agent not in VALID_AGENTS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid agent '{agent}'. Must be one of: {', '.join(sorted(VALID_AGENTS))}",
        )


# ---------------------------------------------------------------------------
# IMPORTANT: Literal-path routes MUST be declared before {agent} routes so
# that FastAPI does not try to match "export" / "import" as an agent name.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /api/memories/export  -- Export all memories grouped by agent
# ---------------------------------------------------------------------------

@router.get("/memories/export")
async def export_memories() -> JSONResponse:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM memories ORDER BY agent_name, created_at DESC"
        )
        rows = await cursor.fetchall()

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        d = dict(row)
        agent = d.get("agent_name", "unknown")
        grouped.setdefault(agent, []).append(d)

    return JSONResponse(
        content=grouped,
        headers={
            "Content-Disposition": 'attachment; filename="memories_export.json"'
        },
    )


# ---------------------------------------------------------------------------
# POST /api/memories/import  -- Import memories from JSON
# ---------------------------------------------------------------------------

@router.post("/memories/import")
async def import_memories(body: MemoriesImport) -> JSONResponse:
    imported_count = 0

    async with get_db() as db:
        for mem in body.memories:
            if mem.agent_name not in VALID_AGENTS:
                # Skip invalid agent entries silently during import
                continue

            created_at = mem.created_at or datetime.now(timezone.utc).isoformat()
            await db.execute(
                """
                INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mem.agent_name, mem.situation, mem.recommendation, mem.run_id, created_at),
            )
            imported_count += 1

        await db.commit()

    return JSONResponse(
        content={"imported_count": imported_count},
        status_code=201,
    )


# ---------------------------------------------------------------------------
# GET /api/memories/{agent}  -- List memories for an agent
# ---------------------------------------------------------------------------

@router.get("/memories/{agent}")
async def list_memories(agent: str) -> dict:
    _validate_agent(agent)

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM memories WHERE agent_name = ? ORDER BY created_at DESC",
            (agent,),
        )
        rows = await cursor.fetchall()

    memories = [dict(row) for row in rows]
    return {"memories": memories, "count": len(memories)}


# ---------------------------------------------------------------------------
# GET /api/memories/{agent}/search  -- Search memories
# ---------------------------------------------------------------------------

@router.get("/memories/{agent}/search")
async def search_memories(agent: str, q: str = Query(..., min_length=1)) -> dict:
    _validate_agent(agent)

    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM memories
            WHERE agent_name = ?
              AND (situation LIKE ? ESCAPE '\\' OR recommendation LIKE ? ESCAPE '\\')
            ORDER BY created_at DESC
            """,
            (agent, pattern, pattern),
        )
        rows = await cursor.fetchall()

    memories = [dict(row) for row in rows]
    return {"memories": memories, "count": len(memories)}


# ---------------------------------------------------------------------------
# DELETE /api/memories/{agent}  -- Clear all memories for an agent
# ---------------------------------------------------------------------------

@router.delete("/memories/{agent}")
async def clear_memories(agent: str) -> dict:
    _validate_agent(agent)

    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM memories WHERE agent_name = ?", (agent,)
        )
        await db.commit()
        deleted_count = cursor.rowcount

    return {"deleted_count": deleted_count}


# ---------------------------------------------------------------------------
# DELETE /api/memories/{agent}/{memory_id}  -- Delete a single memory
# ---------------------------------------------------------------------------

@router.delete("/memories/{agent}/{memory_id}")
async def delete_memory(agent: str, memory_id: int) -> dict:
    _validate_agent(agent)

    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM memories WHERE id = ? AND agent_name = ?",
            (memory_id, agent),
        )
        await db.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Memory {memory_id} not found for agent '{agent}'.",
            )

    return {"deleted": True}
