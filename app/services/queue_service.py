"""Queue service — Kafka producer for publishing message events.

When FastAPI receives a message through any channel, the IntakeService
calls `enqueue_message()` to publish an event to the `customer_messages`
Kafka topic. The downstream Kafka consumer (worker) picks it up and
triggers the AI agent.

Lifecycle:
  - `start()` is called during FastAPI startup  (lifespan)
  - `stop()`  is called during FastAPI shutdown (lifespan)
  - `enqueue_message()` is called per intake request
"""

import json
from typing import ClassVar

from aiokafka import AIOKafkaProducer

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.intake import IntakeResult

logger = get_logger(__name__)

TOPIC_CUSTOMER_MESSAGES = "customer_messages"


class QueueService:
    """Singleton Kafka producer wrapper.

    Usage:
        # In FastAPI lifespan:
        await QueueService.start()
        yield
        await QueueService.stop()

        # In request handler / service:
        await QueueService.enqueue_message(result)
    """

    _producer: ClassVar[AIOKafkaProducer | None] = None

    # ── Lifecycle ────────────────────────────────────────────

    @classmethod
    async def start(cls) -> None:
        """Create and start the Kafka producer. Call once at app startup."""
        if cls._producer is not None:
            return

        settings = get_settings()
        cls._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            # Serialize values to JSON bytes
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            # Use message_id as the Kafka key for partition ordering
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            # Durability: wait for leader acknowledgement
            acks="all",
            # Batch settings for throughput
            linger_ms=10,
            # Retry transient failures
            retry_backoff_ms=250,
        )
        await cls._producer.start()
        logger.info(
            "Kafka producer started [servers=%s]",
            settings.kafka_bootstrap_servers,
        )

    @classmethod
    async def stop(cls) -> None:
        """Flush pending messages and shut down the producer."""
        if cls._producer is None:
            return
        await cls._producer.stop()
        cls._producer = None
        logger.info("Kafka producer stopped")

    # ── Publishing ───────────────────────────────────────────

    @classmethod
    async def enqueue_message(cls, result: IntakeResult) -> None:
        """Publish a message event to the customer_messages topic.

        Payload published to Kafka:
            {
                "customer_id":        "uuid",
                "conversation_id":    "uuid",
                "message_id":         "uuid",
                "channel":            "web" | "gmail" | "whatsapp",
                "is_new_customer":    bool,
                "is_new_conversation": bool
            }

        The message_id is used as the Kafka key so all messages in the
        same conversation land on the same partition (ordering guarantee).

        Args:
            result: The IntakeResult from the intake pipeline.
        """
        if cls._producer is None:
            logger.error("Kafka producer not started — dropping message %s", result.message_id)
            return

        payload = {
            "customer_id": str(result.customer_id),
            "conversation_id": str(result.conversation_id),
            "message_id": str(result.message_id),
            "channel": result.channel.value,
            "is_new_customer": result.is_new_customer,
            "is_new_conversation": result.is_new_conversation,
        }

        # Key by conversation_id → guarantees per-conversation ordering
        key = str(result.conversation_id)

        record_metadata = await cls._producer.send_and_wait(
            topic=TOPIC_CUSTOMER_MESSAGES,
            value=payload,
            key=key,
        )

        logger.info(
            "Published to %s [partition=%d offset=%d]: message_id=%s conversation_id=%s channel=%s",
            TOPIC_CUSTOMER_MESSAGES,
            record_metadata.partition,
            record_metadata.offset,
            result.message_id,
            result.conversation_id,
            result.channel.value,
        )
