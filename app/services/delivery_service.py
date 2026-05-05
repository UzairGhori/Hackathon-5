import logging
from typing import Optional, Dict, Any

from app.db.models import ChannelType
from app.integrations.gmail_client import gmail_client
from app.integrations.twilio_whatsapp_client import twilio_whatsapp_client
from app.core.logging import get_logger

logger = get_logger(__name__)

class DeliveryService:
    async def deliver(
        self,
        channel: ChannelType,
        customer_identifier: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Routes message delivery to the appropriate channel client.
        """
        if not customer_identifier:
            logger.error(f"[DELIVERY] No customer identifier provided for channel {channel}. Cannot deliver.")
            return False

        logger.info(f"[DELIVERY] Attempting to deliver message via {channel} to {customer_identifier}")

        success = False
        try:
            if channel == ChannelType.GMAIL:
                # For Gmail, we use a basic subject if not provided in metadata
                subject = (metadata or {}).get("subject", "Re: Customer Support")
                # We could use a proper HTML template here
                body_html = f"<p>{message}</p>"
                body_text = message
                
                # Support for threading
                in_reply_to = (metadata or {}).get("gmail_message_id")
                references = (metadata or {}).get("gmail_references")
                
                success = await gmail_client.send_email(
                    to_email=customer_identifier,
                    subject=subject,
                    body_html=body_html,
                    body_text=body_text,
                    in_reply_to=in_reply_to,
                    references=references
                )

            elif channel == ChannelType.WHATSAPP:
                success = await twilio_whatsapp_client.send_message(
                    to_phone=customer_identifier,
                    message_text=message
                )

            elif channel == ChannelType.WEB:
                # Web channel delivery is handled via polling/websockets in the frontend
                # So we just log it as a no-op here
                logger.debug(f"[DELIVERY] Web channel delivery is no-op (stored in DB for dashboard).")
                success = True

            else:
                logger.warning(f"[DELIVERY] Unsupported channel for outbound delivery: {channel}")
                success = False

        except Exception as e:
            logger.error(f"[DELIVERY] Error delivering message to {customer_identifier} via {channel}: {str(e)}")
            success = False

        if success:
            logger.info(f"[DELIVERY] Successfully delivered message via {channel} to {customer_identifier}")
        else:
            logger.error(f"[DELIVERY] Failed to deliver message via {channel} to {customer_identifier}")
            
        return success

delivery_service = DeliveryService()
