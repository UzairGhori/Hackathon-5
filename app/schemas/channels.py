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

class WhatsAppProfile(BaseModel):
    name: str | None = None


class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile = Field(default_factory=WhatsAppProfile)
    wa_id: str


class WhatsAppText(BaseModel):
    body: str


class WhatsAppMedia(BaseModel):
    id: str
    mime_type: str | None = None
    sha256: str | None = None
    caption: str | None = None
    filename: str | None = None


class WhatsAppMessage(BaseModel):
    id: str
    from_: str = Field(..., alias="from")
    timestamp: str
    type: str
    text: WhatsAppText | None = None
    image: WhatsAppMedia | None = None
    video: WhatsAppMedia | None = None
    audio: WhatsAppMedia | None = None
    document: WhatsAppMedia | None = None
    voice: WhatsAppMedia | None = None
    location: dict | None = None
    contacts: list[dict] | None = None
    errors: list[dict] | None = None


class WhatsAppStatus(BaseModel):
    id: str
    status: str
    timestamp: str
    recipient_id: str
    conversation: dict | None = None
    pricing: dict | None = None


class WhatsAppMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: list[WhatsAppContact] | None = None
    messages: list[WhatsAppMessage] | None = None
    statuses: list[WhatsAppStatus] | None = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Full payload from WhatsApp Cloud API webhook."""
    object: str = "whatsapp_business_account"
    entry: list[WhatsAppEntry]


# ── Common Intake Response ───────────────────────────────────

class IntakeResponse(BaseModel):
    status: str = "accepted"
    customer_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    channel: str
