import httpx
import logging
from typing import Optional, List, Dict, Any

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class WhatsAppClient:
    def __init__(self):
        self.settings = get_settings()
        self.api_url = self.settings.whatsapp_api_url
        self.phone_number_id = self.settings.whatsapp_phone_number_id
        self.access_token = self.settings.whatsapp_access_token
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
        )

    async def close(self):
        await self.client.aclose()

    async def send_message(self, to_phone: str, message_text: str) -> bool:
        """Sends a text message via WhatsApp Cloud API."""
        if not self.phone_number_id or not self.access_token:
            logger.warning("[WHATSAPP] API credentials not configured. Skipping WhatsApp delivery.")
            return False

        url = f"{self.api_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"body": message_text}
        }

        try:
            logger.info(f"[WHATSAPP] Sending message to {to_phone}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"[WHATSAPP] Message sent successfully to {to_phone}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"[WHATSAPP] Failed to send message: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"[WHATSAPP] Unexpected error sending message: {str(e)}")
            return False

    async def mark_as_read(self, message_id: str) -> bool:
        """Marks a specific message as read (blue ticks)."""
        if not self.phone_number_id or not self.access_token:
            return False

        url = f"{self.api_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            logger.debug(f"[WHATSAPP] Marked message {message_id} as read")
            return True
        except Exception as e:
            logger.error(f"[WHATSAPP] Failed to mark message {message_id} as read: {str(e)}")
            return False

    async def send_image(self, to_phone: str, image_url: str, caption: Optional[str] = None) -> bool:
        """Sends an image via WhatsApp Cloud API."""
        if not self.phone_number_id or not self.access_token:
            return False

        url = f"{self.api_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "image",
            "image": {"link": image_url}
        }
        if caption:
            payload["image"]["caption"] = caption

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"[WHATSAPP] Failed to send image: {str(e)}")
            return False

    async def send_template_message(
        self, 
        to_phone: str, 
        template_name: str, 
        language_code: str = "en_US",
        components: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Sends a template message via WhatsApp Cloud API."""
        if not self.phone_number_id or not self.access_token:
            logger.warning("[WHATSAPP] API credentials not configured. Skipping WhatsApp delivery.")
            return False

        url = f"{self.api_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }
        
        if components:
            payload["template"]["components"] = components

        try:
            logger.info(f"[WHATSAPP] Sending template '{template_name}' to {to_phone}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"[WHATSAPP] Template message sent successfully to {to_phone}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"[WHATSAPP] Failed to send template: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"[WHATSAPP] Unexpected error sending template: {str(e)}")
            return False

whatsapp_client = WhatsAppClient()
