"""WebSocket handler for live-streaming analysis events.

Provides a FastAPI WebSocket endpoint at ``/ws/runs/{run_id}`` that streams
events from the RunnerManager to connected clients in real time.  Supports
reconnect replay via the ``last_event_id`` query parameter.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from webui.backend.runner import runner_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def ws_run_events(
    websocket: WebSocket,
    run_id: str,
    last_event_id: Optional[int] = Query(default=0),
) -> None:
    """Stream analysis events for a specific run over WebSocket.

    Connection lifecycle:
      1. **Validate** that ``run_id`` matches the currently active run.
         If not, close immediately with code 4004.
      2. **Replay** any missed events since ``last_event_id`` (supports
         client reconnect).
      3. **Register** the connection with RunnerManager so it receives
         future events via broadcast.
      4. **Keep alive** until the client disconnects or the run ends.
      5. **Unregister** on disconnect.

    Query params:
        last_event_id: Events with ``id <= last_event_id`` are skipped
            during replay.  Defaults to 0 (replay all).
    """
    await websocket.accept()

    # Accept connection if this run is active OR was recently active
    # (handles race: WebSocket connects after thread crashed/finished)
    is_active = runner_manager.active_run_id == run_id
    has_events = len(runner_manager.events) > 0 and any(
        e.get("run_id") == run_id for e in runner_manager.events
    )
    if not is_active and not has_events:
        # Check DB — maybe the run completed before WS connected
        import aiosqlite
        from webui.backend.database import DB_PATH
        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT status FROM runs WHERE id = ?", (run_id,))
            result = await row.fetchone()
        if result and result[0] in ("completed", "failed", "cancelled"):
            await websocket.send_json({
                "type": result[0],
                "data": {"message": f"Run already {result[0]}", "stop_reconnect": True},
            })
            await websocket.close(code=4000, reason="Run finished")
            return
        elif not result:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"Run {run_id} not found", "stop_reconnect": True},
            })
            await websocket.close(code=4004, reason="Run not found")
            return

    # Replay missed events for reconnecting clients
    since = last_event_id or 0
    missed_events = runner_manager.get_events(since_id=since)
    for event in missed_events:
        try:
            await websocket.send_json(event)
        except Exception:
            logger.debug("Failed to send replay event to client, closing.")
            return

    # Register for live broadcasts
    runner_manager.ws_connections.add(websocket)
    logger.info(
        "WebSocket client connected for run %s (replay from event %d, "
        "sent %d missed events)",
        run_id,
        since,
        len(missed_events),
    )

    try:
        # Keep the connection alive by consuming client messages.
        # We don't expect meaningful inbound data, but the receive loop
        # prevents the connection from being garbage-collected and also
        # lets us detect client-side disconnects cleanly.
        while True:
            data = await websocket.receive_text()

            # Support client-side ping/pong for keepalive
            if data == "ping":
                try:
                    await websocket.send_json({"type": "pong", "data": {}})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from run %s", run_id)

    except Exception as exc:
        logger.debug("WebSocket error for run %s: %s", run_id, exc)

    finally:
        runner_manager.ws_connections.discard(websocket)
        logger.debug(
            "WebSocket unregistered for run %s (%d connections remaining)",
            run_id,
            len(runner_manager.ws_connections),
        )
