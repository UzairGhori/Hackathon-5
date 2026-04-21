"""Demo API — synchronous processing endpoint for live demonstrations.

Bypasses Kafka to provide instant end-to-end flow visibility:
  Form → Intake → AI Agent → Ticket → Response

Works in two modes:
  - Real mode: OPENAI_API_KEY set → uses actual AI agent (gpt-4o)
  - Demo mode: No API key → intelligent mock that simulates agent decisions
"""

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.db.database import get_session
from app.db.models import (
    ChannelType,
    Conversation,
    Customer,
    CustomerIdentifier,
    KnowledgeBase,
    Message,
    MessageDirection,
    MessageSender,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketEvent,
    TicketEventType,
    AgentMetric,
)

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


# ── Request / Response Schemas ───────────────────────────────

class DemoMessageRequest(BaseModel):
    name: str
    email: EmailStr
    company: str = ""
    subject: str
    message: str


class ToolTraceEntry(BaseModel):
    tool: str
    args: dict
    ts_ms: int


class TicketInfo(BaseModel):
    id: str
    subject: str
    status: str
    priority: str
    escalated: bool
    escalation_reason: str | None = None


class DemoMessageResponse(BaseModel):
    # Pipeline metadata
    pipeline_stages: list[str]
    processing_time_ms: int

    # Customer & conversation
    customer_id: str
    conversation_id: str
    message_id: str
    is_new_customer: bool

    # AI Agent result
    ai_response: str
    tool_trace: list[ToolTraceEntry]
    model_used: str
    tokens_input: int
    tokens_output: int

    # Ticket
    ticket: TicketInfo | None = None

    # Escalation
    escalated: bool
    escalation_category: str | None = None


class DBStatsResponse(BaseModel):
    total_customers: int
    total_conversations: int
    total_messages: int
    total_tickets: int
    tickets_by_status: dict[str, int]
    tickets_by_priority: dict[str, int]
    escalated_tickets: int
    ai_resolved: int
    avg_response_time_ms: float | None
    recent_messages: list[dict]


class SeedResponse(BaseModel):
    message: str
    kb_articles_created: int
    sample_customers_created: int


# ── Helper: Intelligent Mock Agent ──────────────────────────

ESCALATION_KEYWORDS = {
    "refund": ("refund_request", "high"),
    "money back": ("refund_request", "high"),
    "pricing": ("pricing_question", "medium"),
    "price": ("pricing_question", "medium"),
    "lawyer": ("legal_issue", "critical"),
    "legal": ("legal_issue", "critical"),
    "sue": ("legal_issue", "critical"),
    "angry": ("angry_customer", "high"),
    "frustrated": ("angry_customer", "high"),
    "terrible": ("angry_customer", "high"),
    "worst": ("angry_customer", "high"),
    "human": ("customer_requested_human", "high"),
    "real person": ("customer_requested_human", "high"),
    "speak to someone": ("customer_requested_human", "high"),
    "billing": ("billing_dispute", "high"),
    "charged": ("billing_dispute", "high"),
    "delete my account": ("account_deletion", "critical"),
    "delete account": ("account_deletion", "critical"),
    "hacked": ("security_concern", "critical"),
    "unauthorized": ("security_concern", "critical"),
    "breach": ("security_concern", "critical"),
}


def _detect_escalation(message: str) -> tuple[str, str] | None:
    """Check if message triggers an escalation rule."""
    lower = message.lower()
    for keyword, (category, priority) in ESCALATION_KEYWORDS.items():
        if keyword in lower:
            return category, priority
    return None


async def _mock_agent_process(
    session: AsyncSession,
    customer_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_content: str,
) -> dict:
    """Simulate AI agent processing with realistic tool traces and decisions."""
    start_time = time.perf_counter()
    tool_trace = []
    now_ms = int(time.time() * 1000)

    # Step 1: Search knowledge base
    tool_trace.append({
        "tool": "search_knowledge_base",
        "args": {"query": message_content[:80]},
        "ts_ms": now_ms,
    })

    # Check KB for relevant articles
    kb_result = await session.execute(
        select(KnowledgeBase)
        .where(
            KnowledgeBase.is_active.is_(True),
            KnowledgeBase.content.ilike(f"%{message_content.split()[0]}%")
            | KnowledgeBase.title.ilike(f"%{message_content.split()[0]}%"),
        )
        .limit(3)
    )
    kb_articles = kb_result.scalars().all()

    # Step 2: Get customer history
    tool_trace.append({
        "tool": "get_customer_history",
        "args": {},
        "ts_ms": now_ms + 150,
    })

    # Step 3: Decide - escalate or resolve
    escalation = _detect_escalation(message_content)
    ticket = None
    escalated = False
    escalation_category = None

    if escalation:
        category, priority = escalation
        escalation_category = category
        escalated = True

        # Create ticket
        priority_map = {
            "low": TicketPriority.LOW,
            "medium": TicketPriority.MEDIUM,
            "high": TicketPriority.HIGH,
            "critical": TicketPriority.CRITICAL,
        }
        ticket = Ticket(
            conversation_id=conversation_id,
            customer_id=customer_id,
            channel=ChannelType.WEB,
            subject=f"Escalated: {category.replace('_', ' ').title()}",
            description=f"Customer message: {message_content[:200]}",
            status=TicketStatus.ESCALATED,
            priority=priority_map.get(priority, TicketPriority.HIGH),
            tags=[category],
        )
        session.add(ticket)
        await session.flush()

        # Ticket event
        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=TicketEventType.ESCALATED,
            actor="ai_agent",
            new_value={"category": category, "reason": message_content[:200]},
            note=f"Auto-escalated by AI: {category}",
        )
        session.add(event)

        tool_trace.append({
            "tool": "create_ticket",
            "args": {"subject": ticket.subject, "priority": priority},
            "ts_ms": now_ms + 300,
        })
        tool_trace.append({
            "tool": "escalate_to_human",
            "args": {"category": category, "reason": f"Customer message triggers {category} rule"},
            "ts_ms": now_ms + 450,
        })

        # Generate escalation response
        response_text = (
            f"I understand your concern regarding {category.replace('_', ' ')}. "
            f"I've created a priority ticket and escalated this to our specialist team. "
            f"A human agent will review your case shortly. "
            f"Your ticket ID is {ticket.id}. "
            f"We take these matters seriously and will respond within the hour."
        )
    else:
        # AI resolves directly
        if kb_articles:
            kb_info = kb_articles[0].content[:200]
            response_text = (
                f"Thank you for reaching out! Based on our knowledge base, "
                f"here's what I found:\n\n{kb_info}\n\n"
                f"Is there anything else I can help you with?"
            )
        else:
            response_text = (
                f"Thank you for contacting us! I've reviewed your message about "
                f"'{message_content[:50]}'. "
                f"I'd be happy to help you with this. "
                f"Our team has been notified and I've created a ticket to track this request. "
                f"You can expect a detailed response shortly."
            )

        # Create a standard ticket for tracking
        ticket = Ticket(
            conversation_id=conversation_id,
            customer_id=customer_id,
            channel=ChannelType.WEB,
            subject=message_content[:100],
            description=message_content,
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.MEDIUM,
        )
        session.add(ticket)
        await session.flush()

        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=TicketEventType.CREATED,
            actor="ai_agent",
            note="Ticket created by AI agent",
        )
        session.add(event)

        tool_trace.append({
            "tool": "create_ticket",
            "args": {"subject": message_content[:60], "priority": "medium"},
            "ts_ms": now_ms + 300,
        })

    # Step 4: Send response
    tool_trace.append({
        "tool": "send_response",
        "args": {"length": len(response_text)},
        "ts_ms": now_ms + 500,
    })

    # Store outbound message
    outbound = Message(
        conversation_id=conversation_id,
        direction=MessageDirection.OUTBOUND,
        sender=MessageSender.AGENT,
        content=response_text,
        channel=ChannelType.WEB,
        metadata_={"sent_by": "ai_agent", "mode": "demo"},
    )
    session.add(outbound)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # Record metric
    metric = AgentMetric(
        conversation_id=conversation_id,
        ticket_id=ticket.id if ticket else None,
        channel=ChannelType.WEB,
        response_time_ms=elapsed_ms,
        tokens_input=385,
        tokens_output=142,
        model_used="gpt-4o (demo-mock)",
        resolved_by_ai=not escalated,
        escalated=escalated,
        metadata_={"tool_trace": tool_trace, "mode": "demo"},
    )
    session.add(metric)
    await session.flush()

    return {
        "response_text": response_text,
        "tool_trace": tool_trace,
        "ticket": ticket,
        "escalated": escalated,
        "escalation_category": escalation_category,
        "elapsed_ms": elapsed_ms,
        "tokens_input": 385,
        "tokens_output": 142,
        "model_used": "gpt-4o (demo-mock)",
    }


# ── Main Demo Endpoint ──────────────────────────────────────

@router.post("/process", response_model=DemoMessageResponse)
async def demo_process_message(
    payload: DemoMessageRequest,
    session: AsyncSession = Depends(get_session),
):
    """Process a customer message end-to-end synchronously for demo purposes.

    Pipeline: Intake → DB → AI Agent → Ticket → Response
    """
    start_time = time.perf_counter()
    pipeline_stages = []

    # ── Stage 1: Customer Resolution ──
    pipeline_stages.append("customer_resolution")
    customer = (
        await session.execute(
            select(Customer)
            .join(CustomerIdentifier)
            .where(
                CustomerIdentifier.channel == ChannelType.WEB,
                CustomerIdentifier.identifier == payload.email,
            )
        )
    ).scalar_one_or_none()

    is_new_customer = False
    if not customer:
        is_new_customer = True
        customer = Customer(
            full_name=payload.name,
            company=payload.company or None,
            metadata_={"source": "web_form"},
        )
        session.add(customer)
        await session.flush()

        identifier = CustomerIdentifier(
            customer_id=customer.id,
            channel=ChannelType.WEB,
            identifier=payload.email,
        )
        session.add(identifier)
        await session.flush()

    # ── Stage 2: Conversation Creation ──
    pipeline_stages.append("conversation_created")
    conversation = Conversation(
        customer_id=customer.id,
        channel=ChannelType.WEB,
        subject=payload.subject,
        status="active",
    )
    session.add(conversation)
    await session.flush()

    # ── Stage 3: Message Storage ──
    pipeline_stages.append("message_stored")
    message = Message(
        conversation_id=conversation.id,
        direction=MessageDirection.INBOUND,
        sender=MessageSender.CUSTOMER,
        content=payload.message,
        channel=ChannelType.WEB,
        metadata_={"subject": payload.subject, "from_name": payload.name},
    )
    session.add(message)
    await session.flush()

    # ── Stage 4: Kafka Queue (simulated for demo) ──
    pipeline_stages.append("kafka_queued")

    # ── Stage 5: AI Agent Processing ──
    pipeline_stages.append("agent_processing")

    _placeholder_keys = {"", "sk-demo-key", "sk-your-key-here", "your-key-here"}
    use_real_agent = bool(
        settings.openai_api_key
        and settings.openai_api_key not in _placeholder_keys
        and not settings.openai_api_key.startswith("sk-your")
    )

    if use_real_agent:
        try:
            from app.agent.agent import run_agent
            response_text = await run_agent(
                session=session,
                customer_id=customer.id,
                conversation_id=conversation.id,
                channel=ChannelType.WEB,
                customer_message=payload.message,
            )
            # Get the metric we just recorded
            metric = (
                await session.execute(
                    select(AgentMetric)
                    .where(AgentMetric.conversation_id == conversation.id)
                    .order_by(AgentMetric.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            tool_trace = (metric.metadata_ or {}).get("tool_trace", []) if metric else []
            ticket = (
                await session.execute(
                    select(Ticket).where(Ticket.conversation_id == conversation.id).limit(1)
                )
            ).scalar_one_or_none()

            agent_result = {
                "response_text": response_text,
                "tool_trace": tool_trace,
                "ticket": ticket,
                "escalated": metric.escalated if metric else False,
                "escalation_category": None,
                "elapsed_ms": metric.response_time_ms if metric else 0,
                "tokens_input": metric.tokens_input if metric else 0,
                "tokens_output": metric.tokens_output if metric else 0,
                "model_used": "gpt-4o",
            }
        except Exception as e:
            logger.warning("Real agent failed, falling back to mock: %s", e)
            agent_result = await _mock_agent_process(
                session, customer.id, conversation.id, payload.message
            )
    else:
        agent_result = await _mock_agent_process(
            session, customer.id, conversation.id, payload.message
        )

    pipeline_stages.append("response_generated")

    total_time = int((time.perf_counter() - start_time) * 1000)

    # Build ticket info
    ticket_info = None
    if agent_result["ticket"]:
        t = agent_result["ticket"]
        ticket_info = TicketInfo(
            id=str(t.id),
            subject=t.subject,
            status=t.status.value,
            priority=t.priority.value,
            escalated=agent_result["escalated"],
            escalation_reason=agent_result.get("escalation_category"),
        )

    return DemoMessageResponse(
        pipeline_stages=pipeline_stages,
        processing_time_ms=total_time,
        customer_id=str(customer.id),
        conversation_id=str(conversation.id),
        message_id=str(message.id),
        is_new_customer=is_new_customer,
        ai_response=agent_result["response_text"],
        tool_trace=[ToolTraceEntry(**t) for t in agent_result["tool_trace"]],
        model_used=agent_result["model_used"],
        tokens_input=agent_result["tokens_input"],
        tokens_output=agent_result["tokens_output"],
        ticket=ticket_info,
        escalated=agent_result["escalated"],
        escalation_category=agent_result.get("escalation_category"),
    )


# ── DB Stats Endpoint ────────────────────────────────────────

@router.get("/stats", response_model=DBStatsResponse)
async def get_demo_stats(session: AsyncSession = Depends(get_session)):
    """Get current database statistics for the demo dashboard."""
    total_customers = (await session.execute(select(func.count(Customer.id)))).scalar() or 0
    total_conversations = (await session.execute(select(func.count(Conversation.id)))).scalar() or 0
    total_messages = (await session.execute(select(func.count(Message.id)))).scalar() or 0
    total_tickets = (await session.execute(select(func.count(Ticket.id)))).scalar() or 0

    # Tickets by status
    status_result = await session.execute(
        select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
    )
    tickets_by_status = {row[0].value: row[1] for row in status_result.all()}

    # Tickets by priority
    priority_result = await session.execute(
        select(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority)
    )
    tickets_by_priority = {row[0].value: row[1] for row in priority_result.all()}

    # Escalated
    escalated = (
        await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.ESCALATED)
        )
    ).scalar() or 0

    # AI resolved
    ai_resolved = (
        await session.execute(
            select(func.count(AgentMetric.id)).where(AgentMetric.resolved_by_ai.is_(True))
        )
    ).scalar() or 0

    # Avg response time
    avg_time = (
        await session.execute(select(func.avg(AgentMetric.response_time_ms)))
    ).scalar()

    # Recent messages
    recent = (
        await session.execute(
            select(Message)
            .order_by(Message.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    recent_messages = [
        {
            "id": str(m.id),
            "direction": m.direction.value,
            "sender": m.sender.value,
            "content": m.content[:150],
            "channel": m.channel.value,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in recent
    ]

    return DBStatsResponse(
        total_customers=total_customers,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_tickets=total_tickets,
        tickets_by_status=tickets_by_status,
        tickets_by_priority=tickets_by_priority,
        escalated_tickets=escalated,
        ai_resolved=ai_resolved,
        avg_response_time_ms=float(avg_time) if avg_time else None,
        recent_messages=recent_messages,
    )


# ── Seed Data Endpoint ───────────────────────────────────────

@router.post("/seed", response_model=SeedResponse)
async def seed_demo_data(session: AsyncSession = Depends(get_session)):
    """Seed the database with knowledge base articles and sample data."""

    # Knowledge base articles
    kb_articles = [
        {
            "title": "Password Reset Guide",
            "category": "Account",
            "content": (
                "To reset your password: 1) Go to login page 2) Click 'Forgot Password' "
                "3) Enter your email 4) Check inbox for reset link 5) Create new password "
                "(min 8 chars, 1 uppercase, 1 number). Link expires in 24 hours."
            ),
        },
        {
            "title": "Refund Policy",
            "category": "Billing",
            "content": (
                "Refunds are processed within 5-7 business days. Eligible for refund: "
                "subscription cancellation within 30 days, duplicate charges, service "
                "outage > 4 hours. Contact billing team for refunds over $500. "
                "All refund requests require a support ticket."
            ),
        },
        {
            "title": "Pricing Plans",
            "category": "Billing",
            "content": (
                "Starter: $29/mo (5 users, 1000 messages). Professional: $99/mo "
                "(25 users, 10K messages, priority support). Enterprise: Custom pricing "
                "(unlimited users, SLA guarantee, dedicated account manager). "
                "Annual plans get 20% discount."
            ),
        },
        {
            "title": "API Integration Guide",
            "category": "Technical",
            "content": (
                "Our REST API supports JSON. Auth via Bearer token in headers. "
                "Rate limit: 100 req/min (Starter), 1000 req/min (Pro), unlimited (Enterprise). "
                "Webhooks available for real-time events. SDK available for Python, Node.js, Java."
            ),
        },
        {
            "title": "Data Export & Account Deletion",
            "category": "Account",
            "content": (
                "To export your data: Settings → Privacy → Export Data (CSV/JSON). "
                "Processing takes 24-48h. For account deletion: submit request via support ticket. "
                "All data permanently deleted within 30 days per GDPR compliance. "
                "Cannot be undone once processing begins."
            ),
        },
        {
            "title": "Service Level Agreement (SLA)",
            "category": "General",
            "content": (
                "Uptime guarantee: 99.9% (Starter/Pro), 99.99% (Enterprise). "
                "Support response times: 24h (Starter), 4h (Pro), 1h (Enterprise). "
                "Compensation: service credits for SLA violations. "
                "Maintenance windows: Sundays 2-4 AM UTC (announced 48h ahead)."
            ),
        },
        {
            "title": "Two-Factor Authentication Setup",
            "category": "Security",
            "content": (
                "Enable 2FA: Settings → Security → Enable 2FA. Supports: "
                "Authenticator apps (Google Auth, Authy), SMS codes, hardware keys (YubiKey). "
                "Backup codes provided (store safely). Required for admin accounts. "
                "Lost 2FA? Contact support with identity verification."
            ),
        },
        {
            "title": "Billing & Invoice FAQ",
            "category": "Billing",
            "content": (
                "Invoices generated on 1st of each month. Payment methods: credit card, "
                "ACH, wire transfer (Enterprise only). Failed payments retried 3x over 7 days. "
                "Tax certificates available under Settings → Billing → Tax Documents. "
                "Proration applied for mid-cycle plan changes."
            ),
        },
    ]

    created_articles = 0
    for article_data in kb_articles:
        existing = (
            await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.title == article_data["title"])
            )
        ).scalar_one_or_none()

        if not existing:
            article = KnowledgeBase(
                title=article_data["title"],
                category=article_data["category"],
                content=article_data["content"],
                is_active=True,
            )
            session.add(article)
            created_articles += 1

    # Sample customers
    sample_customers = [
        {"name": "Ahmed Hassan", "email": "ahmed@techcorp.pk", "company": "TechCorp Pakistan"},
        {"name": "Sarah Khan", "email": "sarah@startup.io", "company": "StartupIO"},
        {"name": "Ali Raza", "email": "ali.raza@enterprise.com", "company": "Enterprise Solutions"},
    ]

    created_customers = 0
    for cust_data in sample_customers:
        existing = (
            await session.execute(
                select(CustomerIdentifier).where(
                    CustomerIdentifier.identifier == cust_data["email"],
                    CustomerIdentifier.channel == ChannelType.WEB,
                )
            )
        ).scalar_one_or_none()

        if not existing:
            customer = Customer(
                full_name=cust_data["name"],
                company=cust_data["company"],
                metadata_={"source": "seed_data"},
            )
            session.add(customer)
            await session.flush()

            ident = CustomerIdentifier(
                customer_id=customer.id,
                channel=ChannelType.WEB,
                identifier=cust_data["email"],
            )
            session.add(ident)
            created_customers += 1

    await session.flush()

    return SeedResponse(
        message="Demo data seeded successfully!",
        kb_articles_created=created_articles,
        sample_customers_created=created_customers,
    )
