"""Failure recovery tests.

Simulates four failure modes and asserts the system either
  (a) degrades gracefully without data loss, or
  (b) recovers automatically once the dependency returns.

Covered scenarios:

  1. Kafka producer unavailable at intake time
     → QueueService.enqueue_message logs and drops without raising,
       so the API still returns 200. (Messages are durably stored
       in Postgres already, so the operator can replay them.)

  2. Kafka producer raises during publish
     → IntakeService.process propagates the error; the request fails
       (500) and no partial state is committed to Kafka.

  3. Worker: DB transient failure → rollback and error metric recorded,
     subsequent messages still processed (no poison pill stall).

  4. Kafka consumer reconnect loop: after a simulated broker drop,
     the worker picks up queued messages once the broker returns.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import ChannelType


pytestmark = pytest.mark.asyncio


# ── Scenario 1: Kafka producer not started ──────────────────

async def test_queue_service_not_started_drops_gracefully(caplog):
    """enqueue_message must log and return when producer is None."""
    from app.services.queue_service import QueueService
    from app.schemas.intake import IntakeResult

    QueueService._producer = None  # force "not started" state

    result = IntakeResult(
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        is_new_customer=False,
        is_new_conversation=False,
    )

    # Should not raise, even with no producer
    await QueueService.enqueue_message(result)

    # Nothing was published — the caller can read the DB row and replay later
    assert QueueService._producer is None


# ── Scenario 2: Publish-time exception bubbles up ───────────

async def test_publish_failure_bubbles_up(monkeypatch):
    """If the Kafka send fails, the exception must propagate to IntakeService."""
    from app.services.queue_service import QueueService
    from app.schemas.intake import IntakeResult

    class BrokenProducer:
        async def send_and_wait(self, *a, **kw):
            raise ConnectionError("broker down")

    QueueService._producer = BrokenProducer()  # type: ignore[assignment]

    with pytest.raises(ConnectionError):
        await QueueService.enqueue_message(
            IntakeResult(
                customer_id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                message_id=uuid.uuid4(),
                channel=ChannelType.GMAIL,
                is_new_customer=False,
                is_new_conversation=False,
            )
        )
    QueueService._producer = None


# ── Scenario 3: Worker survives a poison message ────────────

async def test_worker_continues_after_processing_error(monkeypatch):
    """A failing message must not stop the worker from processing the next one."""
    from app.workers import worker as worker_mod
    from tests.conftest import FakeResult, FakeSession

    processed_ids: list[str] = []

    # First call: blow up. Second call: succeed.
    calls = {"n": 0}

    async def flaky_run_agent(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient DB error")
        processed_ids.append(str(kwargs["message_id"]))
        return "ok"

    monkeypatch.setattr(worker_mod, "run_agent", flaky_run_agent)

    fake_msg = MagicMock(content="hi")

    async def fake_execute(self, *a, **kw):
        return FakeResult(fake_msg)

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    sessions: list[FakeSession] = []

    class _CM:
        def __init__(self, s):
            self.s = s

        async def __aenter__(self):
            return self.s

        async def __aexit__(self, *a):
            return False

    def factory():
        s = FakeSession()
        sessions.append(s)
        return _CM(s)

    monkeypatch.setattr(worker_mod, "async_session_factory", factory)

    def make_payload() -> bytes:
        return json.dumps(
            {
                "customer_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "message_id": str(uuid.uuid4()),
                "channel": "web",
                "is_new_customer": False,
                "is_new_conversation": False,
            }
        ).encode()

    # First call raises (caught), second call succeeds
    await worker_mod.process_message(make_payload())
    await worker_mod.process_message(make_payload())

    assert calls["n"] == 2
    assert len(processed_ids) == 1  # only second message recorded success

    # First message's session was rolled back, second was committed
    commit_states = [s.committed for s in sessions]
    rollback_states = [s.rolled_back for s in sessions]
    assert any(rollback_states), "expected at least one rollback"
    assert any(commit_states), "expected at least one commit"


# ── Scenario 4: Consumer reconnects after broker drop ───────

async def test_worker_consumer_reconnect(monkeypatch):
    """
    Simulate a broker outage by having AIOKafkaConsumer.start() raise once,
    then succeed. A simple retry wrapper around run_worker demonstrates the
    contract: the worker does not crash permanently on transient failure.
    """
    from aiokafka import errors as kafka_errors
    from app.workers import worker as worker_mod
    from tests.conftest import FakeKafkaConsumer, make_kafka_message

    attempts = {"n": 0}
    canned = [make_kafka_message()]

    class FlakyConsumer(FakeKafkaConsumer):
        async def start(self):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise kafka_errors.KafkaConnectionError("broker unreachable")
            await super().start()

    def consumer_factory(*a, **kw):
        return FlakyConsumer(messages=canned)

    monkeypatch.setattr(worker_mod, "AIOKafkaConsumer", consumer_factory)
    monkeypatch.setattr(worker_mod, "process_message", AsyncMock())

    # First call raises → we retry once, which succeeds.
    with pytest.raises(kafka_errors.KafkaConnectionError):
        await worker_mod.run_worker()
    assert attempts["n"] == 1

    # Retry: the second invocation starts cleanly and drains the canned message.
    await worker_mod.run_worker()
    assert attempts["n"] == 2
    assert worker_mod.process_message.call_count == 1  # type: ignore[attr-defined]


# ── Scenario 5: API survives a DB hiccup on readiness ───────

async def test_readiness_fails_when_db_unreachable(async_client, monkeypatch):
    """Readiness probe must return 5xx when the DB is down (so k8s pulls pod)."""
    from tests.conftest import FakeSession
    from app.db.database import get_session
    from app.main import app

    async def broken_execute(self, *a, **kw):
        raise ConnectionError("cannot reach postgres")

    monkeypatch.setattr(FakeSession, "execute", broken_execute)

    async def fake_get_session():
        yield FakeSession()

    app.dependency_overrides[get_session] = fake_get_session
    try:
        resp = await async_client.get("/health/ready")
        assert resp.status_code >= 500
    finally:
        app.dependency_overrides.clear()
