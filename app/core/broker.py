"""Message broker interface with RabbitMQ (aio-pika) and in-memory background worker fallback."""

import asyncio
import json
import logging
from typing import Callable, Coroutine, Any, Dict
from app.config import settings

logger = logging.getLogger(__name__)


class MessageBroker:
    """Manages publishing and routing of video generation jobs to RabbitMQ or async workers."""

    def __init__(self):
        self._connection = None
        self._channel = None
        self._exchange = None
        self._connected = False

    async def connect(self):
        """Establish connection to RabbitMQ with exchange and DLQ topology setup."""
        if settings.BROKER_TYPE != "rabbitmq":
            logger.info("Broker running in '%s' mode (in-process async scheduler).", settings.BROKER_TYPE)
            return

        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)

            # Declare Dead Letter Exchange (DLX) and Queue (DLQ)
            dlx = await self._channel.declare_exchange(
                "media.pipeline.dlx",
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )
            dlq = await self._channel.declare_queue("video.generate.dlq", durable=True)
            await dlq.bind(dlx, routing_key="dead_letter")

            # Declare Main Topic Exchange
            self._exchange = await self._channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            # Declare Main Work Queue bound with DLX configuration
            work_queue = await self._channel.declare_queue(
                settings.RABBITMQ_QUEUE,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "media.pipeline.dlx",
                    "x-dead-letter-routing-key": "dead_letter",
                    "x-message-ttl": 3600000,  # 1 hour TTL
                },
            )
            await work_queue.bind(self._exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)

            self._connected = True
            logger.info("RabbitMQ broker topology successfully initialized.")
        except Exception as e:
            logger.warning(
                "Could not connect to RabbitMQ at %s: %s. Falling back to in-memory async processing.",
                settings.RABBITMQ_URL,
                e,
            )
            self._connected = False

    async def close(self):
        """Cleanly close RabbitMQ channel and connection."""
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        self._connected = False

    async def publish_job(self, task_payload: Dict[str, Any]):
        """
        Publish a video generation job.
        If RabbitMQ is active, publishes a durable persistent AMQP message.
        Otherwise executes via in-process background task.
        """
        if self._connected and self._exchange:
            import aio_pika
            message = aio_pika.Message(
                body=json.dumps(task_payload).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={"task_id": task_payload.get("task_id", "")},
            )
            await self._exchange.publish(message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            logger.info("Published task %s to RabbitMQ exchange '%s'", task_payload.get("task_id"), settings.RABBITMQ_EXCHANGE)
        else:
            # In-memory execution
            from app.pipeline.orchestrator import pipeline_orchestrator
            logger.info("Dispatching task %s to in-memory background worker", task_payload.get("task_id"))
            asyncio.create_task(pipeline_orchestrator.run(task_payload))


broker = MessageBroker()
