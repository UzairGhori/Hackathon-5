"""Twilio WhatsApp webhook intake endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator

from app.config import get_settings
from app.db.database import get_session
from app.db.models import ChannelType
from app.schemas.channels import IntakeResponse
from app.schemas.intake import NormalizedMessage
from app.services.intake_service import IntakeService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _validate_twilio_signature(request: Request, form_data: dict) -> bool:
    """Validate that the request genuinely came from Twilio."""
    settings = get_settings()
    if not settings.twilio_auth_token:
        logger.warning("[TWILIO-WA] Auth token not configured — skipping signature validation")
        return True

    validator = RequestValidator(settings.twilio_auth_token)
    # Reconstruct the full URL Twilio used to reach us
    url = str(request.url)
    signature = request.headers.get("X-Twilio-Signature", "")
    return validator.validate(url, form_data, signature)


@router.post("/twilio-whatsapp")
async def twilio_whatsapp_intake(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Receive an inbound WhatsApp message from Twilio."""
    form_data = await request.form()
    params = dict(form_data)

    # Validate Twilio signature
    if not _validate_twilio_signature(request, params):
        logger.warning("[TWILIO-WA] Invalid Twilio webhook signature")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Extract fields from Twilio's form-encoded webhook
    from_number = params.get("From", "")        # e.g. "whatsapp:+923001234567"
    body = params.get("Body", "")
    message_sid = params.get("MessageSid", "")
    num_media = int(params.get("NumMedia", "0"))
    profile_name = params.get("ProfileName", from_number)

    # Strip the "whatsapp:" prefix to get a clean phone number
    customer_phone = from_number.replace("whatsapp:", "").strip()

    if not customer_phone:
        logger.warning("[TWILIO-WA] Received webhook with no From number")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
            media_type="application/xml",
        )

    # Build content from body + any attached media
    content = body or ""
    metadata = {"message_sid": message_sid}

    for i in range(num_media):
        media_url = params.get(f"MediaUrl{i}", "")
        media_type = params.get(f"MediaContentType{i}", "")
        if media_url:
            content += f"\n[Media: {media_type}] {media_url}"
            metadata[f"media_url_{i}"] = media_url
            metadata[f"media_type_{i}"] = media_type

    if not content.strip():
        content = "[Empty message]"

    normalized = NormalizedMessage(
        channel=ChannelType.WHATSAPP,
        customer_name=profile_name,
        customer_identifier=customer_phone,
        content=content.strip(),
        channel_message_id=message_sid,
        metadata=metadata,
    )

    svc = IntakeService(session)
    result = await svc.process(normalized)

    logger.info(
        "[TWILIO-WA] Processed inbound message from %s (SID: %s)",
        customer_phone,
        message_sid,
    )

    # Return empty TwiML — we send replies asynchronously via the REST API
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )
