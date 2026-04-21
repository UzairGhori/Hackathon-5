"""Web Support Form intake endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import ChannelType
from app.schemas.channels import IntakeResponse, WebFormPayload
from app.schemas.intake import NormalizedMessage
from app.services.intake_service import IntakeService

router = APIRouter()


@router.post("/web", response_model=IntakeResponse)
async def web_intake(
    payload: WebFormPayload,
    session: AsyncSession = Depends(get_session),
) -> IntakeResponse:
    """Receive a message from the Next.js web support form."""
    normalized = NormalizedMessage(
        channel=ChannelType.WEB,
        customer_name=payload.name,
        customer_identifier=payload.email,
        company=payload.company,
        subject=payload.subject,
        content=payload.message,
        metadata=payload.metadata,
    )

    svc = IntakeService(session)
    result = await svc.process(normalized)

    return IntakeResponse(
        customer_id=result.customer_id,
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        channel=result.channel.value,
    )
