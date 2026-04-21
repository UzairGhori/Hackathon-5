"""Load / throughput simulation — 1000 concurrent intake requests.

Two modes:

  1. **Mocked mode (default, offline)** — IntakeService.process is stubbed,
     so the test measures FastAPI + routing + serialization overhead only.
     This is what runs in CI. Target: < 2s total, 0 errors.

  2. **Integration mode** — set `LOAD_TEST_REAL=1` in the environment.
     Tests will hit http://localhost:8000 expecting Postgres + Kafka to
     be running (e.g. via `docker compose up`). Measures true end-to-end
     latency & throughput including DB writes and Kafka publishes.

You can also run this module as a script:

    python tests/test_load.py --count 1000 --concurrency 50 \\
        --url http://localhost:8000

This prints a full percentile report.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from app.db.models import ChannelType
from app.schemas.intake import IntakeResult


# ── Config ───────────────────────────────────────────────────

DEFAULT_COUNT = 1000
DEFAULT_CONCURRENCY = 50
DEFAULT_URL = "http://localhost:8000"


@dataclass
class LoadReport:
    count: int
    duration_s: float
    errors: int
    latencies_ms: list[float]

    @property
    def throughput_rps(self) -> float:
        return self.count / self.duration_s if self.duration_s else 0.0

    @property
    def success_rate(self) -> float:
        return (self.count - self.errors) / self.count if self.count else 0.0

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        k = max(0, min(len(sorted_lat) - 1, int(round((p / 100.0) * (len(sorted_lat) - 1)))))
        return sorted_lat[k]

    def pretty(self) -> str:
        return (
            f"\n── Load Test Report ─────────────────────────\n"
            f"  messages sent     : {self.count}\n"
            f"  duration          : {self.duration_s:.2f}s\n"
            f"  throughput        : {self.throughput_rps:.1f} req/s\n"
            f"  success rate      : {self.success_rate * 100:.2f}%\n"
            f"  errors            : {self.errors}\n"
            f"  latency p50       : {self.percentile(50):.1f} ms\n"
            f"  latency p90       : {self.percentile(90):.1f} ms\n"
            f"  latency p95       : {self.percentile(95):.1f} ms\n"
            f"  latency p99       : {self.percentile(99):.1f} ms\n"
            f"  latency max       : {max(self.latencies_ms, default=0):.1f} ms\n"
            f"  latency mean      : {statistics.fmean(self.latencies_ms) if self.latencies_ms else 0:.1f} ms\n"
            f"─────────────────────────────────────────────"
        )


# ── Payload generator ────────────────────────────────────────

def make_web_payload(i: int) -> dict[str, Any]:
    return {
        "name": f"LoadUser{i}",
        "email": f"load{i}@example.com",
        "subject": f"Load test subject {i}",
        "message": f"This is load test message number {i}. Please help.",
        "company": "LoadCo",
    }


def make_gmail_payload(i: int) -> dict[str, Any]:
    return {
        "message_id": f"load-gmail-{i}",
        "thread_id": f"thread-{i % 100}",
        "from_email": f"load{i}@example.com",
        "from_name": f"LoadUser{i}",
        "to_email": "support@company.com",
        "subject": f"Issue #{i}",
        "body_plain": f"Load test email body {i}",
    }


def make_whatsapp_payload(i: int) -> dict[str, Any]:
    return {
        "entry": [
            {
                "message_id": f"wa-{i}",
                "from_number": f"+1415555{i:04d}",
                "from_name": f"LoadUser{i}",
                "body": f"Load test whatsapp msg {i}",
                "message_type": "text",
            }
        ]
    }


CHANNEL_CYCLE = [
    ("/api/v1/channels/web", make_web_payload),
    ("/api/v1/channels/gmail", make_gmail_payload),
    ("/api/v1/channels/whatsapp", make_whatsapp_payload),
]


# ── Driver ───────────────────────────────────────────────────

async def _send_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    i: int,
    latencies: list[float],
    errors: list[int],
) -> None:
    path, builder = CHANNEL_CYCLE[i % len(CHANNEL_CYCLE)]
    payload = builder(i)
    async with semaphore:
        start = time.perf_counter()
        try:
            resp = await client.post(path, json=payload, timeout=30.0)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
            if resp.status_code != 200:
                errors.append(1)
        except Exception:
            latencies.append((time.perf_counter() - start) * 1000)
            errors.append(1)


async def run_load_test(
    client: httpx.AsyncClient,
    count: int = DEFAULT_COUNT,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> LoadReport:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    errors: list[int] = []

    wall_start = time.perf_counter()
    await asyncio.gather(
        *(_send_one(client, semaphore, i, latencies, errors) for i in range(count))
    )
    wall_duration = time.perf_counter() - wall_start

    return LoadReport(
        count=count,
        duration_s=wall_duration,
        errors=len(errors),
        latencies_ms=latencies,
    )


# ── Pytest: mocked load test (CI-safe) ───────────────────────

@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("LOAD_TEST_REAL") == "1",
    reason="Real integration mode requested — mocked test skipped.",
)
async def test_load_1000_messages_mocked(monkeypatch, mock_queue):
    """Fire 1000 requests at the in-process FastAPI app with a stubbed pipeline."""
    from app.services.intake_service import IntakeService
    from app.db.database import get_session
    from app.main import app
    from tests.conftest import FakeSession

    async def fake_process(self, msg):
        return IntakeResult(
            customer_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
            channel=msg.channel,
            is_new_customer=False,
            is_new_conversation=False,
        )

    async def fake_get_session():
        yield FakeSession()

    monkeypatch.setattr(IntakeService, "process", fake_process)
    app.dependency_overrides[get_session] = fake_get_session

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            report = await run_load_test(client, count=1000, concurrency=50)
    finally:
        app.dependency_overrides.clear()

    print(report.pretty())

    assert report.count == 1000
    assert report.errors == 0, f"got {report.errors} failed requests"
    assert report.success_rate == 1.0
    # Mocked pipeline should easily handle 1k in-process requests
    assert report.duration_s < 30.0
    assert report.percentile(99) < 5000.0  # p99 < 5s is very generous


# ── Pytest: integration load test (opt-in) ───────────────────

@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("LOAD_TEST_REAL") != "1",
    reason="Set LOAD_TEST_REAL=1 to run against a live stack.",
)
async def test_load_1000_messages_real():
    """Fire 1000 requests at a running stack (docker compose / k8s port-forward)."""
    url = os.getenv("LOAD_TEST_URL", DEFAULT_URL)
    async with httpx.AsyncClient(base_url=url) as client:
        report = await run_load_test(client, count=1000, concurrency=50)

    print(report.pretty())
    assert report.success_rate >= 0.99, f"success rate too low: {report.success_rate}"


# ── Script entry point ───────────────────────────────────────

async def _main() -> None:
    parser = argparse.ArgumentParser(description="Customer Success load tester")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=args.url) as client:
        report = await run_load_test(client, args.count, args.concurrency)
    print(report.pretty())


if __name__ == "__main__":
    asyncio.run(_main())
