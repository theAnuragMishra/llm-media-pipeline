"""Server-Sent Events (SSE) endpoint for streaming real-time pipeline status."""

import asyncio
import json
import logging
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.core.events import event_bus
from app.models.schemas import TaskStage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Real-time Streaming (SSE)"])


@router.get(
    "/tasks/{task_id}/events",
    summary="Stream real-time task progress via Server-Sent Events",
    description="Maintains an open HTTP connection yielding continuous status updates as pipeline executes.",
)
async def task_events_sse(task_id: str, request: Request):
    """Streams real-time pipeline events to frontend via standard SSE protocol."""

    async def event_generator():
        logger.info("Client connected to SSE stream for task %s", task_id)
        try:
            async for progress in event_bus.subscribe(task_id):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected for task %s", task_id)
                    break

                yield {
                    "event": "progress",
                    "id": f"{task_id}_{progress.progress_percent}",
                    "retry": 15000,
                    "data": progress.model_dump_json(),
                }

                if progress.stage in (TaskStage.COMPLETED, TaskStage.FAILED):
                    break
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled for task %s", task_id)
        except Exception as e:
            logger.error("Error in SSE event generator for task %s: %s", task_id, e)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e), "task_id": task_id}),
            }

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
