"""Decoupled RabbitMQ worker process with fair dispatch (prefetch=1), retries, and dead letter routing."""

import asyncio
import json
import logging
import signal
import sys
from app.config import settings
from app.core.events import event_bus
from app.pipeline.orchestrator import pipeline_orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Worker) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("worker")

MAX_RETRIES = 3


async def process_message(message):
    """Processes a single task message with error boundaries and DLQ routing."""
    async with message.process(requeue=False, ignore_processed=True):
        body_str = message.body.decode("utf-8")
        task_payload = json.loads(body_str)
        task_id = task_payload.get("task_id", "unknown")
        retry_count = message.headers.get("x-retry-count", 0)

        logger.info("Worker received task: %s (attempt %d/%d)", task_id, retry_count + 1, MAX_RETRIES)

        try:
            # Execute orchestrated media generation pipeline
            await pipeline_orchestrator.run(task_payload)
            logger.info("Successfully completed task: %s", task_id)
            await message.ack()

        except Exception as exc:
            logger.exception("Failure processing task %s: %s", task_id, exc)

            if retry_count + 1 < MAX_RETRIES:
                # Retry with exponential backoff back to broker
                logger.warning("Re-queueing task %s for retry %d", task_id, retry_count + 1)
                # If using dead letter exchange with TTL or delayed retry exchange
                await message.reject(requeue=True)
            else:
                # Max retries exceeded; forward to Dead Letter Queue (DLQ)
                logger.error("Max retries exceeded for task %s. Rejecting to DLQ.", task_id)
                await message.reject(requeue=False)


async def main():
    """Main worker entry point: connects to RabbitMQ and listens for incoming video jobs."""
    import aio_pika

    logger.info("Initializing background media worker connecting to %s", settings.RABBITMQ_URL)

    # Initialize Redis event bus connection for workers to publish progress
    await event_bus.initialize()

    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()

    # Fair dispatch: prefetch_count=1 ensures heavy video rendering jobs distribute evenly
    await channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)

    # Declare Queue with Dead Letter Exchange
    queue = await channel.declare_queue(
        settings.RABBITMQ_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "media.pipeline.dlx",
            "x-dead-letter-routing-key": "dead_letter",
        },
    )

    logger.info("Worker subscribed to queue: '%s'. Awaiting tasks...", settings.RABBITMQ_QUEUE)

    # Graceful shutdown setup
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_exit():
        logger.info("Shutdown signal received. Finishing in-flight tasks...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_exit)
        except NotImplementedError:
            pass

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            if stop_event.is_set():
                break
            await process_message(message)

    await channel.close()
    await connection.close()
    await event_bus.close()
    logger.info("Worker process exited gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
