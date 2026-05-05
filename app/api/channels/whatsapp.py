"""WhatsApp webhook intake endpoint."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_session
from app.db.models import ChannelType
from app.schemas.channels import IntakeResponse, WhatsAppWebhookPayload
from app.schemas.intake import NormalizedMessage
from app.services.intake_service import IntakeService
from app.core.logging import get_logger
from app.integrations.whatsapp_client import whatsapp_client

logger = get_logger(__name__)
router = APIRouter()


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify that the payload was sent from WhatsApp by validating SHA256."""
    if not signature or not signature.startswith("sha256="):
        return False
    
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)


@router.post("/whatsapp", response_model=IntakeResponse)
async def whatsapp_intake(
    request: Request,
    x_hub_signature_256: str = Header(None),
    session: AsyncSession = Depends(get_session),
) -> IntakeResponse:
    """Receive a message from WhatsApp Cloud API webhook."""
    settings = get_settings()
    raw_body = await request.body()

    # Verify signature if secret is configured
    if settings.whatsapp_app_secret:
        if not verify_signature(raw_body, x_hub_signature_256, settings.whatsapp_app_secret):
            logger.warning("[WHATSAPP] Invalid webhook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        body_json = json.loads(raw_body)
        payload = WhatsAppWebhookPayload(**body_json)
    except Exception as e:
        logger.error(f"[WHATSAPP] Failed to parse webhook payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload format")

    svc = IntakeService(session)
    last_result = None

    for entry in payload.entry:
        for change in entry.changes:
            value = change.value
            
            # Handle status updates
            if value.statuses:
                for status in value.statuses:
                    logger.info(f"[WHATSAPP] Status update: {status.id} is now {status.status}")
                continue

            # Handle incoming messages
            if value.messages:
                # Map contacts for easier lookup
                contacts_map = {c.wa_id: c.profile.name for c in (value.contacts or [])}
                
                for msg in value.messages:
                    customer_number = msg.from_
                    customer_name = contacts_map.get(customer_number, customer_number)
                    
                    # Mark as read
                    await whatsapp_client.mark_as_read(msg.id)
                    
                    content = ""
                    metadata = {"msg_id": msg.id, "type": msg.type}

                    if msg.type == "text" and msg.text:
                        content = msg.text.body
                    elif msg.type == "image" and msg.image:
                        content = f"[Image] {msg.image.caption or ''} (ID: {msg.image.id})"
                        metadata["media_id"] = msg.image.id
                    elif msg.type == "video" and msg.video:
                        content = f"[Video] {msg.video.caption or ''} (ID: {msg.video.id})"
                        metadata["media_id"] = msg.video.id
                    elif msg.type == "audio" and msg.audio:
                        content = f"[Audio] (ID: {msg.audio.id})"
                        metadata["media_id"] = msg.audio.id
                    elif msg.type == "document" and msg.document:
                        content = f"[Document] {msg.document.filename or ''} (ID: {msg.document.id})"
                        metadata["media_id"] = msg.document.id
                    elif msg.type == "location" and msg.location:
                        content = f"[Location] Lat: {msg.location.get('latitude')}, Long: {msg.location.get('longitude')}"
                        metadata["location"] = msg.location
                    else:
                        content = f"[Unsupported Message Type: {msg.type}]"

                    normalized = NormalizedMessage(
                        channel=ChannelType.WHATSAPP,
                        customer_name=customer_name,
                        customer_identifier=customer_number,
                        content=content,
                        channel_message_id=msg.id,
                        metadata=metadata,
                    )

                    last_result = await svc.process(normalized)

    if not last_result:
        # If it was just a status update or empty, return a dummy success
        # But according to response_model, we need an IntakeResponse
        # This might happen if we only get statuses.
        # We should probably return a 200 OK immediately if it's just a status update.
        return Response(content="OK", status_code=200)

    return IntakeResponse(
        customer_id=last_result.customer_id,
        conversation_id=last_result.conversation_id,
        message_id=last_result.message_id,
        channel=last_result.channel.value,
    )


@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp webhook verification (GET)."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        # Return the challenge as plain text
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)
