"""Conversation and message management."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    ChannelType,
    Conversation,
    Message,
    MessageDirection,
    MessageSender,
)

logger = get_logger(__name__)


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_or_create(
        self,
        customer_id: uuid.UUID,
        channel: ChannelType,
        subject: str | None = None,
    ) -> tuple[Conversation, bool]:
        """Find an active conversation for the customer+channel, or create one.

        Returns (conversation, is_new).
        """
        stmt = (
            select(Conversation)
            .where(
                Conversation.customer_id == customer_id,
                Conversation.channel == channel,
                Conversation.status == "active",
            )
            .order_by(Conversation.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation:
            logger.info(
                "Found active conversation %s for customer %s on %s",
                conversation.id, customer_id, channel.value,
            )
            return conversation, False

        conversation = Conversation(
            customer_id=customer_id,
            channel=channel,
            subject=subject,
        )
        self.session.add(conversation)
        await self.session.flush()

        logger.info(
            "Created new conversation %s for customer %s on %s",
            conversation.id, customer_id, channel.value,
        )
        return conversation, True

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        channel: ChannelType,
        content: str,
        direction: MessageDirection = MessageDirection.INBOUND,
        sender: MessageSender = MessageSender.CUSTOMER,
        channel_message_id: str | None = None,
        metadata: dict | None = None,
    ) -> Message:
        """Store a message in a conversation."""
        message = Message(
            conversation_id=conversation_id,
            direction=direction,
            sender=sender,
            content=content,
            channel=channel,
            channel_message_id=channel_message_id,
            metadata_=metadata or {},
        )
        self.session.add(message)
        await self.session.flush()

        logger.info(
            "Stored message %s in conversation %s (%s/%s)",
            message.id, conversation_id, direction.value, sender.value,
        )
        return message

    async def get_latest_message(
        self,
        conversation_id: uuid.UUID,
        direction: MessageDirection = MessageDirection.INBOUND,
    ) -> Message | None:
        """Fetch the most recent message in a conversation."""
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.direction == direction,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
