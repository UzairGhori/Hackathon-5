"""Ticket management API — endpoints for human agents to manage tickets.

Provides:
  GET    /api/v1/tickets                  — list tickets (filterable by status)
  GET    /api/v1/tickets/escalated        — list escalated tickets (human queue)
  GET    /api/v1/tickets/{id}             — get ticket details
  GET    /api/v1/tickets/{id}/events      — get ticket audit trail
  PATCH  /api/v1/tickets/{id}/status      — transition ticket status
  PATCH  /api/v1/tickets/{id}/assign      — assign ticket to human agent
  POST   /api/v1/tickets/{id}/resolve     — resolve a ticket
  POST   /api/v1/tickets/{id}/close       — close a ticket
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import TicketStatus
from app.schemas.tickets import (
    AssignTicketRequest,
    TicketEventResponse,
    TicketResponse,
    UpdateTicketStatusRequest,
)
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


def _ticket_to_response(ticket) -> TicketResponse:
    return TicketResponse(
        id=ticket.id,
        conversation_id=ticket.conversation_id,
        customer_id=ticket.customer_id,
        channel=ticket.channel.value,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status.value,
        priority=ticket.priority.value,
        assigned_to=ticket.assigned_to,
        tags=ticket.tags or [],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
    )


def _event_to_response(event) -> TicketEventResponse:
    return TicketEventResponse(
        id=event.id,
        ticket_id=event.ticket_id,
        event_type=event.event_type.value,
        actor=event.actor,
        old_value=event.old_value,
        new_value=event.new_value,
        note=event.note,
        created_at=event.created_at,
    )


# ── List tickets ─────────────────────────────────────────────

@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    status: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[TicketResponse]:
    """List tickets, optionally filtered by status."""
    svc = TicketService(session)

    if status:
        try:
            ticket_status = TicketStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
        tickets = await svc.list_by_status(ticket_status, limit)
    else:
        from sqlalchemy import select
        from app.db.models import Ticket
        result = await session.execute(
            select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
        )
        tickets = list(result.scalars().all())

    return [_ticket_to_response(t) for t in tickets]


# ── List escalated (human queue) ─────────────────────────────

@router.get("/escalated", response_model=list[TicketResponse])
async def list_escalated(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[TicketResponse]:
    """List all escalated tickets waiting for human pickup."""
    svc = TicketService(session)
    tickets = await svc.list_escalated(limit)
    return [_ticket_to_response(t) for t in tickets]


# ── Get ticket detail ────────────────────────────────────────

@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TicketResponse:
    """Get a single ticket by ID."""
    svc = TicketService(session)
    ticket = await svc.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return _ticket_to_response(ticket)


# ── Get ticket audit trail ───────────────────────────────────

@router.get("/{ticket_id}/events", response_model=list[TicketEventResponse])
async def get_ticket_events(
    ticket_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[TicketEventResponse]:
    """Get the full audit trail for a ticket."""
    svc = TicketService(session)
    ticket = await svc.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    events = await svc.get_events(ticket_id)
    return [_event_to_response(e) for e in events]


# ── Update ticket status ─────────────────────────────────────

@router.patch("/{ticket_id}/status", response_model=TicketResponse)
async def update_ticket_status(
    ticket_id: uuid.UUID,
    body: UpdateTicketStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> TicketResponse:
    """Transition a ticket to a new status."""
    svc = TicketService(session)
    ticket = await svc.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    try:
        new_status = TicketStatus(body.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {body.status}")

    try:
        ticket = await svc.transition_status(
            ticket_id, new_status, body.actor, body.note
        )
    except ValueError as e:
        raise HTTPException(422, str(e))

    return _ticket_to_response(ticket)


# ── Assign ticket ────────────────────────────────────────────

@router.patch("/{ticket_id}/assign", response_model=TicketResponse)
async def assign_ticket(
    ticket_id: uuid.UUID,
    body: AssignTicketRequest,
    session: AsyncSession = Depends(get_session),
) -> TicketResponse:
    """Assign a ticket to a human agent."""
    svc = TicketService(session)
    ticket = await svc.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    ticket = await svc.assign(ticket_id, body.assigned_to, body.actor)
    return _ticket_to_response(ticket)


# ── Resolve ticket ───────────────────────────────────────────

@router.post("/{ticket_id}/resolve", response_model=TicketResponse)
async def resolve_ticket(
    ticket_id: uuid.UUID,
    body: UpdateTicketStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> TicketResponse:
    """Resolve a ticket."""
    svc = TicketService(session)
    ticket = await svc.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    try:
        ticket = await svc.resolve(ticket_id, body.actor, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e))

    return _ticket_to_response(ticket)


# ── Close ticket ─────────────────────────────────────────────

@router.post("/{ticket_id}/close", response_model=TicketResponse)
async def close_ticket(
    ticket_id: uuid.UUID,
    body: UpdateTicketStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> TicketResponse:
    """Close a ticket."""
    svc = TicketService(session)
    ticket = await svc.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    try:
        ticket = await svc.close(ticket_id, body.actor, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e))

    return _ticket_to_response(ticket)
