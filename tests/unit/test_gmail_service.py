"""Unit tests for Gmail raw-message conversion."""

import base64
from types import SimpleNamespace

import pytest

from src.services.gmail import GmailMailService


@pytest.mark.unit
def test_gmail_message_converts_to_shared_inbound_format():
    raw_email = (
        b"From: Customer <customer@example.com>\r\n"
        b"To: support@example.com\r\n"
        b"Subject: Question\r\n"
        b"Message-ID: <current@example.com>\r\n"
        b"In-Reply-To: <prior@example.com>\r\n"
        b"References: <first@example.com> <prior@example.com>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Can you help me?\r\n"
    )
    service = object.__new__(GmailMailService)
    service.settings = SimpleNamespace(intake_email_address="fallback@example.com")

    parsed = service._parse_message(
        {"raw": base64.urlsafe_b64encode(raw_email).decode("ascii").rstrip("=")},
        "gmail-message-id",
    )

    assert parsed["from_email"] == "customer@example.com"
    assert parsed["to_email"] == "support@example.com"
    assert parsed["message_id"] == "<current@example.com>"
    assert parsed["in_reply_to"] == "<prior@example.com>"
    assert parsed["references"] == ["first@example.com", "prior@example.com"]
    assert parsed["text_body"] == "Can you help me?\r\n"
