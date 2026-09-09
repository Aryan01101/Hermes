"""Gmail API polling for a personal Gmail mailbox."""

import asyncio
import base64
import json
import logging
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from typing import Any, Dict

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.core.config import get_settings
from src.services.database import get_database
from src.services.inbound import process_inbound_email

logger = logging.getLogger(__name__)

GMAIL_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailMailService:
    """Poll unread Inbox messages using delegated Gmail API access."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_database()

    async def run(self) -> None:
        """Continuously poll the Inbox without bringing down the web process."""
        logger.info("Gmail polling started (interval: %ss)", self.settings.gmail_poll_interval_seconds)

        while True:
            try:
                logger.info("Checking Gmail inbox for unread messages...")
                processed = await self.poll_inbox()
                if processed:
                    logger.info("✓ Processed %s Gmail message(s)", processed)
                else:
                    logger.info("No unread messages found in Gmail inbox")
            except asyncio.CancelledError:
                logger.info("Gmail polling cancelled")
                raise
            except Exception:
                logger.exception("✗ Gmail Inbox polling failed")

            await asyncio.sleep(self.settings.gmail_poll_interval_seconds)

    async def poll_inbox(self) -> int:
        """Process unread Inbox messages, then remove their UNREAD label on success."""
        logger.debug("Getting Gmail access token...")
        access_token = await self._get_access_token()
        logger.debug("✓ Access token obtained")

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"q": "in:inbox is:unread", "maxResults": "10"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            logger.debug("Querying Gmail API for unread messages...")
            response = await client.get(
                f"{GMAIL_BASE_URL}/messages", headers=headers, params=params
            )
            response.raise_for_status()
            messages = response.json().get("messages", [])
            logger.info("Found %s unread message(s) in Gmail inbox", len(messages))

            for idx, message in enumerate(messages, 1):
                message_id = message["id"]
                logger.info("[%s/%s] Processing Gmail message ID: %s", idx, len(messages), message_id)

                logger.debug("Fetching raw message content...")
                raw_message = await client.get(
                    f"{GMAIL_BASE_URL}/messages/{message_id}",
                    headers=headers,
                    params={"format": "raw"},
                )
                raw_message.raise_for_status()

                parsed = self._parse_message(raw_message.json(), message_id)
                logger.info("Email from: %s, subject: %s", parsed["from_email"], parsed["subject"])

                logger.debug("Processing inbound email...")
                await process_inbound_email(parsed)
                logger.info("✓ Email processed successfully")

                logger.debug("Marking message as read...")
                mark_read = await client.post(
                    f"{GMAIL_BASE_URL}/messages/{message_id}/modify",
                    headers=headers,
                    json={"removeLabelIds": ["UNREAD"]},
                )
                mark_read.raise_for_status()
                logger.debug("✓ Message marked as read")

        return len(messages)

    def _parse_message(
        self, gmail_message: Dict[str, Any], gmail_message_id: str
    ) -> Dict[str, Any]:
        """Convert Gmail's raw RFC 5322 payload to Hermes' common email format."""
        raw = gmail_message.get("raw")
        if not raw:
            raise ValueError(f"Gmail message {gmail_message_id} has no raw payload")

        padded_raw = raw + "=" * (-len(raw) % 4)
        message = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(padded_raw)
        )
        sender = parseaddr(message.get("From", ""))[1]
        if not sender:
            raise ValueError(f"Gmail message {gmail_message_id} has no sender")

        text_body, html_body = self._get_bodies(message)
        references = self._parse_references(message.get("References", ""))
        message_id = message.get("Message-ID") or gmail_message_id

        return {
            "from_email": sender,
            "to_email": parseaddr(message.get("To", ""))[1] or self.settings.intake_email_address,
            "subject": message.get("Subject") or "(no subject)",
            "text_body": text_body,
            "html_body": html_body,
            "message_id": message_id,
            "in_reply_to": message.get("In-Reply-To"),
            "references": references,
            "raw_headers": str(message),
        }

    async def _get_access_token(self) -> str:
        """Refresh Gmail credentials and persist the updated OAuth data."""
        logger.debug("Retrieving Gmail token from database...")
        token_cache_value = await self.db.get_integration_token("gmail")
        if not token_cache_value and self.settings.gmail_token_cache:
            logger.debug("Token not in database, using GMAIL_TOKEN_CACHE from environment")
            token_cache_value = self.settings.gmail_token_cache
            await self.db.upsert_integration_token("gmail", token_cache_value)
            logger.debug("✓ Saved GMAIL_TOKEN_CACHE to database")

        if not token_cache_value:
            logger.error("✗ Gmail is not authorized - no token cache found")
            raise RuntimeError(
                "Gmail is not authorized. Add GMAIL_TOKEN_CACHE after running "
                "scripts/authorize_gmail.py."
            )

        try:
            logger.debug("Decoding OAuth credentials...")
            credentials_info = json.loads(base64.b64decode(token_cache_value).decode("utf-8"))
            credentials = Credentials.from_authorized_user_info(credentials_info, GMAIL_SCOPES)
            logger.debug("✓ OAuth credentials decoded successfully")
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error("✗ Invalid GMAIL_TOKEN_CACHE format")
            raise RuntimeError("GMAIL_TOKEN_CACHE is not valid OAuth credentials") from exc

        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                logger.error("✗ Gmail authorization expired and cannot be refreshed")
                raise RuntimeError(
                    "Gmail authorization expired; run scripts/authorize_gmail.py again"
                )
            logger.info("Token expired, refreshing...")
            await asyncio.to_thread(credentials.refresh, Request())
            logger.info("✓ Token refreshed successfully")

        logger.debug("Persisting updated token cache...")
        encoded_cache = base64.b64encode(credentials.to_json().encode("utf-8")).decode("ascii")
        await self.db.upsert_integration_token("gmail", encoded_cache)
        logger.debug("✓ Token cache persisted to database")

        if not credentials.token:
            logger.error("✗ No access token in credentials")
            raise RuntimeError("Gmail authorization did not return an access token")
        return credentials.token

    @staticmethod
    def _get_bodies(message: Any) -> tuple[str, str | None]:
        plain_parts: list[str] = []
        html_parts: list[str] = []
        parts = message.walk() if message.is_multipart() else [message]

        for part in parts:
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue
            content = part.get_content()
            if content_type == "text/plain":
                plain_parts.append(content)
            else:
                html_parts.append(content)

        text_body = "\n".join(plain_parts) or "\n".join(html_parts)
        return text_body, "\n".join(html_parts) or None

    @staticmethod
    def _parse_references(references_raw: str) -> list[str]:
        import re

        return re.findall(r"<([^>]+)>", references_raw)
