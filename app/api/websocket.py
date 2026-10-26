"""WebSocket endpoint for bidirectional real-time progress streaming and control."""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.events import event_bus
from app.models.schemas import TaskStage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Real-time Streaming (WebSocket)"])


@router.websocket("/ws/tasks/{task_id}")
async def task_websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    Bi-directional WebSocket endpoint broadcasting pipeline progress events.
    Supports client heartbeats and graceful disconnects.
    """
    await websocket.accept()
    logger.info("WebSocket connected for task %s", task_id)

    try:
        async for progress in event_bus.subscribe(task_id):
            await websocket.send_text(progress.model_dump_json())

            if progress.stage in (TaskStage.COMPLETED, TaskStage.FAILED):
                # Allow final render frame to land before closing
                await websocket.close(code=1000, reason="Pipeline execution finalized.")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally for task %s", task_id)
    except Exception as e:
        logger.error("WebSocket error on task %s: %s", task_id, e)
        try:
            await websocket.send_text(json.dumps({"error": str(e), "task_id": task_id}))
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
