"""WhatsApp webhook intake endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import ChannelType
from app.schemas.channels import IntakeResponse, WhatsAppWebhookPayload
from app.schemas.intake import NormalizedMessage
from app.services.intake_service import IntakeService

router = APIRouter()


@router.post("/whatsapp", response_model=IntakeResponse)
async def whatsapp_intake(
    payload: WhatsAppWebhookPayload,
    session: AsyncSession = Depends(get_session),
) -> IntakeResponse:
    """Receive a message from WhatsApp Cloud API webhook.

    Processes the first message in the entry list.
    Multi-message batches are handled sequentially.
    """
    # WhatsApp webhooks can batch multiple messages; process first
    msg = payload.entry[0]

    normalized = NormalizedMessage(
        channel=ChannelType.WHATSAPP,
        customer_name=msg.from_name or msg.from_number,
        customer_identifier=msg.from_number,
        content=msg.body,
        channel_message_id=msg.message_id,
        metadata={
            "message_type": msg.message_type,
            **msg.metadata,
        },
    )

    svc = IntakeService(session)
    result = await svc.process(normalized)

    return IntakeResponse(
        customer_id=result.customer_id,
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        channel=result.channel.value,
    )
