"""Kafka consumer worker — the brain executor.

This is a standalone async process that:
  1. Consumes message events from the `customer_messages` Kafka topic
  2. Loads the customer's inbound message from PostgreSQL
  3. Calls the AI Agent (OpenAI Agent SDK)
  4. The agent autonomously executes its tools:
     - get_customer_history  → reads conversation context
     - search_knowledge_base → finds relevant KB articles
     - create_ticket         → opens a support ticket
     - escalate_to_human     → routes to human queue
     - send_response         → stores the outbound reply in DB
  5. Commits the DB transaction (response + metrics persisted)

Run as a separate process:
    python -m app.workers.worker
"""

import asyncio
import json
import signal
import uuid

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select

from app.agent.agent import run_agent
from app.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.db.database import async_session_factory, engine
from app.db.models import AgentMetric, ChannelType, Message

setup_logging()
logger = get_logger(__name__)

TOPIC_CUSTOMER_MESSAGES = "customer_messages"
CONSUMER_GROUP = "agent-worker-group"


async def process_message(raw_value: bytes) -> None:
    """Process a single Kafka message end-to-end.

    Opens its own DB session so each message is an independent
    transaction — a failure in one message does not affect others.
    """
    # ── 1. Deserialize the Kafka payload ─────────────────────
    payload = json.loads(raw_value)
    customer_id = uuid.UUID(payload["customer_id"])
    conversation_id = uuid.UUID(payload["conversation_id"])
    message_id = uuid.UUID(payload["message_id"])
    channel = ChannelType(payload["channel"])

    logger.info(
        "Processing message_id=%s conversation_id=%s channel=%s",
        message_id, conversation_id, channel.value,
    )

    # ── 2. Open a DB session for the full agent lifecycle ────
    async with async_session_factory() as session:
        try:
            # ── 3. Load the inbound message text ─────────────
            stmt = select(Message).where(Message.id == message_id)
            result = await session.execute(stmt)
            message = result.scalar_one_or_none()

            if message is None:
                logger.error("Message %s not found in DB — skipping", message_id)
                return

            customer_message = message.content

            # ── 4. Run the AI Agent ──────────────────────────
            # run_agent() internally:
            #   - Builds AgentContext with this session
            #   - Calls Runner.run() which loops tool calls:
            #       get_customer_history → DB read
            #       search_knowledge_base → DB read
            #       create_ticket → DB write
            #       escalate_to_human → DB write
            #       send_response → DB write (outbound message)
            #   - Records AgentMetric → DB write
            #   - Returns the response text
            response_text = await run_agent(
                session=session,
                customer_id=customer_id,
                conversation_id=conversation_id,
                channel=channel,
                customer_message=customer_message,
            )

            # ── 5. Commit — persists response + metrics ──────
            await session.commit()

            logger.info(
                "Agent completed for message_id=%s conversation_id=%s response_length=%d",
                message_id, conversation_id, len(response_text),
            )

        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to process message_id=%s conversation_id=%s",
                message_id, conversation_id,
            )
            # Record error metric so the dashboard tracks failure rate
            try:
                async with async_session_factory() as err_session:
                    err_metric = AgentMetric(
                        conversation_id=conversation_id,
                        channel=channel,
                        resolved_by_ai=False,
                        escalated=False,
                        metadata_={"error": True, "message_id": str(message_id)},
                    )
                    err_session.add(err_metric)
                    await err_session.commit()
            except Exception:
                logger.exception("Failed to record error metric")


async def run_worker() -> None:
    """Start the Kafka consumer loop. Runs until SIGINT/SIGTERM."""
    settings = get_settings()

    consumer = AIOKafkaConsumer(
        TOPIC_CUSTOMER_MESSAGES,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_GROUP,
        # Deserialize JSON values
        value_deserializer=lambda v: v,  # raw bytes — decoded in process_message
        # Start from earliest unprocessed message on first launch
        auto_offset_reset="earliest",
        # Manual commit after successful processing
        enable_auto_commit=False,
    )

    await consumer.start()
    logger.info(
        "Worker started — consuming from '%s' [group=%s servers=%s]",
        TOPIC_CUSTOMER_MESSAGES, CONSUMER_GROUP, settings.kafka_bootstrap_servers,
    )

    try:
        async for msg in consumer:
            logger.info(
                "Received: topic=%s partition=%d offset=%d key=%s",
                msg.topic, msg.partition, msg.offset,
                msg.key.decode("utf-8") if msg.key else None,
            )

            await process_message(msg.value)

            # Commit offset only after successful processing
            await consumer.commit()

    finally:
        await consumer.stop()
        await engine.dispose()
        logger.info("Worker shut down")


def _handle_shutdown(loop: asyncio.AbstractEventLoop, task: asyncio.Task) -> None:
    """Cancel the worker task on SIGINT/SIGTERM for graceful shutdown."""
    logger.info("Shutdown signal received — stopping worker")
    task.cancel()


def main() -> None:
    """Entry point — sets up the event loop with signal handlers."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    task = loop.create_task(run_worker())

    # Register signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_shutdown, loop, task)
        except NotImplementedError:
            # Windows does not support add_signal_handler
            pass

    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        logger.info("Worker cancelled — exiting")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
