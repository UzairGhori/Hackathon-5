"""Customer Success AI Agent — built on OpenAI Agent SDK.

This module defines the agent and provides a `run_agent()` function
that the Kafka worker calls for each incoming message.
"""

import time
import uuid

from agents import Agent, Runner
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import AgentContext
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import ALL_TOOLS
from app.core.logging import get_logger
from app.db.models import AgentMetric, ChannelType
from app.services.customer_service import CustomerService
from app.services.conversation_service import ConversationService

logger = get_logger(__name__)

# ── Agent Definition ─────────────────────────────────────────

support_agent = Agent(
    name="Customer Success Agent",
    instructions=SYSTEM_PROMPT,
    tools=ALL_TOOLS,
    model="gpt-4o",
)

# ── Runner ───────────────────────────────────────────────────


async def run_agent(
    session: AsyncSession,
    customer_id: uuid.UUID,
    conversation_id: uuid.UUID,
    channel: ChannelType,
    customer_message: str,
) -> str:
    """Execute the agent for a single customer message.

    Args:
        session: Active async DB session.
        customer_id: UUID of the customer.
        conversation_id: UUID of the conversation.
        channel: The channel the message arrived on.
        customer_message: The raw customer message text.

    Returns:
        The agent's response text.
    """
    # Build context for tool calls
    cust_service = CustomerService(session)
    customer_identifier = await cust_service.get_identifier(customer_id, channel) or ""

    # Fetch latest message for metadata (threading support)
    conv_service = ConversationService(session)
    latest_msg = await conv_service.get_latest_message(conversation_id)
    metadata = {}
    if latest_msg and channel == ChannelType.GMAIL:
        msg_metadata = latest_msg.metadata_ or {}
        headers = msg_metadata.get("headers", {})
        metadata["gmail_message_id"] = latest_msg.channel_message_id
        # Build references
        prev_refs = headers.get("References", "")
        metadata["gmail_references"] = f"{prev_refs} {latest_msg.channel_message_id}".strip()
        metadata["subject"] = headers.get("Subject", "Re: Customer Support")
        if metadata["subject"] and not metadata["subject"].startswith("Re:"):
            metadata["subject"] = f"Re: {metadata['subject']}"

    context = AgentContext(
        session=session,
        customer_id=customer_id,
        conversation_id=conversation_id,
        channel=channel,
        customer_identifier=customer_identifier,
        metadata=metadata,
    )

    start_time = time.perf_counter()

    logger.info(
        "Running agent for conversation=%s customer=%s channel=%s",
        conversation_id, customer_id, channel.value,
    )

    result = await Runner.run(
        starting_agent=support_agent,
        input=customer_message,
        context=context,
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # Extract token usage from result
    tokens_in = 0
    tokens_out = 0
    if result.raw_responses:
        for raw in result.raw_responses:
            usage = getattr(raw, "usage", None)
            if usage:
                tokens_in += getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0)
                tokens_out += getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0)

    # Record metrics — persist tool_trace in metadata for UI visibility
    metric = AgentMetric(
        conversation_id=conversation_id,
        ticket_id=context.ticket_id,
        channel=channel,
        response_time_ms=elapsed_ms,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        model_used="gpt-4o",
        resolved_by_ai=not context.escalated,
        escalated=context.escalated,
        metadata_={"tool_trace": context.tool_trace},
    )
    session.add(metric)
    await session.flush()

    # The response text was set by the send_response tool
    response_text = context.response_text or result.final_output

    logger.info(
        "Agent completed: conversation=%s elapsed=%dms tokens_in=%d tokens_out=%d escalated=%s",
        conversation_id, elapsed_ms, tokens_in, tokens_out, context.escalated,
    )

    return response_text
