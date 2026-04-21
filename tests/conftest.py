"""Shared pytest fixtures for the Customer Success test suite.

Provides:
  - `async_client`    — httpx.AsyncClient bound to the FastAPI app with
                         the queue service stubbed out so tests run without Kafka.
  - `mock_queue`      — MagicMock used to replace QueueService.enqueue_message.
  - `db_session`      — in-memory-style transactional AsyncSession (rolled back).
  - `stub_run_agent`  — monkeypatched Runner.run that returns a scripted
                         agent response, avoiding real OpenAI calls.
  - `fake_consumer`   — AIOKafkaConsumer replacement that yields a fixed
                         list of canned messages.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ── Event loop ───────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Queue service stub ───────────────────────────────────────

@pytest_asyncio.fixture
async def mock_queue(monkeypatch) -> AsyncMock:
    """Replace QueueService.enqueue_message with an AsyncMock.

    Tests can assert on `mock_queue.call_count` or
    inspect `mock_queue.call_args_list` to verify events were published.
    """
    from app.services.queue_service import QueueService

    enqueue = AsyncMock(return_value=None)
    start = AsyncMock(return_value=None)
    stop = AsyncMock(return_value=None)

    monkeypatch.setattr(QueueService, "enqueue_message", enqueue)
    monkeypatch.setattr(QueueService, "start", start)
    monkeypatch.setattr(QueueService, "stop", stop)
    return enqueue


# ── FastAPI client ───────────────────────────────────────────

@pytest_asyncio.fixture
async def async_client(mock_queue) -> AsyncIterator[AsyncClient]:
    """ASGI-backed AsyncClient — no real HTTP port is opened."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Fake DB session ──────────────────────────────────────────

class FakeResult:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value

    def scalars(self) -> "FakeResult":
        return self

    def all(self) -> list[Any]:
        return list(self._value) if isinstance(self._value, Iterable) else []


class FakeSession:
    """A minimal AsyncSession substitute for unit tests.

    - `add()` records instances into `self.added`
    - `execute()` returns whatever `next_result` is preloaded with, OR
       pops the next result from `results_queue` if one is configured
    - `commit` / `rollback` / `flush` / `close` are no-ops

    `queue(value)` — set a single result to be returned by every execute()
    `queue_many([v1, v2, ...])` — return each value in order for sequential
        execute() calls (useful for services that do multiple queries per call).
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.next_result: Any = None
        self.results_queue: list[FakeResult] = []
        self.execute_calls: int = 0

    def queue(self, value: Any) -> None:
        self.next_result = FakeResult(value)

    def queue_many(self, values: list[Any]) -> None:
        """Preload a FIFO queue of results for sequential execute() calls."""
        self.results_queue = [FakeResult(v) for v in values]

    async def execute(self, *args, **kwargs) -> FakeResult:
        self.execute_calls += 1
        if self.results_queue:
            return self.results_queue.pop(0)
        return self.next_result or FakeResult()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        pass

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()


@pytest.fixture
def db_session() -> FakeSession:
    return FakeSession()


# ── Agent Runner stub ────────────────────────────────────────

@dataclass
class FakeUsage:
    input_tokens: int = 120
    output_tokens: int = 60


@dataclass
class FakeRawResponse:
    usage: FakeUsage = field(default_factory=FakeUsage)


@dataclass
class FakeAgentResult:
    final_output: str = "Hello! Thanks for reaching out. I'd be happy to help."
    raw_responses: list[FakeRawResponse] = field(
        default_factory=lambda: [FakeRawResponse()]
    )


@pytest_asyncio.fixture
async def stub_run_agent(monkeypatch) -> AsyncMock:
    """Replace OpenAI Runner.run so agent tests run offline."""
    from agents import Runner

    fake = AsyncMock(return_value=FakeAgentResult())
    monkeypatch.setattr(Runner, "run", fake)
    return fake


# ── Kafka consumer stub ──────────────────────────────────────

class FakeKafkaMessage:
    def __init__(self, value: bytes, key: bytes | None = None) -> None:
        self.topic = "customer_messages"
        self.partition = 0
        self.offset = 0
        self.key = key
        self.value = value


class FakeKafkaConsumer:
    """Replaces AIOKafkaConsumer with an iterable of canned messages."""

    def __init__(self, *args, messages: list[FakeKafkaMessage] | None = None, **kwargs) -> None:
        self._messages = messages or []
        self.started = False
        self.stopped = False
        self.commits = 0

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def commit(self) -> None:
        self.commits += 1

    def __aiter__(self):
        self._iter = iter(self._messages)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def make_kafka_message(
    customer_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    channel: str = "web",
) -> FakeKafkaMessage:
    payload = {
        "customer_id": str(customer_id or uuid.uuid4()),
        "conversation_id": str(conversation_id or uuid.uuid4()),
        "message_id": str(message_id or uuid.uuid4()),
        "channel": channel,
        "is_new_customer": False,
        "is_new_conversation": False,
    }
    return FakeKafkaMessage(
        value=json.dumps(payload).encode("utf-8"),
        key=payload["conversation_id"].encode("utf-8"),
    )
