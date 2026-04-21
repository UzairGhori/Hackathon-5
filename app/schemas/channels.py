"""Pydantic schemas for channel intake payloads and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Web Support Form ─────────────────────────────────────────

class WebFormPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    subject: str = Field(..., min_length=1, max_length=512)
    message: str = Field(..., min_length=1)
    company: str | None = None
    metadata: dict = Field(default_factory=dict)


# ── Gmail Webhook ────────────────────────────────────────────

class GmailWebhookPayload(BaseModel):
    message_id: str = Field(..., description="Gmail message ID")
    thread_id: str | None = None
    from_email: EmailStr
    from_name: str = Field(default="")
    to_email: EmailStr
    subject: str = Field(default="")
    body_plain: str = Field(..., min_length=1)
    body_html: str | None = None
    received_at: datetime | None = None
    headers: dict = Field(default_factory=dict)


# ── WhatsApp Webhook ─────────────────────────────────────────

class WhatsAppMessage(BaseModel):
    message_id: str = Field(..., description="WhatsApp message ID")
    from_number: str = Field(..., pattern=r"^\+?[1-9]\d{6,14}$")
    from_name: str = Field(default="")
    body: str = Field(..., min_length=1)
    timestamp: datetime | None = None
    message_type: str = Field(default="text")
    metadata: dict = Field(default_factory=dict)


class WhatsAppWebhookPayload(BaseModel):
    """Normalized payload from WhatsApp Cloud API webhook."""
    entry: list[WhatsAppMessage] = Field(..., min_length=1)


# ── Common Intake Response ───────────────────────────────────

class IntakeResponse(BaseModel):
    status: str = "accepted"
    customer_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    channel: str
