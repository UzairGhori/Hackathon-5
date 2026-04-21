"""Agent tools — functions the AI agent can call during a conversation.

Each tool receives the RunContextWrapper[AgentContext] as its first argument,
giving it access to the DB session, customer/conversation IDs, and channel.
"""

import time

from sqlalchemy import select
from agents import function_tool, RunContextWrapper

from app.agent.context import AgentContext
from app.core.logging import get_logger
from app.db.models import (
    Conversation,
    Customer,
    KnowledgeBase,
    Message,
    MessageDirection,
    MessageSender,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.services.ticket_service import TicketService

logger = get_logger(__name__)


def _trace(ctx: RunContextWrapper[AgentContext], tool: str, args: dict) -> None:
    """Append a tool invocation to the context's tool_trace list.

    Emits a visible [AGENT-TOOL] log marker for demo-friendly terminal output.
    The timestamp is a millisecond walltime captured when the tool was entered;
    the UI converts these into a pill-row of tools fired in order.
    """
    entry = {
        "tool": tool,
        "args": args,
        "ts_ms": int(time.time() * 1000),
    }
    ctx.context.tool_trace.append(entry)
    logger.info("[AGENT-TOOL] %s args=%s", tool, args)


# ── Tool 1: Search Knowledge Base ────────────────────────────

@function_tool
async def search_knowledge_base(
    ctx: RunContextWrapper[AgentContext],
    query: str,
) -> str:
    """Search the knowledge base for articles relevant to the customer's question.

    Args:
        query: The search query derived from the customer's message.

    Returns:
        Matching knowledge base articles as formatted text.
    """
    _trace(ctx, "search_knowledge_base", {"query": query})
    session = ctx.context.session

    stmt = (
        select(KnowledgeBase)
        .where(
            KnowledgeBase.is_active.is_(True),
            KnowledgeBase.content.ilike(f"%{query}%")
            | KnowledgeBase.title.ilike(f"%{query}%"),
        )
        .limit(5)
    )
    result = await session.execute(stmt)
    articles = result.scalars().all()

    if not articles:
        logger.info("Knowledge base search for '%s' returned no results", query)
        return "No relevant articles found in the knowledge base."

    formatted = []
    for article in articles:
        formatted.append(
            f"**{article.title}**\n"
            f"Category: {article.category or 'General'}\n"
            f"{article.content}\n"
        )

    logger.info("Knowledge base search for '%s' returned %d articles", query, len(articles))
    return "\n---\n".join(formatted)


# ── Tool 2: Get Customer History ─────────────────────────────

@function_tool
async def get_customer_history(
    ctx: RunContextWrapper[AgentContext],
) -> str:
    """Retrieve the customer's recent conversation history and past tickets.

    Returns:
        Summary of past conversations and tickets for this customer.
    """
    _trace(ctx, "get_customer_history", {})
    session = ctx.context.session
    customer_id = ctx.context.customer_id

    customer = (
        await session.execute(
            select(Customer).where(Customer.id == customer_id)
        )
    ).scalar_one_or_none()

    if not customer:
        return "Customer not found."

    convos = (
        await session.execute(
            select(Conversation)
            .where(Conversation.customer_id == customer_id)
            .order_by(Conversation.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    tickets = (
        await session.execute(
            select(Ticket)
            .where(Ticket.customer_id == customer_id)
            .order_by(Ticket.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    messages = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == ctx.context.conversation_id)
            .order_by(Message.created_at.asc())
        )
    ).scalars().all()

    parts = [
        f"Customer: {customer.full_name}",
        f"Company: {customer.company or 'N/A'}",
        f"Total conversations: {len(convos)}",
    ]

    if tickets:
        parts.append("\nRecent tickets:")
        for t in tickets:
            parts.append(f"  - [{t.status.value}] {t.subject} (priority: {t.priority.value})")

    if messages:
        parts.append(f"\nCurrent conversation ({len(messages)} messages):")
        for m in messages:
            sender_label = "Customer" if m.sender == MessageSender.CUSTOMER else "Agent"
            parts.append(f"  [{sender_label}]: {m.content[:200]}")

    logger.info("Retrieved history for customer %s", customer_id)
    return "\n".join(parts)


# ── Tool 3: Create Ticket ────────────────────────────────────

@function_tool
async def create_ticket(
    ctx: RunContextWrapper[AgentContext],
    subject: str,
    description: str,
    priority: str = "medium",
) -> str:
    """Create a support ticket for the current conversation.

    Args:
        subject: Brief summary of the issue.
        description: Detailed description of the problem.
        priority: Ticket priority — low, medium, high, or critical.

    Returns:
        Confirmation with the ticket ID.
    """
    _trace(ctx, "create_ticket", {"subject": subject, "priority": priority})
    priority_map = {
        "low": TicketPriority.LOW,
        "medium": TicketPriority.MEDIUM,
        "high": TicketPriority.HIGH,
        "critical": TicketPriority.CRITICAL,
    }
    ticket_priority = priority_map.get(priority.lower(), TicketPriority.MEDIUM)

    ticket_svc = TicketService(ctx.context.session)
    ticket = await ticket_svc.create_ticket(
        conversation_id=ctx.context.conversation_id,
        customer_id=ctx.context.customer_id,
        channel=ctx.context.channel,
        subject=subject,
        description=description,
        priority=ticket_priority,
    )

    ctx.context.ticket_id = ticket.id

    logger.info("Created ticket %s for conversation %s", ticket.id, ctx.context.conversation_id)
    return f"Ticket created successfully. Ticket ID: {ticket.id}"


# ── Tool 4: Escalate to Human ────────────────────────────────

@function_tool
async def escalate_to_human(
    ctx: RunContextWrapper[AgentContext],
    reason: str,
    category: str = "low_confidence",
) -> str:
    """Escalate the current conversation to a human agent.

    MUST call create_ticket before this tool so a ticket exists to escalate.

    Use this when any escalation rule is triggered:
    - refund_request: Customer wants a refund or money back.
    - pricing_question: Customer asks about pricing, discounts, or plans.
    - legal_issue: Customer mentions legal action, lawyers, or regulations.
    - angry_customer: Customer is very frustrated, using profanity or threats.
    - low_confidence: AI cannot find a confident answer in the knowledge base.
    - customer_requested_human: Customer explicitly asks for a human.
    - complex_technical: Issue is too complex for AI resolution.
    - billing_dispute: Customer disputes a charge on their account.
    - account_deletion: Customer requests their account be deleted.
    - security_concern: Customer reports unauthorized access or breach.

    Args:
        reason: Clear explanation of why escalation is needed.
        category: The escalation category from the list above.

    Returns:
        Confirmation of the escalation.
    """
    _trace(ctx, "escalate_to_human", {"category": category, "reason": reason[:120]})
    ticket_svc = TicketService(ctx.context.session)

    # If no ticket exists yet, create one automatically
    if not ctx.context.ticket_id:
        ticket = await ticket_svc.create_ticket(
            conversation_id=ctx.context.conversation_id,
            customer_id=ctx.context.customer_id,
            channel=ctx.context.channel,
            subject=f"Escalated: {category}",
            description=reason,
            priority=TicketPriority.HIGH,
        )
        ctx.context.ticket_id = ticket.id

    # Escalate with category and auto-priority
    ticket = await ticket_svc.escalate(
        ticket_id=ctx.context.ticket_id,
        reason=reason,
        category=category,
    )

    ctx.context.escalated = True

    logger.info(
        "Escalated conversation %s [category=%s priority=%s]: %s",
        ctx.context.conversation_id, category, ticket.priority.value, reason,
    )
    return (
        f"Conversation escalated to a human agent.\n"
        f"Category: {category}\n"
        f"Priority: {ticket.priority.value}\n"
        f"Reason: {reason}"
    )


# ── Tool 5: Send Response ────────────────────────────────────

@function_tool
async def send_response(
    ctx: RunContextWrapper[AgentContext],
    message: str,
) -> str:
    """Send a response message back to the customer.

    This stores the outbound message in the database and marks it
    for delivery through the appropriate channel.

    Args:
        message: The response text to send to the customer.

    Returns:
        Confirmation that the message was sent.
    """
    _trace(ctx, "send_response", {"length": len(message)})
    session = ctx.context.session

    outbound = Message(
        conversation_id=ctx.context.conversation_id,
        direction=MessageDirection.OUTBOUND,
        sender=MessageSender.AGENT,
        content=message,
        channel=ctx.context.channel,
        metadata_={"sent_by": "ai_agent"},
    )
    session.add(outbound)
    await session.flush()

    ctx.context.response_text = message

    logger.info(
        "Agent response stored for conversation %s (%d chars)",
        ctx.context.conversation_id, len(message),
    )
    return f"Response sent to customer: {message[:100]}..."


# ── Tool registry ────────────────────────────────────────────

ALL_TOOLS = [
    search_knowledge_base,
    get_customer_history,
    create_ticket,
    escalate_to_human,
    send_response,
]
