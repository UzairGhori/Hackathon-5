"""Service-layer unit tests.

Exercises the three core services directly against FakeSession:

  CustomerService.find_or_create
  ConversationService.find_or_create
  ConversationService.add_message
  TicketService.create_ticket
  TicketService.transition_status   (+ invalid transition guard)
  TicketService.escalate             (+ priority bump + tag + conversation flip)
  TicketService.assign               (+ escalated → in_progress auto-flip)
  TicketService.resolve / close      (timestamps set)
  TicketService._escalation_priority (helper correctness)

Services call `session.execute` + `session.add` + `session.flush`, all of
which FakeSession supports. No Postgres required.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.db.models import (
    ChannelType,
    MessageDirection,
    MessageSender,
    TicketPriority,
    TicketStatus,
)


pytestmark = pytest.mark.asyncio


# ══════════════════════════════════════════════════════════════
# CustomerService
# ══════════════════════════════════════════════════════════════


async def test_customer_find_or_create_returns_existing(db_session):
    """Existing CustomerIdentifier → load Customer, is_new=False."""
    from app.services.customer_service import CustomerService

    existing_customer_id = uuid.uuid4()
    ci = SimpleNamespace(customer_id=existing_customer_id)
    customer = SimpleNamespace(id=existing_customer_id, full_name="Alice")

    # First execute() returns the CustomerIdentifier row
    # Second execute() loads the Customer
    db_session.queue_many([ci, customer])

    svc = CustomerService(db_session)
    result, is_new = await svc.find_or_create(
        channel=ChannelType.WEB,
        identifier="alice@example.com",
        full_name="Alice",
    )

    assert is_new is False
    assert result.id == existing_customer_id
    assert db_session.execute_calls == 2
    assert db_session.added == []  # no inserts


async def test_customer_find_or_create_creates_new(db_session):
    """No match → insert Customer + CustomerIdentifier, is_new=True."""
    from app.services.customer_service import CustomerService
    from app.db.models import Customer, CustomerIdentifier

    # First execute() returns None (no identifier found)
    db_session.queue_many([None])

    svc = CustomerService(db_session)
    customer, is_new = await svc.find_or_create(
        channel=ChannelType.GMAIL,
        identifier="bob@example.com",
        full_name="Bob Builder",
        company="Acme",
    )

    assert is_new is True
    assert customer.full_name == "Bob Builder"
    assert customer.company == "Acme"

    inserted_customers = [o for o in db_session.added if isinstance(o, Customer)]
    inserted_cis = [o for o in db_session.added if isinstance(o, CustomerIdentifier)]
    assert len(inserted_customers) == 1
    assert len(inserted_cis) == 1
    assert inserted_cis[0].channel == ChannelType.GMAIL
    assert inserted_cis[0].identifier == "bob@example.com"
    assert inserted_cis[0].is_primary is True


# ══════════════════════════════════════════════════════════════
# ConversationService
# ══════════════════════════════════════════════════════════════


async def test_conversation_find_or_create_returns_active(db_session):
    from app.services.conversation_service import ConversationService

    existing = SimpleNamespace(id=uuid.uuid4())
    db_session.queue(existing)

    svc = ConversationService(db_session)
    convo, is_new = await svc.find_or_create(
        customer_id=uuid.uuid4(),
        channel=ChannelType.WHATSAPP,
        subject="ignored when reusing",
    )
    assert is_new is False
    assert convo.id == existing.id
    assert db_session.added == []


async def test_conversation_find_or_create_creates_new(db_session):
    from app.services.conversation_service import ConversationService
    from app.db.models import Conversation

    db_session.queue(None)  # no active conversation

    svc = ConversationService(db_session)
    customer_id = uuid.uuid4()
    convo, is_new = await svc.find_or_create(
        customer_id=customer_id,
        channel=ChannelType.WEB,
        subject="First contact",
    )
    assert is_new is True
    inserted = [o for o in db_session.added if isinstance(o, Conversation)]
    assert len(inserted) == 1
    assert inserted[0].customer_id == customer_id
    assert inserted[0].channel == ChannelType.WEB
    assert inserted[0].subject == "First contact"


async def test_conversation_add_message_inbound_default(db_session):
    from app.services.conversation_service import ConversationService
    from app.db.models import Message

    svc = ConversationService(db_session)
    message = await svc.add_message(
        conversation_id=uuid.uuid4(),
        channel=ChannelType.GMAIL,
        content="Hello, I have a question.",
        channel_message_id="gmail-42",
        metadata={"thread_id": "t-1"},
    )

    assert isinstance(message, Message)
    assert message.direction == MessageDirection.INBOUND
    assert message.sender == MessageSender.CUSTOMER
    assert message.channel_message_id == "gmail-42"
    assert message.metadata_ == {"thread_id": "t-1"}
    assert db_session.added[-1] is message


async def test_conversation_add_message_outbound_override(db_session):
    from app.services.conversation_service import ConversationService

    svc = ConversationService(db_session)
    message = await svc.add_message(
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        content="Thanks for reaching out.",
        direction=MessageDirection.OUTBOUND,
        sender=MessageSender.AGENT,
    )
    assert message.direction == MessageDirection.OUTBOUND
    assert message.sender == MessageSender.AGENT


# ══════════════════════════════════════════════════════════════
# TicketService
# ══════════════════════════════════════════════════════════════


async def test_ticket_create_adds_ticket_and_event(db_session):
    from app.services.ticket_service import TicketService
    from app.db.models import Ticket, TicketEvent, TicketEventType

    svc = TicketService(db_session)
    ticket = await svc.create_ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="Login broken",
        description="Cannot sign in after reset",
        priority=TicketPriority.HIGH,
    )

    assert ticket.status == TicketStatus.OPEN
    assert ticket.priority == TicketPriority.HIGH
    assert ticket.assigned_to == "ai_agent"

    tickets_added = [o for o in db_session.added if isinstance(o, Ticket)]
    events_added = [o for o in db_session.added if isinstance(o, TicketEvent)]
    assert len(tickets_added) == 1
    assert len(events_added) == 1
    assert events_added[0].event_type == TicketEventType.CREATED
    assert events_added[0].new_value["priority"] == "high"


async def test_ticket_transition_status_valid(db_session):
    from app.services.ticket_service import TicketService
    from app.db.models import Ticket, TicketEvent, TicketEventType

    ticket = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="x",
        description="y",
    )
    ticket.status = TicketStatus.OPEN
    db_session.queue(ticket)

    svc = TicketService(db_session)
    result = await svc.transition_status(
        ticket_id=ticket.id,
        new_status=TicketStatus.IN_PROGRESS,
        actor="agent@co",
        note="picking up",
    )
    assert result.status == TicketStatus.IN_PROGRESS

    events = [o for o in db_session.added if isinstance(o, TicketEvent)]
    assert len(events) == 1
    assert events[0].event_type == TicketEventType.STATUS_CHANGED
    assert events[0].note == "picking up"
    assert events[0].old_value == {"status": "open"}
    assert events[0].new_value == {"status": "in_progress"}


async def test_ticket_transition_status_invalid_raises(db_session):
    """closed → in_progress is not a valid transition."""
    from app.services.ticket_service import TicketService
    from app.db.models import Ticket

    ticket = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="x",
        description="y",
    )
    ticket.status = TicketStatus.CLOSED
    db_session.queue(ticket)

    svc = TicketService(db_session)
    with pytest.raises(ValueError, match="Invalid transition"):
        await svc.transition_status(
            ticket_id=ticket.id,
            new_status=TicketStatus.IN_PROGRESS,
            actor="agent@co",
        )


async def test_ticket_resolve_sets_timestamp(db_session):
    from app.services.ticket_service import TicketService
    from app.db.models import Ticket

    ticket = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="x",
        description="y",
    )
    ticket.status = TicketStatus.IN_PROGRESS
    db_session.queue(ticket)

    svc = TicketService(db_session)
    result = await svc.resolve(ticket.id, actor="agent@co", note="fixed")

    assert result.status == TicketStatus.RESOLVED
    assert result.resolved_at is not None


async def test_ticket_close_sets_timestamp(db_session):
    from app.services.ticket_service import TicketService
    from app.db.models import Ticket

    ticket = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="x",
        description="y",
    )
    ticket.status = TicketStatus.RESOLVED
    db_session.queue(ticket)

    svc = TicketService(db_session)
    result = await svc.close(ticket.id, actor="agent@co")

    assert result.status == TicketStatus.CLOSED
    assert result.closed_at is not None


async def test_ticket_escalate_bumps_priority_and_tags(db_session):
    """Escalation must: flip status, reassign to human_queue, bump priority,
    add category tag, flip conversation.status, and emit an ESCALATED event."""
    from app.services.ticket_service import TicketService
    from app.db.models import Conversation, Ticket, TicketEvent, TicketEventType

    ticket = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="x",
        description="y",
    )
    ticket.status = TicketStatus.OPEN
    ticket.priority = TicketPriority.MEDIUM
    ticket.tags = []
    ticket.assigned_to = "ai_agent"

    conversation = Conversation(
        customer_id=ticket.customer_id,
        channel=ChannelType.WEB,
    )
    conversation.status = "active"

    # escalate() runs: select Ticket → update → add event → select Conversation
    db_session.queue_many([ticket, conversation])

    svc = TicketService(db_session)
    result = await svc.escalate(
        ticket_id=ticket.id,
        reason="Customer is upset",
        category="angry_customer",
    )

    assert result.status == TicketStatus.ESCALATED
    assert result.assigned_to == "human_queue"
    assert result.priority == TicketPriority.HIGH  # angry_customer bumps to HIGH
    assert "angry_customer" in result.tags

    events = [o for o in db_session.added if isinstance(o, TicketEvent)]
    assert len(events) == 1
    assert events[0].event_type == TicketEventType.ESCALATED
    assert events[0].note == "Customer is upset"
    assert events[0].new_value["escalation_category"] == "angry_customer"

    assert conversation.status == "escalated"


async def test_ticket_escalate_legal_bumps_to_critical(db_session):
    from app.services.ticket_service import TicketService
    from app.db.models import Conversation, Ticket

    ticket = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.GMAIL,
        subject="x",
        description="y",
    )
    ticket.status = TicketStatus.OPEN
    ticket.priority = TicketPriority.LOW
    ticket.tags = []

    conversation = Conversation(customer_id=ticket.customer_id, channel=ChannelType.GMAIL)
    conversation.status = "active"
    db_session.queue_many([ticket, conversation])

    svc = TicketService(db_session)
    result = await svc.escalate(
        ticket_id=ticket.id,
        reason="Customer mentions lawyers",
        category="legal_issue",
    )
    assert result.priority == TicketPriority.CRITICAL


async def test_ticket_assign_auto_flips_escalated_to_in_progress(db_session):
    from app.services.ticket_service import TicketService
    from app.db.models import Ticket, TicketEvent, TicketEventType

    ticket = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="x",
        description="y",
    )
    ticket.status = TicketStatus.ESCALATED
    ticket.assigned_to = "human_queue"
    db_session.queue(ticket)

    svc = TicketService(db_session)
    result = await svc.assign(
        ticket_id=ticket.id, assigned_to="agent@co", actor="supervisor@co"
    )

    assert result.assigned_to == "agent@co"
    assert result.status == TicketStatus.IN_PROGRESS  # auto-flipped

    events = [o for o in db_session.added if isinstance(o, TicketEvent)]
    assert events[-1].event_type == TicketEventType.ASSIGNED
    assert events[-1].old_value == {"assigned_to": "human_queue"}


# ── Escalation priority helper ───────────────────────────────

def test_escalation_priority_helper():
    from app.services.ticket_service import TicketService

    # Critical categories always → CRITICAL
    assert TicketService._escalation_priority(
        "legal_issue", TicketPriority.LOW
    ) == TicketPriority.CRITICAL
    assert TicketService._escalation_priority(
        "security_concern", TicketPriority.HIGH
    ) == TicketPriority.CRITICAL

    # High categories → max(current, HIGH)
    assert TicketService._escalation_priority(
        "refund_request", TicketPriority.LOW
    ) == TicketPriority.HIGH
    assert TicketService._escalation_priority(
        "angry_customer", TicketPriority.CRITICAL
    ) == TicketPriority.CRITICAL  # never downgrade

    # Default categories → max(current, MEDIUM)
    assert TicketService._escalation_priority(
        "low_confidence", TicketPriority.LOW
    ) == TicketPriority.MEDIUM
    assert TicketService._escalation_priority(
        "low_confidence", TicketPriority.HIGH
    ) == TicketPriority.HIGH  # never downgrade


# ── List / get helpers ───────────────────────────────────────

async def test_ticket_list_by_status(db_session):
    from app.services.ticket_service import TicketService
    from app.db.models import Ticket

    t1 = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="a",
        description="x",
    )
    t2 = Ticket(
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="b",
        description="y",
    )
    db_session.queue([t1, t2])

    svc = TicketService(db_session)
    results = await svc.list_by_status(TicketStatus.OPEN, limit=10)
    assert len(results) == 2


async def test_ticket_get_by_id_not_found(db_session):
    from app.services.ticket_service import TicketService

    db_session.queue(None)
    svc = TicketService(db_session)
    assert await svc.get_by_id(uuid.uuid4()) is None
