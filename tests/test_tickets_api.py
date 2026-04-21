"""Tickets API tests.

Covers every endpoint in `app/api/tickets.py`:
  GET    /api/v1/tickets                  list (+ filter by status)
  GET    /api/v1/tickets/escalated        list escalated
  GET    /api/v1/tickets/{id}             get by id (+ 404)
  GET    /api/v1/tickets/{id}/events      audit trail (+ 404)
  PATCH  /api/v1/tickets/{id}/status      transition (+ 404 + 422)
  PATCH  /api/v1/tickets/{id}/assign      assign (+ 404)
  POST   /api/v1/tickets/{id}/resolve     resolve (+ 404 + 422)
  POST   /api/v1/tickets/{id}/close       close (+ 404 + 422)

The real Postgres layer is not touched. `TicketService` is monkey-patched
at import time inside `app.api.tickets`, and `get_session` is overridden
with a FakeSession so the Depends() plumbing still works.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.models import (
    ChannelType,
    TicketEventType,
    TicketPriority,
    TicketStatus,
)


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────

def _fake_ticket(
    *,
    status: TicketStatus = TicketStatus.OPEN,
    priority: TicketPriority = TicketPriority.MEDIUM,
    assigned_to: str | None = "ai_agent",
    tags: list[str] | None = None,
) -> SimpleNamespace:
    """Build a duck-typed Ticket that `_ticket_to_response` can serialize."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        subject="Cannot reset password",
        description="Reset link 404s",
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        tags=tags or [],
        created_at=now,
        updated_at=now,
        resolved_at=None,
        closed_at=None,
    )


def _fake_event(
    ticket_id: uuid.UUID,
    event_type: TicketEventType = TicketEventType.CREATED,
    actor: str = "ai_agent",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        ticket_id=ticket_id,
        event_type=event_type,
        actor=actor,
        old_value=None,
        new_value={"status": "open"},
        note="initial",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def patch_tickets_api(monkeypatch):
    """Override get_session + monkeypatch TicketService inside api.tickets.

    Yields a MagicMock-like instance whose attributes are the async methods
    the endpoint layer calls. Each test preloads return values / side effects.
    """
    from app.api import tickets as tickets_mod
    from app.db.database import get_session
    from app.main import app
    from tests.conftest import FakeSession

    svc = SimpleNamespace(
        get_by_id=AsyncMock(),
        list_by_status=AsyncMock(),
        list_escalated=AsyncMock(),
        transition_status=AsyncMock(),
        assign=AsyncMock(),
        resolve=AsyncMock(),
        close=AsyncMock(),
        get_events=AsyncMock(),
    )

    class StubTicketService:
        def __init__(self, session):
            self.session = session

        def __getattr__(self, name):
            return getattr(svc, name)

    monkeypatch.setattr(tickets_mod, "TicketService", StubTicketService)

    async def fake_get_session():
        yield FakeSession()

    app.dependency_overrides[get_session] = fake_get_session
    try:
        yield svc
    finally:
        app.dependency_overrides.clear()


# ── GET /api/v1/tickets ──────────────────────────────────────

async def test_list_tickets_by_status(async_client, patch_tickets_api):
    t1 = _fake_ticket(status=TicketStatus.OPEN)
    t2 = _fake_ticket(status=TicketStatus.OPEN)
    patch_tickets_api.list_by_status.return_value = [t1, t2]

    resp = await async_client.get("/api/v1/tickets?status=open&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {row["id"] for row in body} == {str(t1.id), str(t2.id)}
    assert body[0]["status"] == "open"
    patch_tickets_api.list_by_status.assert_awaited_once_with(
        TicketStatus.OPEN, 10
    )


async def test_list_tickets_rejects_invalid_status(async_client, patch_tickets_api):
    resp = await async_client.get("/api/v1/tickets?status=bogus")
    assert resp.status_code == 400
    assert "Invalid status" in resp.json()["detail"]


async def test_list_tickets_without_filter_uses_raw_query(
    async_client, patch_tickets_api, monkeypatch
):
    """Unfiltered listing goes through a direct SELECT — we stub session.execute."""
    from tests.conftest import FakeSession

    tickets = [_fake_ticket(), _fake_ticket(), _fake_ticket()]

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return tickets

    async def fake_execute(self, *a, **kw):
        return _Result()

    monkeypatch.setattr(FakeSession, "execute", fake_execute)

    resp = await async_client.get("/api/v1/tickets?limit=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ── GET /api/v1/tickets/escalated ────────────────────────────

async def test_list_escalated(async_client, patch_tickets_api):
    escalated = _fake_ticket(
        status=TicketStatus.ESCALATED,
        priority=TicketPriority.HIGH,
        tags=["refund_request"],
    )
    patch_tickets_api.list_escalated.return_value = [escalated]

    resp = await async_client.get("/api/v1/tickets/escalated?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "escalated"
    assert body[0]["priority"] == "high"
    assert "refund_request" in body[0]["tags"]
    patch_tickets_api.list_escalated.assert_awaited_once_with(5)


# ── GET /api/v1/tickets/{id} ─────────────────────────────────

async def test_get_ticket_by_id(async_client, patch_tickets_api):
    t = _fake_ticket()
    patch_tickets_api.get_by_id.return_value = t

    resp = await async_client.get(f"/api/v1/tickets/{t.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(t.id)


async def test_get_ticket_not_found(async_client, patch_tickets_api):
    patch_tickets_api.get_by_id.return_value = None

    resp = await async_client.get(f"/api/v1/tickets/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Ticket not found"


# ── GET /api/v1/tickets/{id}/events ──────────────────────────

async def test_get_ticket_events(async_client, patch_tickets_api):
    t = _fake_ticket()
    patch_tickets_api.get_by_id.return_value = t
    patch_tickets_api.get_events.return_value = [
        _fake_event(t.id, TicketEventType.CREATED),
        _fake_event(t.id, TicketEventType.ASSIGNED, actor="agent@co"),
    ]

    resp = await async_client.get(f"/api/v1/tickets/{t.id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2
    assert events[0]["event_type"] == "created"
    assert events[1]["event_type"] == "assigned"
    assert events[1]["actor"] == "agent@co"


async def test_get_ticket_events_not_found(async_client, patch_tickets_api):
    patch_tickets_api.get_by_id.return_value = None
    resp = await async_client.get(f"/api/v1/tickets/{uuid.uuid4()}/events")
    assert resp.status_code == 404


# ── PATCH /api/v1/tickets/{id}/status ────────────────────────

async def test_update_ticket_status(async_client, patch_tickets_api):
    t = _fake_ticket(status=TicketStatus.OPEN)
    patch_tickets_api.get_by_id.return_value = t

    in_progress = _fake_ticket(status=TicketStatus.IN_PROGRESS)
    in_progress.id = t.id
    patch_tickets_api.transition_status.return_value = in_progress

    resp = await async_client.patch(
        f"/api/v1/tickets/{t.id}/status",
        json={"status": "in_progress", "actor": "agent@co", "note": "picking up"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    patch_tickets_api.transition_status.assert_awaited_once()
    kwargs = patch_tickets_api.transition_status.await_args
    assert kwargs.args[1] == TicketStatus.IN_PROGRESS
    assert kwargs.args[2] == "agent@co"
    assert kwargs.args[3] == "picking up"


async def test_update_ticket_status_rejects_invalid_status(
    async_client, patch_tickets_api
):
    t = _fake_ticket()
    patch_tickets_api.get_by_id.return_value = t

    resp = await async_client.patch(
        f"/api/v1/tickets/{t.id}/status",
        json={"status": "bogus", "actor": "agent@co"},
    )
    assert resp.status_code == 400


async def test_update_ticket_status_rejects_invalid_transition(
    async_client, patch_tickets_api
):
    t = _fake_ticket(status=TicketStatus.CLOSED)
    patch_tickets_api.get_by_id.return_value = t
    patch_tickets_api.transition_status.side_effect = ValueError(
        "Invalid transition: closed → in_progress"
    )

    resp = await async_client.patch(
        f"/api/v1/tickets/{t.id}/status",
        json={"status": "in_progress", "actor": "agent@co"},
    )
    assert resp.status_code == 422
    assert "Invalid transition" in resp.json()["detail"]


async def test_update_ticket_status_not_found(async_client, patch_tickets_api):
    patch_tickets_api.get_by_id.return_value = None
    resp = await async_client.patch(
        f"/api/v1/tickets/{uuid.uuid4()}/status",
        json={"status": "in_progress", "actor": "agent@co"},
    )
    assert resp.status_code == 404


# ── PATCH /api/v1/tickets/{id}/assign ────────────────────────

async def test_assign_ticket(async_client, patch_tickets_api):
    t = _fake_ticket(status=TicketStatus.ESCALATED, assigned_to="human_queue")
    patch_tickets_api.get_by_id.return_value = t

    assigned = _fake_ticket(
        status=TicketStatus.IN_PROGRESS, assigned_to="agent@co"
    )
    assigned.id = t.id
    patch_tickets_api.assign.return_value = assigned

    resp = await async_client.patch(
        f"/api/v1/tickets/{t.id}/assign",
        json={"assigned_to": "agent@co", "actor": "supervisor@co"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assigned_to"] == "agent@co"
    assert body["status"] == "in_progress"
    patch_tickets_api.assign.assert_awaited_once_with(
        t.id, "agent@co", "supervisor@co"
    )


async def test_assign_ticket_not_found(async_client, patch_tickets_api):
    patch_tickets_api.get_by_id.return_value = None
    resp = await async_client.patch(
        f"/api/v1/tickets/{uuid.uuid4()}/assign",
        json={"assigned_to": "a", "actor": "b"},
    )
    assert resp.status_code == 404


async def test_assign_ticket_rejects_empty_body(async_client, patch_tickets_api):
    t = _fake_ticket()
    patch_tickets_api.get_by_id.return_value = t
    resp = await async_client.patch(
        f"/api/v1/tickets/{t.id}/assign",
        json={"assigned_to": "", "actor": ""},
    )
    assert resp.status_code == 422


# ── POST /api/v1/tickets/{id}/resolve ────────────────────────

async def test_resolve_ticket(async_client, patch_tickets_api):
    t = _fake_ticket(status=TicketStatus.IN_PROGRESS)
    patch_tickets_api.get_by_id.return_value = t

    resolved = _fake_ticket(status=TicketStatus.RESOLVED)
    resolved.id = t.id
    resolved.resolved_at = datetime.now(timezone.utc)
    patch_tickets_api.resolve.return_value = resolved

    resp = await async_client.post(
        f"/api/v1/tickets/{t.id}/resolve",
        json={"status": "resolved", "actor": "agent@co", "note": "fixed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    patch_tickets_api.resolve.assert_awaited_once_with(
        t.id, "agent@co", "fixed"
    )


async def test_resolve_ticket_invalid_transition(async_client, patch_tickets_api):
    t = _fake_ticket(status=TicketStatus.CLOSED)
    patch_tickets_api.get_by_id.return_value = t
    patch_tickets_api.resolve.side_effect = ValueError(
        "Invalid transition: closed → resolved"
    )
    resp = await async_client.post(
        f"/api/v1/tickets/{t.id}/resolve",
        json={"status": "resolved", "actor": "agent@co"},
    )
    assert resp.status_code == 422


# ── POST /api/v1/tickets/{id}/close ──────────────────────────

async def test_close_ticket(async_client, patch_tickets_api):
    t = _fake_ticket(status=TicketStatus.RESOLVED)
    patch_tickets_api.get_by_id.return_value = t

    closed = _fake_ticket(status=TicketStatus.CLOSED)
    closed.id = t.id
    closed.closed_at = datetime.now(timezone.utc)
    patch_tickets_api.close.return_value = closed

    resp = await async_client.post(
        f"/api/v1/tickets/{t.id}/close",
        json={"status": "closed", "actor": "agent@co"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


async def test_close_ticket_not_found(async_client, patch_tickets_api):
    patch_tickets_api.get_by_id.return_value = None
    resp = await async_client.post(
        f"/api/v1/tickets/{uuid.uuid4()}/close",
        json={"status": "closed", "actor": "a"},
    )
    assert resp.status_code == 404
