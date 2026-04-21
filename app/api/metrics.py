"""Metrics API — dashboard endpoints for monitoring agent performance.

Provides:
  GET /api/v1/metrics/dashboard           — full dashboard (all KPIs)
  GET /api/v1/metrics/response-time       — response time stats
  GET /api/v1/metrics/messages            — message counts
  GET /api/v1/metrics/escalations         — escalation stats
  GET /api/v1/metrics/resolution-rate     — AI resolution rate
  GET /api/v1/metrics/errors              — error rate
  GET /api/v1/metrics/tokens              — token usage
  GET /api/v1/metrics/channels            — per-channel breakdown

All endpoints accept an optional `hours` query param to filter by time window.
"""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.schemas.metrics import (
    ChannelStats,
    DashboardResponse,
    ErrorRate,
    EscalationStats,
    MessageCounts,
    ResolutionRate,
    ResponseTimeStats,
    TokenUsage,
)
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


def _since(hours: int | None) -> datetime | None:
    """Convert an `hours` query param to a datetime cutoff."""
    if hours is None:
        return None
    return datetime.now(timezone.utc) - timedelta(hours=hours)


# ── Full Dashboard ───────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    hours: int | None = Query(None, description="Filter to last N hours"),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Full metrics dashboard — all KPIs in a single call."""
    svc = MetricsService(session)
    data = await svc.dashboard(_since(hours))
    return DashboardResponse(**data)


# ── Individual KPIs ──────────────────────────────────────────

@router.get("/response-time", response_model=ResponseTimeStats)
async def response_time(
    hours: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> ResponseTimeStats:
    """Response time statistics (avg, p50, p95, max)."""
    svc = MetricsService(session)
    return ResponseTimeStats(**(await svc.response_time_stats(_since(hours))))


@router.get("/messages", response_model=MessageCounts)
async def messages(
    hours: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> MessageCounts:
    """Message counts — total, inbound, outbound, by channel."""
    svc = MetricsService(session)
    return MessageCounts(**(await svc.message_counts(_since(hours))))


@router.get("/escalations", response_model=EscalationStats)
async def escalations(
    hours: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> EscalationStats:
    """Escalation stats — count, rate, and breakdown by category."""
    svc = MetricsService(session)
    return EscalationStats(**(await svc.escalation_stats(_since(hours))))


@router.get("/resolution-rate", response_model=ResolutionRate)
async def resolution_rate(
    hours: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> ResolutionRate:
    """AI resolution rate — % resolved without human handoff."""
    svc = MetricsService(session)
    return ResolutionRate(**(await svc.resolution_rate(_since(hours))))


@router.get("/errors", response_model=ErrorRate)
async def errors(
    hours: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> ErrorRate:
    """Error rate — % of agent runs that failed."""
    svc = MetricsService(session)
    return ErrorRate(**(await svc.error_rate(_since(hours))))


@router.get("/tokens", response_model=TokenUsage)
async def tokens(
    hours: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> TokenUsage:
    """Token consumption — total and average per run."""
    svc = MetricsService(session)
    return TokenUsage(**(await svc.token_usage(_since(hours))))


@router.get("/channels", response_model=dict[str, ChannelStats])
async def channels(
    hours: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, ChannelStats]:
    """Per-channel performance breakdown."""
    svc = MetricsService(session)
    data = await svc.channel_breakdown(_since(hours))
    return {k: ChannelStats(**v) for k, v in data.items()}
