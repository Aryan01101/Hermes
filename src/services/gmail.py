"""Gmail API polling for a personal Gmail mailbox."""

import asyncio
import base64
from datetime import datetime, timezone
import json
import logging
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from typing import Any, Dict, Optional, Tuple

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.core.config import get_settings
from src.services.database import get_database
from src.services.inbound import process_inbound_email
from src.utils.errors import (
    log_circuit_breaker_opened,
    log_email_skipped,
    log_quota_pause,
)

logger = logging.getLogger(__name__)

GMAIL_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Skip emails from these patterns
SKIP_EMAIL_PATTERNS = [
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
    "@facebookmail.com",  # Birthday notifications
    "@linkedin.com",  # LinkedIn notifications
    "@twitter.com",  # Twitter notifications
    "@x.com",  # X (Twitter) notifications
    "notifications@",
    "bounce@",
    "mailer-daemon@",
    "postmaster@",
]


class GmailMailService:
    """Poll unread Inbox messages using delegated Gmail API access."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_database()

        # Circuit breaker state
        self.consecutive_failures = 0
        self.circuit_open_until: Optional[datetime] = None

    async def run(self) -> None:
        """Continuously poll the Inbox without bringing down the web process."""
        logger.info("Gmail polling started (interval: %ss)", self.settings.gmail_poll_interval_seconds)

        while True:
            try:
                # Check circuit breaker
                if self._is_circuit_open():
                    logger.warning("Circuit breaker is open, skipping poll")
                    await asyncio.sleep(self.settings.gmail_poll_interval_seconds)
                    continue

                # Check quotas before polling
                can_proceed, reason, quota_details = await self._check_quotas()
                if not can_proceed:
                    log_quota_pause(
                        quota_name=reason,
                        current_usage=quota_details.get("used", 0),
                        quota_limit=quota_details.get("limit", 0),
                    )
                    await asyncio.sleep(self.settings.gmail_poll_interval_seconds)
                    continue

                logger.info("Checking Gmail inbox for unread messages...")
                processed = await self.poll_inbox()
                if processed:
                    logger.info("✓ Processed %s Gmail message(s)", processed)
                    self._record_success()  # Reset failure counter
                else:
                    logger.info("No unread messages found in Gmail inbox")
            except asyncio.CancelledError:
                logger.info("Gmail polling cancelled")
                raise
            except Exception as e:
                logger.exception("✗ Gmail Inbox polling failed")
                self._record_failure()  # Track failure for circuit breaker

            await asyncio.sleep(self.settings.gmail_poll_interval_seconds)

    async def poll_inbox(self) -> int:
        """Process unread Inbox messages ONE AT A TIME, always marking as read."""
        logger.debug("Getting Gmail access token...")
        access_token = await self._get_access_token()
        logger.debug("✓ Access token obtained")

        headers = {"Authorization": f"Bearer {access_token}"}
        # Changed from maxResults=10 to maxResults=1 for sequential processing
        params = {"q": "in:inbox is:unread", "maxResults": "1"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            logger.debug("Querying Gmail API for unread messages...")
            response = await client.get(
                f"{GMAIL_BASE_URL}/messages", headers=headers, params=params
            )
            response.raise_for_status()
            messages = response.json().get("messages", [])

            if not messages:
                return 0

            logger.info("Found %s unread message(s) in Gmail inbox", len(messages))

            for idx, message in enumerate(messages, 1):
                message_id = message["id"]
                logger.info("[%s/%s] Processing Gmail message ID: %s", idx, len(messages), message_id)

                try:
                    logger.debug("Fetching raw message content...")
                    raw_message = await client.get(
                        f"{GMAIL_BASE_URL}/messages/{message_id}",
                        headers=headers,
                        params={"format": "raw"},
                    )
                    raw_message.raise_for_status()

                    parsed = self._parse_message(raw_message.json(), message_id)
                    logger.info("Email from: %s, subject: %s", parsed["from_email"], parsed["subject"])

                    # Check if email should be processed
                    should_process, skip_reason = self._should_process_email(
                        parsed["from_email"], parsed["subject"]
                    )

                    if not should_process:
                        log_email_skipped(
                            reason=skip_reason,
                            from_email=parsed["from_email"],
                            subject=parsed["subject"],
                            message_id=parsed["message_id"],
                        )
                        # Still mark as read to prevent retry
                        await self._mark_as_read(client, headers, message_id)
                        continue

                    logger.debug("Processing inbound email...")
                    await process_inbound_email(parsed)
                    logger.info("✓ Email processed successfully")

                    # Mark as read after successful processing
                    await self._mark_as_read(client, headers, message_id)

                except Exception as e:
                    logger.error(f"❌ Failed to process message {message_id}: {e}", exc_info=True)
                    # CRITICAL: Always mark as read to prevent retry loop
                    try:
                        await self._mark_as_read(client, headers, message_id)
                        logger.info("✓ Marked failed message as read to prevent retry")
                    except Exception as mark_error:
                        logger.error(f"❌ Failed to mark message as read: {mark_error}")
                    # Don't raise - continue to next message

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

    def _should_process_email(self, from_email: str, subject: str) -> Tuple[bool, str]:
        """
        Determine if email should be processed or skipped.

        Returns:
            (should_process, skip_reason)
        """
        from_email_lower = from_email.lower()

        # Check skip patterns
        for pattern in SKIP_EMAIL_PATTERNS:
            if pattern in from_email_lower:
                return False, f"Automated notification ({pattern})"

        # Check allowed domains (if configured)
        if self.settings.allowed_sender_domains:
            allowed_domains = [
                d.strip().lower()
                for d in self.settings.allowed_sender_domains.split(",")
            ]
            sender_domain = from_email_lower.split("@")[1] if "@" in from_email_lower else ""

            if sender_domain not in allowed_domains:
                return False, f"Domain not whitelisted ({sender_domain})"

        # Check allowed emails (if configured)
        if self.settings.allowed_sender_emails:
            allowed_emails = [
                e.strip().lower()
                for e in self.settings.allowed_sender_emails.split(",")
            ]

            if from_email_lower not in allowed_emails:
                return False, f"Email not whitelisted ({from_email_lower})"

        return True, "ok"

    async def _check_quotas(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if quotas allow processing.

        Returns:
            (can_proceed, reason, quota_details)
        """
        # Check Gemini quota if enabled
        if (
            self.settings.llm_provider == "gemini"
            and self.settings.gemini_enable_quota_tracking
        ):
            gemini_available = await self.db.check_gemini_quota_available()
            if not gemini_available:
                quota_status = await self.db.get_gemini_quota_status()
                return (
                    False,
                    "Gemini API",
                    {
                        "used": quota_status.get("request_count", 0),
                        "limit": self.settings.gemini_daily_request_limit,
                    },
                )

        # Check WhatsApp quota if enabled
        if self.settings.whatsapp_enable_quota_tracking:
            whatsapp_available = await self.db.check_whatsapp_quota_available()
            if not whatsapp_available:
                quota_status = await self.db.get_whatsapp_quota_status()
                return (
                    False,
                    "WhatsApp",
                    {
                        "used": quota_status.get("message_count", 0),
                        "limit": self.settings.twilio_daily_message_limit,
                    },
                )

        return True, "ok", {}

    async def _mark_as_read(
        self, client: httpx.AsyncClient, headers: Dict[str, str], message_id: str
    ) -> None:
        """Mark a Gmail message as read."""
        logger.debug("Marking message as read...")
        mark_read = await client.post(
            f"{GMAIL_BASE_URL}/messages/{message_id}/modify",
            headers=headers,
            json={"removeLabelIds": ["UNREAD"]},
        )
        mark_read.raise_for_status()
        logger.debug("✓ Message marked as read")

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.settings.circuit_breaker_enabled:
            return False

        if self.circuit_open_until:
            now = datetime.now(timezone.utc)
            if now < self.circuit_open_until:
                return True
            else:
                # Circuit breaker timeout expired, reset
                logger.info("Circuit breaker auto-reset after timeout")
                self.circuit_open_until = None
                self.consecutive_failures = 0
                return False

        return False

    def _record_success(self) -> None:
        """Record successful processing, reset circuit breaker."""
        self.consecutive_failures = 0
        self.circuit_open_until = None

    def _record_failure(self) -> None:
        """Record failure, potentially open circuit breaker."""
        if not self.settings.circuit_breaker_enabled:
            return

        self.consecutive_failures += 1

        if self.consecutive_failures >= self.settings.circuit_breaker_failure_threshold:
            # Open circuit breaker
            reset_timeout = self.settings.circuit_breaker_reset_timeout_minutes
            self.circuit_open_until = datetime.now(timezone.utc).replace(
                microsecond=0
            ) + __import__("datetime").timedelta(minutes=reset_timeout)

            log_circuit_breaker_opened(
                failure_count=self.consecutive_failures,
                reset_timeout_minutes=reset_timeout,
            )
            logger.error(
                f"Circuit breaker opened. Will reset at {self.circuit_open_until.isoformat()}"
            )
