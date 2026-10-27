"""Email transport. Sign-in links never enter application or task logs."""

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.config import Settings


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, text: str, html: str) -> None: ...


class SMTPSender:
    def __init__(self, config: Settings) -> None:
        self.config = config

    async def send(self, to: str, subject: str, text: str, html: str) -> None:
        message = EmailMessage()
        message["From"] = self.config.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        def deliver() -> None:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=15) as smtp:
                if self.config.smtp_starttls:
                    smtp.starttls()
                if self.config.smtp_username:
                    smtp.login(self.config.smtp_username, self.config.smtp_password)
                smtp.send_message(message)

        await asyncio.to_thread(deliver)


class ResendSender:
    def __init__(self, config: Settings) -> None:
        self.config = config

    async def send(self, to: str, subject: str, text: str, html: str) -> None:
        if not self.config.email_api_key:
            raise RuntimeError("Email delivery is not configured")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.config.email_api_key}"},
                json={
                    "from": self.config.email_from,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                    "html": html,
                },
            )
            response.raise_for_status()


def get_sender(config: Settings) -> EmailSender:
    return ResendSender(config) if config.email_provider == "resend" else SMTPSender(config)
