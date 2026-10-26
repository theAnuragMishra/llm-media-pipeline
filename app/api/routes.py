"""Core REST API endpoints for video generation and status retrieval."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from app.config import settings
from app.core.broker import broker
from app.core.events import event_bus
from app.models.schemas import (
    VideoGenerationRequest,
    TaskResponse,
    TaskStatus,
    TaskStage,
)

router = APIRouter(prefix="/api/v1", tags=["Video Generation Pipeline"])


@router.post(
    "/generate-course-video",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue async video generation job",
    description="Accepts a topic, creates an async background task, and returns status & real-time streaming URLs.",
)
async def generate_course_video(request: VideoGenerationRequest) -> TaskResponse:
    """
    Submits a video generation request to the message broker (RabbitMQ / async queue).
    Clients can immediately stream live updates via SSE or WebSockets.
    """
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    # Seed initial task state
    initial_status = TaskStatus(
        task_id=task_id,
        topic=request.topic,
        stage=TaskStage.QUEUED,
        progress_percent=0,
        message="Task accepted and enqueued for processing.",
        created_at=now,
        updated_at=now,
        metadata={
            "target_scenes": request.target_scenes,
            "voice": request.voice,
            "resolution": request.resolution,
            "style": request.style,
        },
    )
    await event_bus.set_task_status(initial_status)

    # Dispatch to RabbitMQ / in-memory broker
    task_payload = {
        "task_id": task_id,
        "topic": request.topic,
        "target_scenes": request.target_scenes,
        "voice": request.voice,
        "resolution": request.resolution,
        "style": request.style,
        "created_at": now,
    }
    await broker.publish_job(task_payload)

    return TaskResponse(
        task_id=task_id,
        topic=request.topic,
        status="ACCEPTED",
        stage=TaskStage.QUEUED,
        sse_url=f"/api/v1/tasks/{task_id}/events",
        ws_url=f"/ws/tasks/{task_id}",
        poll_url=f"/api/v1/tasks/{task_id}",
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatus,
    summary="Poll task progress snapshot",
)
async def get_task_status(task_id: str) -> TaskStatus:
    """Returns the current state and progress snapshot of a given task."""
    status_obj = await event_bus.get_task_status(task_id)
    if not status_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )
    return status_obj


@router.get("/health", tags=["Health"])
async def health_check():
    """Healthcheck endpoint for orchestrator and container probes."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "broker_mode": settings.BROKER_TYPE,
        "tts_provider": settings.TTS_PROVIDER,
        "llm_provider": settings.LLM_PROVIDER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
