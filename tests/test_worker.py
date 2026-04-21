"""Worker / Kafka consumer tests.

Covers `app.workers.worker.process_message`:
  - deserializes the Kafka payload
  - loads the inbound Message from DB
  - calls run_agent with the right arguments
  - commits the session on success
  - rolls back and records an error metric on failure
  - skips gracefully when the message is not found
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def _payload_bytes(channel: str = "web") -> bytes:
    return json.dumps(
        {
            "customer_id": str(uuid.uuid4()),
            "conversation_id": str(uuid.uuid4()),
            "message_id": str(uuid.uuid4()),
            "channel": channel,
            "is_new_customer": False,
            "is_new_conversation": False,
        }
    ).encode("utf-8")


class _SessionCM:
    """Async context manager wrapping a single FakeSession."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_):
        return False


@pytest.fixture
def patch_session_factory(monkeypatch):
    """Replace async_session_factory with one that returns a pre-made FakeSession."""
    from tests.conftest import FakeSession
    from app.workers import worker as worker_mod

    sessions: list[FakeSession] = []

    def factory():
        s = FakeSession()
        sessions.append(s)
        return _SessionCM(s)

    monkeypatch.setattr(worker_mod, "async_session_factory", factory)
    return sessions


async def test_process_message_happy_path(monkeypatch, patch_session_factory):
    """End-to-end: valid payload → agent runs → session committed."""
    from app.workers import worker as worker_mod

    # Preload the fake session to "find" a Message row
    fake_message = MagicMock()
    fake_message.content = "Hi, I cannot log in."

    # Patch run_agent
    run_agent_mock = AsyncMock(return_value="Sure, let's fix that.")
    monkeypatch.setattr(worker_mod, "run_agent", run_agent_mock)

    raw = _payload_bytes("web")

    # Inject the Message into the session that will be created inside process_message
    # Because session is created inside the function, we patch FakeSession.execute globally
    from tests.conftest import FakeResult, FakeSession

    async def fake_execute(self, *a, **kw):
        return FakeResult(fake_message)

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    await worker_mod.process_message(raw)

    assert run_agent_mock.call_count == 1
    called_kwargs = run_agent_mock.call_args.kwargs
    assert called_kwargs["customer_message"] == "Hi, I cannot log in."
    assert str(called_kwargs["customer_id"])

    # The session was committed
    assert patch_session_factory[0].committed is True
    assert patch_session_factory[0].rolled_back is False


async def test_process_message_missing_row(monkeypatch, patch_session_factory):
    """Message not found in DB → agent NOT called, early return."""
    from app.workers import worker as worker_mod
    from tests.conftest import FakeResult, FakeSession

    async def fake_execute(self, *a, **kw):
        return FakeResult(None)  # simulate row missing

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    run_agent_mock = AsyncMock()
    monkeypatch.setattr(worker_mod, "run_agent", run_agent_mock)

    await worker_mod.process_message(_payload_bytes())

    assert run_agent_mock.call_count == 0


async def test_process_message_agent_failure_is_caught(
    monkeypatch, patch_session_factory
):
    """If run_agent raises, the session is rolled back and an error metric is recorded."""
    from app.workers import worker as worker_mod
    from tests.conftest import FakeResult, FakeSession

    fake_message = MagicMock()
    fake_message.content = "Whatever"

    async def fake_execute(self, *a, **kw):
        return FakeResult(fake_message)

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    run_agent_mock = AsyncMock(side_effect=RuntimeError("agent blew up"))
    monkeypatch.setattr(worker_mod, "run_agent", run_agent_mock)

    # Must not raise — the worker catches exceptions
    await worker_mod.process_message(_payload_bytes())

    # Primary session rolled back
    assert patch_session_factory[0].rolled_back is True
    # Secondary (error-metric) session committed
    assert len(patch_session_factory) >= 2
    assert patch_session_factory[1].committed is True


async def test_process_message_parses_channel(monkeypatch, patch_session_factory):
    """Each supported channel value must deserialize cleanly."""
    from app.workers import worker as worker_mod
    from app.db.models import ChannelType
    from tests.conftest import FakeResult, FakeSession

    fake_message = MagicMock(content="hi")

    async def fake_execute(self, *a, **kw):
        return FakeResult(fake_message)

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    seen_channels = []

    async def fake_run_agent(**kwargs):
        seen_channels.append(kwargs["channel"])
        return "ok"

    monkeypatch.setattr(worker_mod, "run_agent", fake_run_agent)

    for ch in ("web", "gmail", "whatsapp"):
        await worker_mod.process_message(_payload_bytes(ch))

    assert seen_channels == [
        ChannelType.WEB,
        ChannelType.GMAIL,
        ChannelType.WHATSAPP,
    ]
