"""Unit tests for Microsoft Graph message conversion."""

from types import SimpleNamespace

import pytest

from src.services.outlook import OutlookMailService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    async def get(self, *_args, **_kwargs):
        return FakeResponse(
            {
                "internetMessageHeaders": [
                    {"name": "In-Reply-To", "value": "<prior@example.com>"},
                    {
                        "name": "References",
                        "value": "<first@example.com> <prior@example.com>",
                    },
                ]
            }
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_graph_message_converts_to_shared_inbound_format():
    service = object.__new__(OutlookMailService)
    service.settings = SimpleNamespace(intake_email_address="aadhikari678@outlook.com")

    parsed = await service._parse_message(
        FakeClient(),
        {"Authorization": "Bearer token"},
        {
            "id": "graph-message-id",
            "internetMessageId": "<current@example.com>",
            "subject": "Question",
            "body": {"content": "Can you help me?"},
            "from": {"emailAddress": {"address": "customer@example.com"}},
        },
    )

    assert parsed["from_email"] == "customer@example.com"
    assert parsed["message_id"] == "<current@example.com>"
    assert parsed["in_reply_to"] == "<prior@example.com>"
    assert parsed["references"] == ["first@example.com", "prior@example.com"]
    assert parsed["text_body"] == "Can you help me?"
