"""API intake tests.

Verifies each channel intake endpoint:
  - Accepts valid payloads
  - Rejects invalid payloads with 422
  - Publishes exactly one event to the Kafka queue

The intake pipeline (CustomerService / ConversationService) is patched
to skip the real database so this file runs without Postgres.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.db.models import ChannelType
from app.schemas.intake import IntakeResult


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────

def _fake_intake_result(channel: ChannelType) -> IntakeResult:
    return IntakeResult(
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        channel=channel,
        is_new_customer=True,
        is_new_conversation=True,
    )


@pytest.fixture
def patched_intake(monkeypatch):
    """Stub IntakeService.process so handlers return quickly without a DB."""
    from app.services.intake_service import IntakeService

    async def fake_process(self, msg):
        return _fake_intake_result(msg.channel)

    monkeypatch.setattr(IntakeService, "process", fake_process)

    # get_session yields a FakeSession so the Depends() works
    from app.db.database import get_session
    from tests.conftest import FakeSession
    from app.main import app

    async def fake_get_session():
        yield FakeSession()

    app.dependency_overrides[get_session] = fake_get_session
    yield
    app.dependency_overrides.clear()


# ── Health endpoints ─────────────────────────────────────────

async def test_liveness(async_client, patched_intake):
    resp = await async_client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readiness(async_client, patched_intake, monkeypatch):
    # Patch session.execute used by readiness probe
    from tests.conftest import FakeResult, FakeSession

    async def fake_execute(self, *a, **kw):
        return FakeResult(1)

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    resp = await async_client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"


# ── Web channel ──────────────────────────────────────────────

async def test_web_intake_success(async_client, patched_intake):
    payload = {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "subject": "Cannot log in",
        "message": "I keep getting 'invalid password' even after reset.",
        "company": "Acme Inc",
    }
    resp = await async_client.post("/api/v1/channels/web", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel"] == "web"
    assert uuid.UUID(data["customer_id"])
    assert uuid.UUID(data["conversation_id"])
    assert uuid.UUID(data["message_id"])


async def test_web_intake_rejects_missing_email(async_client, patched_intake):
    resp = await async_client.post(
        "/api/v1/channels/web",
        json={"name": "Alice", "subject": "x", "message": "y"},
    )
    assert resp.status_code == 422


async def test_web_intake_rejects_bad_email(async_client, patched_intake):
    resp = await async_client.post(
        "/api/v1/channels/web",
        json={
            "name": "Alice",
            "email": "not-an-email",
            "subject": "x",
            "message": "y",
        },
    )
    assert resp.status_code == 422


# ── Gmail channel ────────────────────────────────────────────

async def test_gmail_intake_success(async_client, patched_intake):
    payload = {
        "message_id": "gmail-msg-42",
        "thread_id": "thread-7",
        "from_email": "bob@example.com",
        "from_name": "Bob",
        "to_email": "support@company.com",
        "subject": "Refund request",
        "body_plain": "I want my money back.",
    }
    resp = await async_client.post("/api/v1/channels/gmail", json=payload)
    assert resp.status_code == 200
    assert resp.json()["channel"] == "gmail"


async def test_gmail_rejects_empty_body(async_client, patched_intake):
    resp = await async_client.post(
        "/api/v1/channels/gmail",
        json={
            "message_id": "x",
            "from_email": "a@b.co",
            "to_email": "c@d.co",
            "body_plain": "",  # fails min_length
        },
    )
    assert resp.status_code == 422


# ── WhatsApp channel ─────────────────────────────────────────

async def test_whatsapp_intake_success(async_client, patched_intake):
    payload = {
        "entry": [
            {
                "message_id": "wa-99",
                "from_number": "+14155551234",
                "from_name": "Carol",
                "body": "Is my order shipped?",
                "message_type": "text",
            }
        ]
    }
    resp = await async_client.post("/api/v1/channels/whatsapp", json=payload)
    assert resp.status_code == 200
    assert resp.json()["channel"] == "whatsapp"


async def test_whatsapp_rejects_bad_number(async_client, patched_intake):
    resp = await async_client.post(
        "/api/v1/channels/whatsapp",
        json={
            "entry": [
                {"message_id": "x", "from_number": "not-a-number", "body": "hi"}
            ]
        },
    )
    assert resp.status_code == 422


# ── Queue publishing is triggered via a real intake pipeline ─

async def test_intake_service_publishes_to_queue(monkeypatch, mock_queue):
    """Bypass the API layer — verify IntakeService publishes exactly once."""
    from app.schemas.intake import NormalizedMessage
    from app.services.intake_service import IntakeService

    svc = IntakeService(session=None)  # type: ignore[arg-type]

    fake_customer = type("C", (), {"id": uuid.uuid4()})()
    fake_conv = type("Cv", (), {"id": uuid.uuid4()})()
    fake_msg = type("M", (), {"id": uuid.uuid4()})()

    svc.customer_svc.find_or_create = AsyncMock(return_value=(fake_customer, True))  # type: ignore[assignment]
    svc.conversation_svc.find_or_create = AsyncMock(return_value=(fake_conv, True))  # type: ignore[assignment]
    svc.conversation_svc.add_message = AsyncMock(return_value=fake_msg)  # type: ignore[assignment]

    normalized = NormalizedMessage(
        channel=ChannelType.WEB,
        customer_name="Test User",
        customer_identifier="t@example.com",
        subject="subj",
        content="hello",
    )
    result = await svc.process(normalized)

    assert result.customer_id == fake_customer.id
    assert mock_queue.call_count == 1
