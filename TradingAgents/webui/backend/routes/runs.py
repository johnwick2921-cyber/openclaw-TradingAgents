import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from webui.backend.database import get_db

# Will be implemented as a singleton in webui.backend.runner
from webui.backend.runner import runner_manager

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RunCreate(BaseModel):
    ticker: str
    trade_date: str
    provider: str
    deep_model: str
    quick_model: str
    effort: Optional[str] = None
    backend_url: Optional[str] = None
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    data_vendors: Optional[Dict[str, str]] = None
    tool_vendors: Optional[Dict[str, str]] = None
    selected_analysts: List[str] = Field(default_factory=list)


class ReflectRequest(BaseModel):
    returns_losses: float


class RunImport(BaseModel):
    """Schema for importing a full run (as produced by the export endpoint)."""
    run: Dict[str, Any]
    reports: List[Dict[str, Any]] = Field(default_factory=list)
    debates: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Return a run row as a dict, or None if not found."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def _fetch_full_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Return the run together with its reports and debates."""
    run = await _fetch_run(run_id)
    if run is None:
        return None

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM reports WHERE run_id = ?", (run_id,)
        )
        report_rows = await cursor.fetchall()

        cursor = await db.execute(
            "SELECT * FROM debates WHERE run_id = ?", (run_id,)
        )
        debate_rows = await cursor.fetchall()

    # Parse JSON-encoded columns in the run
    for col in ("data_vendors", "tool_vendors", "selected_analysts"):
        if col in run and isinstance(run[col], str):
            try:
                run[col] = json.loads(run[col])
            except (json.JSONDecodeError, TypeError):
                pass

    reports = [dict(r) for r in report_rows]
    debates = [dict(d) for d in debate_rows]

    return {"run": run, "reports": reports, "debates": debates}


# ---------------------------------------------------------------------------
# POST /api/runs  -- Start a new analysis
# ---------------------------------------------------------------------------

@router.post("/runs")
async def create_run(body: RunCreate) -> JSONResponse:
    # Check if a run is already active
    if runner_manager.is_running:
        raise HTTPException(status_code=409, detail="A run is already in progress.")

    run_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO runs
                (id, ticker, trade_date, provider, deep_model, quick_model,
                 effort, backend_url, max_debate_rounds, max_risk_discuss_rounds,
                 data_vendors, tool_vendors, selected_analysts, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                run_id,
                body.ticker,
                body.trade_date,
                body.provider,
                body.deep_model,
                body.quick_model,
                body.effort,
                body.backend_url,
                body.max_debate_rounds,
                body.max_risk_discuss_rounds,
                json.dumps(body.data_vendors or {}),
                json.dumps(body.tool_vendors or {}),
                json.dumps(body.selected_analysts),
                now,
            ),
        )
        await db.commit()

    # Read saved strategy config, strategy name, and data_vendors from settings
    strategy_config = {}
    strategy_name = "default"
    saved_data_vendors = {}
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT key, value FROM settings WHERE key IN ('strategy_config', 'strategy', 'data_vendors')"
        )
        rows = await cursor.fetchall()
        for row in rows:
            key, value = row["key"], row["value"]
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                continue
            if key == "strategy_config":
                strategy_config = parsed if isinstance(parsed, dict) else {}
            elif key == "strategy":
                strategy_name = parsed if isinstance(parsed, str) else "default"
            elif key == "data_vendors":
                # Handle double-encoded JSON
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except (ValueError, TypeError):
                        pass
                saved_data_vendors = parsed if isinstance(parsed, dict) else {}

    # Build the config dict expected by the runner
    # Priority: request body > saved settings > defaults
    config_dict = {
        "ticker": body.ticker,
        "trade_date": body.trade_date,
        "provider": body.provider,
        "deep_model": body.deep_model,
        "quick_model": body.quick_model,
        "backend_url": body.backend_url,
        "max_debate_rounds": body.max_debate_rounds,
        "max_risk_discuss_rounds": body.max_risk_discuss_rounds,
        "data_vendors": body.data_vendors or saved_data_vendors or {},
        "tool_vendors": body.tool_vendors or {},
        "selected_analysts": body.selected_analysts,
        "strategy": strategy_name,
        "strategy_config": strategy_config,
    }
    if body.effort is not None:
        config_dict["effort"] = body.effort

    runner_manager.start_run(run_id=run_id, config_dict=config_dict)

    return JSONResponse(
        content={"run_id": run_id, "status": "running"},
        status_code=201,
    )


# ---------------------------------------------------------------------------
# GET /api/runs  -- List runs (with filtering / pagination)
# ---------------------------------------------------------------------------

@router.get("/runs")
async def list_runs(
    ticker: Optional[str] = None,
    signal: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    conditions: List[str] = []
    params: List[Any] = []

    if ticker:
        conditions.append("ticker = ?")
        params.append(ticker)
    if signal:
        conditions.append("signal = ?")
        params.append(signal)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if from_date:
        conditions.append("created_at >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("created_at <= ?")
        params.append(to_date)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Whitelist sortable columns to prevent SQL injection
    allowed_sort = {"created_at", "ticker", "status", "signal", "trade_date"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    # SECURITY: sort_by is whitelisted above. order_dir is restricted to ASC/DESC. Safe for f-string.
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    offset = (page - 1) * per_page

    async with get_db() as db:
        # Total count
        count_cursor = await db.execute(
            f"SELECT COUNT(*) as cnt FROM runs {where_clause}", params
        )
        total_row = await count_cursor.fetchone()
        total = total_row["cnt"] if total_row else 0

        # Page of results
        query = (
            f"SELECT * FROM runs {where_clause} "
            f"ORDER BY {sort_by} {order_dir} "
            f"LIMIT ? OFFSET ?"
        )
        cursor = await db.execute(query, params + [per_page, offset])
        rows = await cursor.fetchall()

    runs = []
    for row in rows:
        r = dict(row)
        for col in ("data_vendors", "tool_vendors", "selected_analysts"):
            if col in r and isinstance(r[col], str):
                try:
                    r[col] = json.loads(r[col])
                except (json.JSONDecodeError, TypeError):
                    pass
        runs.append(r)

    return {"runs": runs, "total": total, "page": page, "per_page": per_page}


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}  -- Full run details
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    result = await _fetch_full_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return result


# ---------------------------------------------------------------------------
# DELETE /api/runs/{run_id}  -- Delete a run (cascade)
# ---------------------------------------------------------------------------

@router.delete("/runs/{run_id}")
async def delete_run(run_id: str) -> dict:
    async with get_db() as db:
        # Check existence first
        cursor = await db.execute("SELECT id FROM runs WHERE id = ?", (run_id,))
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Run not found.")

        # SQLite foreign-key cascades require PRAGMA foreign_keys = ON which
        # may not be set, so delete explicitly from child tables as well.
        await db.execute("DELETE FROM reports WHERE run_id = ?", (run_id,))
        await db.execute("DELETE FROM debates WHERE run_id = ?", (run_id,))
        await db.execute("DELETE FROM memories WHERE run_id = ?", (run_id,))
        await db.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        await db.commit()

    return {"deleted": True}


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/cancel  -- Cancel an active run
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict:
    run = await _fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run["status"] != "running":
        raise HTTPException(status_code=409, detail="Run is not currently running.")

    runner_manager.cancel_run()

    async with get_db() as db:
        await db.execute(
            "UPDATE runs SET status = 'cancelled' WHERE id = ?", (run_id,)
        )
        await db.commit()

    return {"cancelled": True}


# ---------------------------------------------------------------------------
# POST /api/runs/reset  -- Force-reset stuck runner state
# ---------------------------------------------------------------------------

@router.post("/runs/reset")
async def reset_runner() -> dict:
    """Force-reset the runner when it's stuck thinking a run is active."""
    runner_manager.force_reset()

    # Also mark any 'running' rows in DB as failed
    async with get_db() as db:
        await db.execute(
            "UPDATE runs SET status = 'failed', error_message = 'Force-reset by user' WHERE status = 'running'"
        )
        await db.commit()

    return {"reset": True}


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/reflect  -- Submit PnL for reflection (stub)
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/reflect")
async def reflect_run(run_id: str, body: ReflectRequest) -> dict:
    run = await _fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    # Load reports for this run
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT section_name, content FROM reports WHERE run_id = ?", (run_id,)
        )
        report_rows = await cursor.fetchall()

    reports = {r["section_name"]: r["content"] for r in report_rows}
    situation = "\n\n".join(
        reports.get(k, "") for k in
        ["market_report", "sentiment_report", "news_report", "fundamentals_report"]
        if reports.get(k)
    )

    if not situation:
        raise HTTPException(status_code=400, detail="No reports found for this run. Cannot reflect.")

    # Build recommendation from each agent's perspective
    returns_str = f"Actual P&L: ${body.returns_losses:.2f}"
    outcome = "profitable" if body.returns_losses > 0 else "loss"

    from webui.backend.memory_bridge import memory_bridge
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    # For each agent, create a memory entry linking situation to outcome
    agent_reports = {
        "bull": reports.get("investment_plan", ""),
        "bear": reports.get("investment_plan", ""),
        "trader": reports.get("trader_investment_plan", ""),
        "invest_judge": reports.get("investment_plan", ""),
        "portfolio_manager": reports.get("final_trade_decision", ""),
    }

    async with get_db() as db:
        for agent_name, agent_report in agent_reports.items():
            if not agent_report:
                continue
            recommendation = (
                f"{returns_str}. Outcome: {outcome}. "
                f"The agent's analysis was: {agent_report[:500]}... "
                f"Lesson: {'This approach worked — repeat similar setups.' if body.returns_losses > 0 else 'This approach failed — review what went wrong and adjust.'}"
            )
            await db.execute(
                "INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (agent_name, situation[:2000], recommendation, run_id, now),
            )
            inserted += 1
        await db.commit()

    # Reload memories into BM25 instances
    await memory_bridge.load_from_db()

    return {"status": "completed", "memories_created": inserted, "returns_losses": body.returns_losses}


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/rerun  -- Re-run with the same config
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/rerun")
async def rerun(run_id: str) -> JSONResponse:
    run = await _fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    # Reconstruct a RunCreate from the stored config
    selected_analysts = run.get("selected_analysts", "[]")
    if isinstance(selected_analysts, str):
        selected_analysts = json.loads(selected_analysts)

    data_vendors = run.get("data_vendors", "{}")
    if isinstance(data_vendors, str):
        data_vendors = json.loads(data_vendors)

    tool_vendors = run.get("tool_vendors", "{}")
    if isinstance(tool_vendors, str):
        tool_vendors = json.loads(tool_vendors)

    body = RunCreate(
        ticker=run["ticker"],
        trade_date=run["trade_date"],
        provider=run["provider"],
        deep_model=run["deep_model"],
        quick_model=run["quick_model"],
        effort=run.get("effort"),
        backend_url=run.get("backend_url"),
        max_debate_rounds=run.get("max_debate_rounds", 1),
        max_risk_discuss_rounds=run.get("max_risk_discuss_rounds", 1),
        data_vendors=data_vendors,
        tool_vendors=tool_vendors,
        selected_analysts=selected_analysts,
    )

    return await create_run(body)


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/tokens  -- Token breakdown (stub)
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/tokens")
async def get_tokens(run_id: str) -> dict:
    run = await _fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return {
        "run_id": run_id,
        "tokens_in": run.get("tokens_in", 0),
        "tokens_out": run.get("tokens_out", 0),
        "breakdown": {},
    }


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/timing  -- Timing breakdown (stub)
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/timing")
async def get_timing(run_id: str) -> dict:
    run = await _fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return {
        "run_id": run_id,
        "duration_seconds": run.get("duration_seconds"),
        "breakdown": {},
    }


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/tools  -- Tool calls log (stub)
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/tools")
async def get_tools(run_id: str) -> dict:
    run = await _fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return {"run_id": run_id, "tool_calls": []}


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/export  -- Export a run as JSON
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/export")
async def export_run(run_id: str) -> JSONResponse:
    result = await _fetch_full_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    return JSONResponse(
        content=result,
        headers={
            "Content-Disposition": f'attachment; filename="run_{run_id}.json"'
        },
    )


# ---------------------------------------------------------------------------
# POST /api/runs/import  -- Import a run from JSON
# ---------------------------------------------------------------------------

@router.post("/runs/import")
async def import_run(body: RunImport) -> JSONResponse:
    run_data = body.run
    run_id = run_data.get("id") or uuid.uuid4().hex

    async with get_db() as db:
        # Check for duplicate
        cursor = await db.execute("SELECT id FROM runs WHERE id = ?", (run_id,))
        if await cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Run {run_id} already exists. Delete it first or change the id.",
            )

        await db.execute(
            """
            INSERT INTO runs
                (id, ticker, trade_date, provider, deep_model, quick_model,
                 effort, backend_url, max_debate_rounds, max_risk_discuss_rounds,
                 data_vendors, tool_vendors, selected_analysts,
                 signal, status, error_message,
                 tokens_in, tokens_out, duration_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_data.get("ticker", ""),
                run_data.get("trade_date", ""),
                run_data.get("provider", ""),
                run_data.get("deep_model"),
                run_data.get("quick_model"),
                run_data.get("effort"),
                run_data.get("backend_url"),
                run_data.get("max_debate_rounds", 1),
                run_data.get("max_risk_discuss_rounds", 1),
                json.dumps(run_data.get("data_vendors", {}))
                if not isinstance(run_data.get("data_vendors"), str)
                else run_data.get("data_vendors", "{}"),
                json.dumps(run_data.get("tool_vendors", {}))
                if not isinstance(run_data.get("tool_vendors"), str)
                else run_data.get("tool_vendors", "{}"),
                json.dumps(run_data.get("selected_analysts", []))
                if not isinstance(run_data.get("selected_analysts"), str)
                else run_data.get("selected_analysts", "[]"),
                run_data.get("signal"),
                run_data.get("status", "imported"),
                run_data.get("error_message"),
                run_data.get("tokens_in", 0),
                run_data.get("tokens_out", 0),
                run_data.get("duration_seconds"),
                run_data.get("created_at", datetime.now(timezone.utc).isoformat()),
            ),
        )

        for report in body.reports:
            await db.execute(
                "INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)",
                (run_id, report.get("section_name", ""), report.get("content")),
            )

        for debate in body.debates:
            await db.execute(
                """
                INSERT INTO debates
                    (run_id, debate_type, full_history,
                     side_a_history, side_b_history, side_c_history,
                     judge_decision)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    debate.get("debate_type"),
                    debate.get("full_history"),
                    debate.get("side_a_history"),
                    debate.get("side_b_history"),
                    debate.get("side_c_history"),
                    debate.get("judge_decision"),
                ),
            )

        await db.commit()

    return JSONResponse(
        content={"imported": True, "run_id": run_id},
        status_code=201,
    )


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/compare/{other_id}  -- Compare two runs
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/compare/{other_id}")
async def compare_runs(run_id: str, other_id: str) -> dict:
    run1 = await _fetch_full_run(run_id)
    if run1 is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    run2 = await _fetch_full_run(other_id)
    if run2 is None:
        raise HTTPException(status_code=404, detail=f"Run {other_id} not found.")

    return {"run1": run1, "run2": run2}
