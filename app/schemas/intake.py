"""Normalized internal message — the common format after channel parsing.

Every channel handler converts its raw payload into this structure
before passing it to the intake service.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import ChannelType


class NormalizedMessage(BaseModel):
    """Channel-agnostic representation of an incoming customer message."""

    channel: ChannelType
    customer_name: str
    customer_identifier: str          # email or phone number
    company: str | None = None
    subject: str | None = None
    content: str
    channel_message_id: str | None = None   # external id for dedup
    metadata: dict = Field(default_factory=dict)


class IntakeResult(BaseModel):
    """Returned by the intake service after processing."""

    customer_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    channel: ChannelType
    is_new_customer: bool
    is_new_conversation: bool
