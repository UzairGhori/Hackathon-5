"""Pydantic schemas for ticket API endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TicketResponse(BaseModel):
    """Single ticket in API responses."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    customer_id: uuid.UUID
    channel: str
    subject: str
    description: str | None
    status: str
    priority: str
    assigned_to: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class TicketEventResponse(BaseModel):
    """Single audit event in API responses."""
    id: uuid.UUID
    ticket_id: uuid.UUID
    event_type: str
    actor: str
    old_value: dict | None
    new_value: dict | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignTicketRequest(BaseModel):
    """Request body for assigning a ticket."""
    assigned_to: str = Field(..., min_length=1, max_length=255)
    actor: str = Field(..., min_length=1, max_length=255)


class UpdateTicketStatusRequest(BaseModel):
    """Request body for changing ticket status."""
    status: str = Field(..., description="Target status: open, in_progress, waiting_on_customer, escalated, resolved, closed")
    actor: str = Field(..., min_length=1, max_length=255)
    note: str | None = None
