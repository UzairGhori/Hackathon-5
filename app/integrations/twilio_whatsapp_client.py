"""Twilio WhatsApp client for sending messages via Twilio's WhatsApp Business API."""

import asyncio
from typing import Optional, Dict, Any

from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TwilioWhatsAppClient:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[TwilioClient] = None

    @property
    def client(self) -> TwilioClient:
        """Lazy-init the Twilio REST client."""
        if self._client is None:
            self._client = TwilioClient(
                self.settings.twilio_account_sid,
                self.settings.twilio_auth_token,
            )
        return self._client

    def _format_whatsapp_number(self, phone: str) -> str:
        """Ensure the phone number has the whatsapp: prefix and + sign."""
        phone = phone.strip()
        if phone.startswith("whatsapp:"):
            return phone
        if not phone.startswith("+"):
            phone = f"+{phone}"
        return f"whatsapp:{phone}"

    @property
    def from_number(self) -> str:
        return self._format_whatsapp_number(self.settings.twilio_whatsapp_number)

    async def send_message(self, to_phone: str, message_text: str) -> bool:
        """Send a text message via Twilio WhatsApp."""
        if not self.settings.twilio_account_sid or not self.settings.twilio_auth_token:
            logger.warning("[TWILIO-WA] Twilio credentials not configured. Skipping delivery.")
            return False

        to = self._format_whatsapp_number(to_phone)
        try:
            logger.info(f"[TWILIO-WA] Sending message to {to}")
            message = await asyncio.to_thread(
                self.client.messages.create,
                body=message_text,
                from_=self.from_number,
                to=to,
            )
            logger.info(f"[TWILIO-WA] Message sent successfully. SID: {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"[TWILIO-WA] Twilio API error: {e.code} - {e.msg}")
            return False
        except Exception as e:
            logger.error(f"[TWILIO-WA] Unexpected error sending message: {str(e)}")
            return False

    async def send_template_message(
        self,
        to_phone: str,
        content_sid: str,
        variables: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Send a pre-approved template message via Twilio WhatsApp.

        Args:
            to_phone: Recipient phone number.
            content_sid: Twilio Content SID for the approved template.
            variables: Template variable substitutions (e.g. {"1": "John"}).
        """
        if not self.settings.twilio_account_sid or not self.settings.twilio_auth_token:
            logger.warning("[TWILIO-WA] Twilio credentials not configured. Skipping delivery.")
            return False

        to = self._format_whatsapp_number(to_phone)
        try:
            logger.info(f"[TWILIO-WA] Sending template {content_sid} to {to}")
            kwargs: Dict[str, Any] = {
                "from_": self.from_number,
                "to": to,
                "content_sid": content_sid,
            }
            if variables:
                kwargs["content_variables"] = str(variables)

            message = await asyncio.to_thread(
                self.client.messages.create,
                **kwargs,
            )
            logger.info(f"[TWILIO-WA] Template message sent. SID: {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"[TWILIO-WA] Twilio API error sending template: {e.code} - {e.msg}")
            return False
        except Exception as e:
            logger.error(f"[TWILIO-WA] Unexpected error sending template: {str(e)}")
            return False

    async def send_media_message(
        self,
        to_phone: str,
        media_url: str,
        body: Optional[str] = None,
    ) -> bool:
        """Send a media message (image, document, etc.) via Twilio WhatsApp."""
        if not self.settings.twilio_account_sid or not self.settings.twilio_auth_token:
            logger.warning("[TWILIO-WA] Twilio credentials not configured. Skipping delivery.")
            return False

        to = self._format_whatsapp_number(to_phone)
        try:
            logger.info(f"[TWILIO-WA] Sending media message to {to}")
            kwargs: Dict[str, Any] = {
                "from_": self.from_number,
                "to": to,
                "media_url": [media_url],
            }
            if body:
                kwargs["body"] = body

            message = await asyncio.to_thread(
                self.client.messages.create,
                **kwargs,
            )
            logger.info(f"[TWILIO-WA] Media message sent. SID: {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"[TWILIO-WA] Twilio API error sending media: {e.code} - {e.msg}")
            return False
        except Exception as e:
            logger.error(f"[TWILIO-WA] Unexpected error sending media: {str(e)}")
            return False


twilio_whatsapp_client = TwilioWhatsAppClient()
