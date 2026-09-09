"""Microsoft Graph polling for a personal Outlook mailbox."""

import asyncio
import base64
import logging
from typing import Any, Dict
from urllib.parse import quote

import httpx
import msal

from src.core.config import get_settings
from src.services.database import get_database
from src.services.inbound import process_inbound_email

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
OUTLOOK_SCOPES = ["Mail.ReadWrite", "User.Read", "offline_access"]


class OutlookMailService:
    """Poll unread Inbox messages using delegated Microsoft Graph access."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_database()

    async def run(self) -> None:
        """Continuously poll the Inbox without bringing down the web process."""
        while True:
            try:
                processed = await self.poll_inbox()
                if processed:
                    logger.info("Processed %s Outlook message(s)", processed)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outlook Inbox polling failed")

            await asyncio.sleep(self.settings.outlook_poll_interval_seconds)

    async def poll_inbox(self) -> int:
        """Process each unread Inbox message, then mark it read on success."""
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Prefer": 'outlook.body-content-type="text"',
        }
        params = {
            "$filter": "isRead eq false",
            "$select": "id,internetMessageId,subject,body,bodyPreview,from,receivedDateTime",
            "$top": "10",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messages",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            messages = response.json().get("value", [])

            for message in messages:
                parsed_email = await self._parse_message(client, headers, message)
                await process_inbound_email(parsed_email)

                mark_read = await client.patch(
                    f"{GRAPH_BASE_URL}/me/messages/{quote(message['id'], safe='')}",
                    headers=headers,
                    json={"isRead": True},
                )
                mark_read.raise_for_status()

        return len(messages)

    async def _parse_message(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Convert a Graph message into Hermes' common inbound-email format."""
        sender = message.get("from", {}).get("emailAddress", {}).get("address")
        if not sender:
            raise ValueError(f"Outlook message {message.get('id')} has no sender")

        response = await client.get(
            f"{GRAPH_BASE_URL}/me/messages/{quote(message['id'], safe='')}",
            headers=headers,
            params={"$select": "internetMessageHeaders"},
        )
        response.raise_for_status()
        raw_headers = response.json().get("internetMessageHeaders", [])
        header_map = {
            item["name"].lower(): item["value"]
            for item in raw_headers
            if item.get("name") and item.get("value")
        }

        references = self._parse_references(header_map.get("references", ""))
        message_id = message.get("internetMessageId") or message["id"]
        body = message.get("body", {}).get("content") or message.get("bodyPreview", "")

        return {
            "from_email": sender,
            "to_email": self.settings.intake_email_address,
            "subject": message.get("subject") or "(no subject)",
            "text_body": body,
            "html_body": None,
            "message_id": message_id,
            "in_reply_to": header_map.get("in-reply-to"),
            "references": references,
            "raw_headers": "\n".join(
                f"{item['name']}: {item['value']}" for item in raw_headers
            ),
        }

    async def _get_access_token(self) -> str:
        """Refresh a delegated Graph token and persist the updated MSAL cache."""
        token_cache_value = await self.db.get_integration_token("outlook")
        if not token_cache_value and self.settings.outlook_token_cache:
            token_cache_value = self.settings.outlook_token_cache
            await self.db.upsert_integration_token("outlook", token_cache_value)

        if not token_cache_value:
            raise RuntimeError(
                "Outlook is not authorized. Add OUTLOOK_TOKEN_CACHE after running "
                "scripts/authorize_outlook.py."
            )

        token_cache = msal.SerializableTokenCache()
        token_cache.deserialize(base64.b64decode(token_cache_value).decode("utf-8"))
        app = msal.PublicClientApplication(
            self.settings.outlook_client_id,
            authority="https://login.microsoftonline.com/consumers",
            token_cache=token_cache,
        )
        accounts = app.get_accounts()
        if not accounts:
            raise RuntimeError("Outlook token cache does not contain an authorized account")

        token = app.acquire_token_silent(OUTLOOK_SCOPES, account=accounts[0])
        if not token or "access_token" not in token:
            raise RuntimeError("Outlook authorization expired; run scripts/authorize_outlook.py again")

        if token_cache.has_state_changed:
            encoded_cache = base64.b64encode(
                token_cache.serialize().encode("utf-8")
            ).decode("ascii")
            await self.db.upsert_integration_token("outlook", encoded_cache)

        return token["access_token"]

    @staticmethod
    def _parse_references(references_raw: str) -> list[str]:
        """Extract RFC 5322 message IDs from a References header."""
        import re

        return re.findall(r"<([^>]+)>", references_raw)
