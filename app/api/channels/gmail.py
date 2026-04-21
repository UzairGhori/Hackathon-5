"""Gmail webhook intake endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import ChannelType
from app.schemas.channels import GmailWebhookPayload, IntakeResponse
from app.schemas.intake import NormalizedMessage
from app.services.intake_service import IntakeService

router = APIRouter()


@router.post("/gmail", response_model=IntakeResponse)
async def gmail_intake(
    payload: GmailWebhookPayload,
    session: AsyncSession = Depends(get_session),
) -> IntakeResponse:
    """Receive a parsed email from Gmail webhook / Pub/Sub push."""
    normalized = NormalizedMessage(
        channel=ChannelType.GMAIL,
        customer_name=payload.from_name or payload.from_email,
        customer_identifier=payload.from_email,
        subject=payload.subject,
        content=payload.body_plain,
        channel_message_id=payload.message_id,
        metadata={
            "thread_id": payload.thread_id,
            "headers": payload.headers,
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
