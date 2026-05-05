import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosmtplib
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class GmailClient:
    def __init__(self):
        self.settings = get_settings()
        self.host = self.settings.gmail_smtp_host
        self.port = self.settings.gmail_smtp_port
        self.username = self.settings.gmail_email_address
        self.password = self.settings.gmail_app_password
        self.from_name = self.settings.gmail_from_name

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None
    ) -> bool:
        """Sends an email using Gmail SMTP."""
        if not self.username or not self.password:
            logger.warning("[GMAIL] SMTP credentials not configured. Skipping email delivery.")
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{self.from_name} <{self.username}>"
        message["To"] = to_email

        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references

        # Attach body parts
        message.attach(MIMEText(body_text, "plain"))
        message.attach(MIMEText(body_html, "html"))

        try:
            logger.info(f"[GMAIL] Sending email to {to_email} - Subject: {subject}")
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=True if self.port == 587 else False,
                use_tls=True if self.port == 465 else False,
            )
            logger.info(f"[GMAIL] Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"[GMAIL] Failed to send email to {to_email}: {str(e)}")
            return False

gmail_client = GmailClient()
