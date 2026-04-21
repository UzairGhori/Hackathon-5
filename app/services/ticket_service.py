"""Ticket lifecycle management — create, transition, escalate, resolve, close.

Enforces a strict state machine:

    open ──→ in_progress ──→ resolved ──→ closed
      │          │               ▲
      │          ▼               │
      ├──→ escalated ───────────┘
      │          │
      │          ▼
      │     (human_queue)
      │
      └──→ waiting_on_customer ──→ open (when customer replies)

Every status change is recorded as an immutable TicketEvent for audit.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    ChannelType,
    Conversation,
    Ticket,
    TicketEvent,
    TicketEventType,
    TicketPriority,
    TicketStatus,
)

logger = get_logger(__name__)

# ── Valid state transitions ──────────────────────────────────

VALID_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.ESCALATED,
        TicketStatus.WAITING_ON_CUSTOMER,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.IN_PROGRESS: {
        TicketStatus.ESCALATED,
        TicketStatus.WAITING_ON_CUSTOMER,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.WAITING_ON_CUSTOMER: {
        TicketStatus.OPEN,
        TicketStatus.IN_PROGRESS,
        TicketStatus.ESCALATED,
        TicketStatus.CLOSED,
    },
    TicketStatus.ESCALATED: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.RESOLVED: {
        TicketStatus.CLOSED,
        TicketStatus.OPEN,  # reopen
    },
    TicketStatus.CLOSED: {
        TicketStatus.OPEN,  # reopen
    },
}

# ── Escalation categories ────────────────────────────────────

ESCALATION_CATEGORIES = {
    "refund_request",
    "pricing_question",
    "legal_issue",
    "angry_customer",
    "low_confidence",
    "customer_requested_human",
    "complex_technical",
    "billing_dispute",
    "account_deletion",
    "security_concern",
}


class TicketService:
    """Manages the full ticket lifecycle with audit trail."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Create ───────────────────────────────────────────────

    async def create_ticket(
        self,
        conversation_id: uuid.UUID,
        customer_id: uuid.UUID,
        channel: ChannelType,
        subject: str,
        description: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        assigned_to: str = "ai_agent",
        tags: list[str] | None = None,
    ) -> Ticket:
        """Create a new ticket and record the creation event."""
        ticket = Ticket(
            conversation_id=conversation_id,
            customer_id=customer_id,
            channel=channel,
            subject=subject,
            description=description,
            priority=priority,
            status=TicketStatus.OPEN,
            assigned_to=assigned_to,
            tags=tags or [],
        )
        self.session.add(ticket)
        await self.session.flush()

        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=TicketEventType.CREATED,
            actor=assigned_to,
            new_value={
                "subject": subject,
                "priority": priority.value,
                "status": "open",
                "assigned_to": assigned_to,
            },
        )
        self.session.add(event)
        await self.session.flush()

        logger.info("Created ticket %s [priority=%s] for conversation %s",
                     ticket.id, priority.value, conversation_id)
        return ticket

    # ── Status transitions ───────────────────────────────────

    async def transition_status(
        self,
        ticket_id: uuid.UUID,
        new_status: TicketStatus,
        actor: str,
        note: str | None = None,
    ) -> Ticket:
        """Move a ticket to a new status. Raises ValueError on invalid transition."""
        ticket = (
            await self.session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
        ).scalar_one()

        old_status = ticket.status
        if new_status not in VALID_TRANSITIONS.get(old_status, set()):
            raise ValueError(
                f"Invalid transition: {old_status.value} → {new_status.value}"
            )

        ticket.status = new_status

        # Set timestamps for terminal states
        now = datetime.now(timezone.utc)
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = now
        elif new_status == TicketStatus.CLOSED:
            ticket.closed_at = now

        event_type_map = {
            TicketStatus.ESCALATED: TicketEventType.ESCALATED,
            TicketStatus.RESOLVED: TicketEventType.RESOLVED,
            TicketStatus.CLOSED: TicketEventType.CLOSED,
        }
        event_type = event_type_map.get(new_status, TicketEventType.STATUS_CHANGED)

        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=event_type,
            actor=actor,
            old_value={"status": old_status.value},
            new_value={"status": new_status.value},
            note=note,
        )
        self.session.add(event)
        await self.session.flush()

        logger.info("Ticket %s: %s → %s [actor=%s]",
                     ticket_id, old_status.value, new_status.value, actor)
        return ticket

    # ── Escalate ─────────────────────────────────────────────

    async def escalate(
        self,
        ticket_id: uuid.UUID,
        reason: str,
        category: str,
        actor: str = "ai_agent",
    ) -> Ticket:
        """Escalate a ticket to the human queue with categorized reason.

        Args:
            ticket_id: The ticket to escalate.
            reason: Free-text explanation of why escalation is needed.
            category: One of ESCALATION_CATEGORIES (e.g. 'refund_request').
            actor: Who triggered the escalation.
        """
        ticket = (
            await self.session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
        ).scalar_one()

        old_status = ticket.status
        ticket.status = TicketStatus.ESCALATED
        ticket.assigned_to = "human_queue"
        ticket.priority = self._escalation_priority(category, ticket.priority)
        if category not in (ticket.tags or []):
            ticket.tags = (ticket.tags or []) + [category]

        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=TicketEventType.ESCALATED,
            actor=actor,
            old_value={
                "status": old_status.value,
                "assigned_to": "ai_agent",
            },
            new_value={
                "status": "escalated",
                "assigned_to": "human_queue",
                "escalation_category": category,
                "priority": ticket.priority.value,
            },
            note=reason,
        )
        self.session.add(event)
        await self.session.flush()

        # Also mark the conversation as escalated
        conversation = (
            await self.session.execute(
                select(Conversation).where(Conversation.id == ticket.conversation_id)
            )
        ).scalar_one()
        conversation.status = "escalated"
        await self.session.flush()

        logger.info("Escalated ticket %s [category=%s priority=%s]: %s",
                     ticket_id, category, ticket.priority.value, reason)
        return ticket

    # ── Assign ───────────────────────────────────────────────

    async def assign(
        self,
        ticket_id: uuid.UUID,
        assigned_to: str,
        actor: str,
    ) -> Ticket:
        """Assign a ticket to a human agent."""
        ticket = (
            await self.session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
        ).scalar_one()

        old_assigned = ticket.assigned_to
        ticket.assigned_to = assigned_to

        # Move from escalated → in_progress when a human picks it up
        if ticket.status == TicketStatus.ESCALATED:
            ticket.status = TicketStatus.IN_PROGRESS

        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=TicketEventType.ASSIGNED,
            actor=actor,
            old_value={"assigned_to": old_assigned},
            new_value={"assigned_to": assigned_to, "status": ticket.status.value},
        )
        self.session.add(event)
        await self.session.flush()

        logger.info("Assigned ticket %s to %s [actor=%s]",
                     ticket_id, assigned_to, actor)
        return ticket

    # ── Resolve ──────────────────────────────────────────────

    async def resolve(
        self,
        ticket_id: uuid.UUID,
        actor: str,
        note: str | None = None,
    ) -> Ticket:
        """Resolve a ticket."""
        return await self.transition_status(
            ticket_id, TicketStatus.RESOLVED, actor, note
        )

    # ── Close ────────────────────────────────────────────────

    async def close(
        self,
        ticket_id: uuid.UUID,
        actor: str,
        note: str | None = None,
    ) -> Ticket:
        """Close a ticket."""
        return await self.transition_status(
            ticket_id, TicketStatus.CLOSED, actor, note
        )

    # ── Query ────────────────────────────────────────────────

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        """Fetch a single ticket by ID."""
        result = await self.session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: TicketStatus,
        limit: int = 50,
    ) -> list[Ticket]:
        """List tickets filtered by status, newest first."""
        result = await self.session.execute(
            select(Ticket)
            .where(Ticket.status == status)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_escalated(self, limit: int = 50) -> list[Ticket]:
        """List all escalated tickets awaiting human pickup."""
        return await self.list_by_status(TicketStatus.ESCALATED, limit)

    async def get_events(self, ticket_id: uuid.UUID) -> list[TicketEvent]:
        """Get the full audit trail for a ticket."""
        result = await self.session.execute(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at.asc())
        )
        return list(result.scalars().all())

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _escalation_priority(
        category: str, current: TicketPriority
    ) -> TicketPriority:
        """Bump priority based on escalation category."""
        critical_categories = {"legal_issue", "security_concern"}
        high_categories = {
            "refund_request", "billing_dispute", "angry_customer",
            "account_deletion",
        }

        if category in critical_categories:
            return TicketPriority.CRITICAL
        if category in high_categories:
            return max(current, TicketPriority.HIGH, key=_priority_rank)
        return max(current, TicketPriority.MEDIUM, key=_priority_rank)


def _priority_rank(p: TicketPriority) -> int:
    """Numeric rank for priority comparison."""
    return {
        TicketPriority.LOW: 0,
        TicketPriority.MEDIUM: 1,
        TicketPriority.HIGH: 2,
        TicketPriority.CRITICAL: 3,
    }[p]
