"""Idempotency tests.

These tests document and lock down the system's behaviour around duplicate
delivery of the same logical customer message. Two failure modes exist:

  1. **Intake-layer duplication** — a channel webhook (Gmail/WhatsApp) may
     deliver the same `channel_message_id` twice. To be idempotent, intake
     must dedupe on `(channel, channel_message_id)`.

  2. **Worker-layer duplication** — Kafka offers at-least-once delivery, so
     the same internal `message_id` can be redelivered if a worker crashes
     between `session.commit()` and `consumer.commit()`. To be idempotent,
     the worker must track processed message_ids (or derive idempotency
     from an upsert on `outbound Message(source_message_id)`).

**Current state of the codebase (as of this test file):**

  - `Message.channel_message_id` is **indexed** but **not unique-constrained**
    (see `database/schema.sql:95` — a plain btree index, not `UNIQUE`).
  - `ConversationService.add_message` performs no pre-insert lookup.
  - `worker.process_message` loads a `Message` by internal UUID and calls
    `run_agent` unconditionally — no check for "already processed".

So **neither layer is idempotent today**. The tests below are structured as:

  - `test_intake_current_behavior_is_non_idempotent`     → passes, baseline
  - `test_worker_current_behavior_is_non_idempotent`     → passes, baseline
  - `test_intake_should_dedupe_by_channel_message_id`    → xfail (TODO)
  - `test_worker_should_be_idempotent_on_redelivery`     → xfail (TODO)

When the production code is fixed, flip the two xfail tests to pass and
remove the baseline tests (or convert them to describe the new behaviour).
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import ChannelType, Message, MessageDirection, MessageSender


pytestmark = pytest.mark.asyncio


# ══════════════════════════════════════════════════════════════
# 1. Intake-layer idempotency
# ══════════════════════════════════════════════════════════════


async def test_intake_current_behavior_is_non_idempotent(db_session):
    """Baseline: replaying the same channel_message_id twice creates TWO rows.

    This test locks down the current (non-idempotent) behaviour so a future
    fix is visible as a failing test that must be updated intentionally.
    """
    from app.services.conversation_service import ConversationService

    svc = ConversationService(db_session)

    conv_id = uuid.uuid4()

    m1 = await svc.add_message(
        conversation_id=conv_id,
        channel=ChannelType.GMAIL,
        content="Hello",
        channel_message_id="gmail-duplicate-id",
    )
    m2 = await svc.add_message(
        conversation_id=conv_id,
        channel=ChannelType.GMAIL,
        content="Hello",  # identical payload
        channel_message_id="gmail-duplicate-id",
    )

    messages = [o for o in db_session.added if isinstance(o, Message)]
    # Current behaviour: TWO rows — no dedupe.
    assert len(messages) == 2
    assert m1 is not m2
    assert m1.id != m2.id


@pytest.mark.xfail(
    reason="channel_message_id has no UNIQUE constraint in schema.sql; "
    "intake does not dedupe on replay. Fix: add "
    "UNIQUE(channel, channel_message_id) + upsert in add_message.",
    strict=True,
)
async def test_intake_should_dedupe_by_channel_message_id(db_session):
    """Desired behaviour: replaying the same channel_message_id is a no-op.

    When this test goes from xfail → pass (after the fix), flip it to a
    regular test and delete the baseline above.
    """
    from app.services.conversation_service import ConversationService

    svc = ConversationService(db_session)
    conv_id = uuid.uuid4()

    await svc.add_message(
        conversation_id=conv_id,
        channel=ChannelType.GMAIL,
        content="Hello",
        channel_message_id="gmail-duplicate-id",
    )
    await svc.add_message(
        conversation_id=conv_id,
        channel=ChannelType.GMAIL,
        content="Hello",
        channel_message_id="gmail-duplicate-id",
    )

    messages = [o for o in db_session.added if isinstance(o, Message)]
    assert len(messages) == 1, "expected exactly one row after dedupe"


# ══════════════════════════════════════════════════════════════
# 2. Worker-layer idempotency (Kafka redelivery)
# ══════════════════════════════════════════════════════════════


def _payload(message_id: uuid.UUID) -> bytes:
    return json.dumps(
        {
            "customer_id": str(uuid.uuid4()),
            "conversation_id": str(uuid.uuid4()),
            "message_id": str(message_id),
            "channel": "web",
            "is_new_customer": False,
            "is_new_conversation": False,
        }
    ).encode()


class _SessionCM:
    def __init__(self, s):
        self.s = s

    async def __aenter__(self):
        return self.s

    async def __aexit__(self, *a):
        return False


@pytest.fixture
def patched_worker(monkeypatch):
    """Shared plumbing for worker idempotency tests."""
    from tests.conftest import FakeResult, FakeSession
    from app.workers import worker as worker_mod

    fake_row = MagicMock(content="Same inbound content")

    async def fake_execute(self, *a, **kw):
        return FakeResult(fake_row)

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    sessions: list[FakeSession] = []

    def factory():
        s = FakeSession()
        sessions.append(s)
        return _SessionCM(s)

    monkeypatch.setattr(worker_mod, "async_session_factory", factory)
    return SimpleNamespace(sessions=sessions, worker_mod=worker_mod)


async def test_worker_current_behavior_is_non_idempotent(patched_worker, monkeypatch):
    """Baseline: redelivering the same message_id runs the agent twice.

    Locks down the current (non-idempotent) behaviour. `run_agent` is called
    once per delivery — there is no "already processed" short-circuit.
    """
    worker_mod = patched_worker.worker_mod

    calls: list[uuid.UUID] = []

    async def stub_run_agent(**kwargs):
        calls.append(kwargs["message_id"])
        return "ok"

    monkeypatch.setattr(worker_mod, "run_agent", stub_run_agent)

    mid = uuid.uuid4()
    await worker_mod.process_message(_payload(mid))
    await worker_mod.process_message(_payload(mid))  # Kafka replay

    # Current behaviour: agent invoked TWICE for the same logical message.
    assert calls == [mid, mid]
    # Both sessions committed.
    assert all(s.committed for s in patched_worker.sessions)


@pytest.mark.xfail(
    reason="Worker does not track processed message_ids; a Kafka replay "
    "re-runs the agent. Fix: add a processed_messages table or a "
    "`processed_at` column on messages + SELECT ... FOR UPDATE SKIP LOCKED.",
    strict=True,
)
async def test_worker_should_be_idempotent_on_redelivery(patched_worker, monkeypatch):
    """Desired behaviour: redelivery of the same message_id is a no-op."""
    worker_mod = patched_worker.worker_mod

    calls: list[uuid.UUID] = []

    async def stub_run_agent(**kwargs):
        calls.append(kwargs["message_id"])
        return "ok"

    monkeypatch.setattr(worker_mod, "run_agent", stub_run_agent)

    mid = uuid.uuid4()
    await worker_mod.process_message(_payload(mid))
    await worker_mod.process_message(_payload(mid))  # replay

    assert calls == [mid], "agent should run exactly once per logical message"


# ══════════════════════════════════════════════════════════════
# 3. Distinct message_ids are always processed independently
# ══════════════════════════════════════════════════════════════


async def test_worker_processes_distinct_messages_independently(
    patched_worker, monkeypatch
):
    """Sanity: two different message_ids always run the agent twice."""
    worker_mod = patched_worker.worker_mod

    calls: list[uuid.UUID] = []

    async def stub_run_agent(**kwargs):
        calls.append(kwargs["message_id"])
        return "ok"

    monkeypatch.setattr(worker_mod, "run_agent", stub_run_agent)

    m1 = uuid.uuid4()
    m2 = uuid.uuid4()
    await worker_mod.process_message(_payload(m1))
    await worker_mod.process_message(_payload(m2))

    assert calls == [m1, m2]
    assert len(patched_worker.sessions) == 2
