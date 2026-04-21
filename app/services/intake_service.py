"""Intake orchestrator — the single entry point for all channels.

Flow:
  1. Find or create customer
  2. Find or create conversation
  3. Store message
  4. Enqueue to Kafka
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.schemas.intake import IntakeResult, NormalizedMessage
from app.services.customer_service import CustomerService
from app.services.conversation_service import ConversationService
from app.services.queue_service import QueueService

logger = get_logger(__name__)


class IntakeService:
    def __init__(self, session: AsyncSession):
        self.customer_svc = CustomerService(session)
        self.conversation_svc = ConversationService(session)

    async def process(self, msg: NormalizedMessage) -> IntakeResult:
        """Process a normalized inbound message end-to-end."""

        # 1. Resolve customer
        customer, is_new_customer = await self.customer_svc.find_or_create(
            channel=msg.channel,
            identifier=msg.customer_identifier,
            full_name=msg.customer_name,
            company=msg.company,
        )

        # 2. Resolve conversation
        conversation, is_new_conversation = await self.conversation_svc.find_or_create(
            customer_id=customer.id,
            channel=msg.channel,
            subject=msg.subject,
        )

        # 3. Store message
        message = await self.conversation_svc.add_message(
            conversation_id=conversation.id,
            channel=msg.channel,
            content=msg.content,
            channel_message_id=msg.channel_message_id,
            metadata=msg.metadata,
        )

        result = IntakeResult(
            customer_id=customer.id,
            conversation_id=conversation.id,
            message_id=message.id,
            channel=msg.channel,
            is_new_customer=is_new_customer,
            is_new_conversation=is_new_conversation,
        )

        # 4. Publish to Kafka for async agent processing
        await QueueService.enqueue_message(result)

        logger.info(
            "Intake complete: customer=%s conversation=%s message=%s channel=%s",
            customer.id, conversation.id, message.id, msg.channel.value,
        )
        return result
