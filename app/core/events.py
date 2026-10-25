"""Real-time event broadcasting bus supporting both Redis Pub/Sub and in-memory async queues.

Provides zero-configuration fallback so the microservice functions cleanly both
with and without an external Redis instance.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Set
from datetime import datetime, timezone
from app.config import settings
from app.models.schemas import PipelineProgress, TaskStage, TaskStatus

logger = logging.getLogger(__name__)


class EventBus:
    """Pub/Sub broker for pipeline status events with persistent state cache."""

    def __init__(self):
        self._memory_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._task_cache: Dict[str, TaskStatus] = {}
        self._lock = asyncio.Lock()
        self._redis_client = None

    async def initialize(self):
        """Optionally connect to Redis if available, else use in-memory fallback."""
        try:
            import redis.asyncio as redis
            client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.ping()
            self._redis_client = client
            logger.info("Connected to Redis Pub/Sub at %s", settings.REDIS_URL)
        except Exception as e:
            logger.info("Redis not reachable (%s). Using high-concurrency in-memory event bus.", e)
            self._redis_client = None

    async def close(self):
        """Close connection to Redis if initialized."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

    async def get_task_status(self, task_id: str) -> TaskStatus | None:
        """Fetch the latest status of a task from cache or Redis."""
        if self._redis_client:
            try:
                data = await self._redis_client.get(f"task_state:{task_id}")
                if data:
                    return TaskStatus.model_validate_json(data)
            except Exception as e:
                logger.warning("Error fetching task state from Redis: %s", e)

        async with self._lock:
            return self._task_cache.get(task_id)

    async def set_task_status(self, status: TaskStatus):
        """Store task status in memory and Redis."""
        async with self._lock:
            self._task_cache[status.task_id] = status

        if self._redis_client:
            try:
                await self._redis_client.set(
                    f"task_state:{status.task_id}",
                    status.model_dump_json(),
                    ex=86400,  # 24h TTL
                )
            except Exception as e:
                logger.warning("Error caching task state to Redis: %s", e)

    async def publish(self, progress: PipelineProgress):
        """Publish a pipeline progress event to all active SSE/WebSocket subscribers."""
        # 1. Update persistent task state
        now = datetime.now(timezone.utc).isoformat()
        current_status = await self.get_task_status(progress.task_id)
        created_at = current_status.created_at if current_status else now

        status = TaskStatus(
            task_id=progress.task_id,
            topic=progress.topic,
            stage=progress.stage,
            progress_percent=progress.progress_percent,
            message=progress.message,
            video_url=progress.video_url,
            thumbnail_url=progress.thumbnail_url,
            error=progress.error,
            created_at=created_at,
            updated_at=now,
        )
        await self.set_task_status(status)

        # 2. Redis broadcast if available
        payload = progress.model_dump_json()
        if self._redis_client:
            try:
                channel = f"task_events:{progress.task_id}"
                await self._redis_client.publish(channel, payload)
            except Exception as e:
                logger.warning("Redis publish error: %s", e)

        # 3. In-memory subscribers broadcast
        async with self._lock:
            subscribers = self._memory_subscribers.get(progress.task_id, set()).copy()

        for q in subscribers:
            try:
                q.put_nowait(progress)
            except Exception as e:
                logger.debug("Failed to put event into subscriber queue: %s", e)

    async def subscribe(self, task_id: str) -> AsyncGenerator[PipelineProgress, None]:
        """Subscribe to real-time events for a task. Yields PipelineProgress models."""
        queue: asyncio.Queue[PipelineProgress] = asyncio.Queue()

        # Emit initial state if task already exists
        initial_status = await self.get_task_status(task_id)
        if initial_status:
            yield PipelineProgress(
                task_id=initial_status.task_id,
                topic=initial_status.topic,
                stage=initial_status.stage,
                progress_percent=initial_status.progress_percent,
                message=initial_status.message,
                video_url=initial_status.video_url,
                thumbnail_url=initial_status.thumbnail_url,
                error=initial_status.error,
                timestamp=initial_status.updated_at,
            )
            # If already terminal, we're done
            if initial_status.stage in (TaskStage.COMPLETED, TaskStage.FAILED):
                return

        # Register in-memory queue
        async with self._lock:
            if task_id not in self._memory_subscribers:
                self._memory_subscribers[task_id] = set()
            self._memory_subscribers[task_id].add(queue)

        try:
            while True:
                # Wait for next event with a timeout for heartbeat ping
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                    if event.stage in (TaskStage.COMPLETED, TaskStage.FAILED):
                        break
                except asyncio.TimeoutError:
                    # Heartbeat keep-alive check
                    task_now = await self.get_task_status(task_id)
                    if task_now and task_now.stage in (TaskStage.COMPLETED, TaskStage.FAILED):
                        break
                    # Send a heartbeat event
                    yield PipelineProgress(
                        task_id=task_id,
                        topic=(task_now.topic if task_now else "unknown"),
                        stage=(task_now.stage if task_now else TaskStage.QUEUED),
                        progress_percent=(task_now.progress_percent if task_now else 0),
                        message="[Heartbeat] Processing in progress...",
                    )
        finally:
            async with self._lock:
                if task_id in self._memory_subscribers:
                    self._memory_subscribers[task_id].discard(queue)
                    if not self._memory_subscribers[task_id]:
                        del self._memory_subscribers[task_id]


event_bus = EventBus()
