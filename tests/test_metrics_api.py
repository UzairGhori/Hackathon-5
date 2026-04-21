"""Metrics API tests.

Covers every endpoint in `app/api/metrics.py`:
  GET /api/v1/metrics/dashboard
  GET /api/v1/metrics/response-time
  GET /api/v1/metrics/messages
  GET /api/v1/metrics/escalations
  GET /api/v1/metrics/resolution-rate
  GET /api/v1/metrics/errors
  GET /api/v1/metrics/tokens
  GET /api/v1/metrics/channels

`MetricsService` is monkey-patched at the import site so the endpoints are
exercised end-to-end (including Pydantic serialization) without touching
Postgres. The `hours` query parameter is also verified to flow through.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


pytestmark = pytest.mark.asyncio


# ── Fixtures ─────────────────────────────────────────────────

SAMPLE_RESPONSE_TIME = {
    "total_runs": 120,
    "avg_ms": 842.5,
    "min_ms": 150,
    "max_ms": 4200,
    "p50_ms": 710.0,
    "p95_ms": 2100.5,
}

SAMPLE_MESSAGES = {
    "total": 900,
    "inbound": 450,
    "outbound": 450,
    "by_channel": {"web": 400, "gmail": 300, "whatsapp": 200},
}

SAMPLE_ESCALATIONS = {
    "total_runs": 120,
    "escalated_count": 18,
    "escalation_rate_pct": 15.0,
    "by_category": {"refund_request": 10, "legal_issue": 3, "angry_customer": 5},
}

SAMPLE_RESOLUTION = {
    "total_runs": 120,
    "resolved_by_ai": 102,
    "escalated": 18,
    "ai_resolution_rate_pct": 85.0,
}

SAMPLE_ERRORS = {
    "total_runs": 120,
    "error_count": 3,
    "error_rate_pct": 2.5,
}

SAMPLE_TOKENS = {
    "total_runs": 120,
    "total_tokens_input": 36000,
    "total_tokens_output": 18000,
    "total_tokens": 54000,
    "avg_tokens_input": 300.0,
    "avg_tokens_output": 150.0,
}

SAMPLE_CHANNELS = {
    "web": {
        "total_runs": 60,
        "avg_response_time_ms": 700.0,
        "resolved_by_ai": 55,
        "escalated": 5,
        "resolution_rate_pct": 91.7,
    },
    "gmail": {
        "total_runs": 40,
        "avg_response_time_ms": 950.0,
        "resolved_by_ai": 32,
        "escalated": 8,
        "resolution_rate_pct": 80.0,
    },
    "whatsapp": {
        "total_runs": 20,
        "avg_response_time_ms": 620.0,
        "resolved_by_ai": 15,
        "escalated": 5,
        "resolution_rate_pct": 75.0,
    },
}


@pytest.fixture
def patch_metrics_api(monkeypatch):
    """Replace MetricsService used by api.metrics with an AsyncMock per method."""
    from app.api import metrics as metrics_mod
    from app.db.database import get_session
    from app.main import app
    from tests.conftest import FakeSession

    svc = SimpleNamespace(
        response_time_stats=AsyncMock(return_value=SAMPLE_RESPONSE_TIME),
        message_counts=AsyncMock(return_value=SAMPLE_MESSAGES),
        escalation_stats=AsyncMock(return_value=SAMPLE_ESCALATIONS),
        resolution_rate=AsyncMock(return_value=SAMPLE_RESOLUTION),
        error_rate=AsyncMock(return_value=SAMPLE_ERRORS),
        token_usage=AsyncMock(return_value=SAMPLE_TOKENS),
        channel_breakdown=AsyncMock(return_value=SAMPLE_CHANNELS),
        dashboard=AsyncMock(
            return_value={
                "response_time": SAMPLE_RESPONSE_TIME,
                "messages": SAMPLE_MESSAGES,
                "escalations": SAMPLE_ESCALATIONS,
                "resolution": SAMPLE_RESOLUTION,
                "errors": SAMPLE_ERRORS,
                "tokens": SAMPLE_TOKENS,
                "by_channel": SAMPLE_CHANNELS,
            }
        ),
    )

    class StubMetricsService:
        def __init__(self, session):
            self.session = session

        def __getattr__(self, name):
            return getattr(svc, name)

    monkeypatch.setattr(metrics_mod, "MetricsService", StubMetricsService)

    async def fake_get_session():
        yield FakeSession()

    app.dependency_overrides[get_session] = fake_get_session
    try:
        yield svc
    finally:
        app.dependency_overrides.clear()


# ── Individual KPI endpoints ─────────────────────────────────

async def test_response_time(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/response-time")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_runs"] == 120
    assert body["p95_ms"] == 2100.5
    patch_metrics_api.response_time_stats.assert_awaited_once()
    # No hours query → since is None
    assert patch_metrics_api.response_time_stats.await_args.args[0] is None


async def test_response_time_with_hours_filter(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/response-time?hours=24")
    assert resp.status_code == 200
    since_arg = patch_metrics_api.response_time_stats.await_args.args[0]
    # _since(24) should return a datetime roughly 24h ago
    assert isinstance(since_arg, datetime)
    delta = datetime.now(timezone.utc) - since_arg
    assert timedelta(hours=23, minutes=58) <= delta <= timedelta(hours=24, minutes=2)


async def test_messages_counts(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 900
    assert body["by_channel"]["web"] == 400
    assert body["by_channel"]["whatsapp"] == 200


async def test_escalations(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/escalations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalation_rate_pct"] == 15.0
    assert body["by_category"]["refund_request"] == 10


async def test_resolution_rate(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/resolution-rate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_resolution_rate_pct"] == 85.0
    assert body["escalated"] == 18


async def test_errors(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/errors")
    assert resp.status_code == 200
    assert resp.json()["error_rate_pct"] == 2.5


async def test_tokens(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/tokens")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tokens"] == 54000
    assert body["avg_tokens_input"] == 300.0


async def test_channels_breakdown(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/channels")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"web", "gmail", "whatsapp"}
    assert body["web"]["resolution_rate_pct"] == 91.7
    assert body["gmail"]["total_runs"] == 40


# ── Full dashboard ───────────────────────────────────────────

async def test_dashboard(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert "response_time" in body
    assert "messages" in body
    assert "escalations" in body
    assert "resolution" in body
    assert "errors" in body
    assert "tokens" in body
    assert "by_channel" in body
    assert body["response_time"]["total_runs"] == 120
    assert body["by_channel"]["web"]["total_runs"] == 60


async def test_dashboard_with_hours(async_client, patch_metrics_api):
    resp = await async_client.get("/api/v1/metrics/dashboard?hours=6")
    assert resp.status_code == 200
    since_arg = patch_metrics_api.dashboard.await_args.args[0]
    delta = datetime.now(timezone.utc) - since_arg
    assert timedelta(hours=5, minutes=58) <= delta <= timedelta(hours=6, minutes=2)
