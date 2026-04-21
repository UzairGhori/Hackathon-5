"""Metrics service — aggregate queries against agent_metrics, messages, and tickets.

Computes the five core KPIs:
  1. Response time   — avg, p50, p95, max (ms)
  2. Message count   — total inbound, outbound, by channel
  3. Escalation count — total, by category, escalation rate
  4. AI resolution rate — % resolved without human handoff
  5. Error rate      — % of agent runs that failed
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, case, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    AgentMetric,
    ChannelType,
    Message,
    MessageDirection,
    Ticket,
    TicketStatus,
)

logger = get_logger(__name__)


class MetricsService:
    """Computes aggregate metrics from the agent_metrics table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 1. Response Time ─────────────────────────────────────

    async def response_time_stats(
        self,
        since: datetime | None = None,
        channel: ChannelType | None = None,
    ) -> dict:
        """Average, p50, p95, and max response time in milliseconds."""
        filters = [AgentMetric.response_time_ms.isnot(None)]
        if since:
            filters.append(AgentMetric.created_at >= since)
        if channel:
            filters.append(AgentMetric.channel == channel)

        result = await self.session.execute(
            select(
                func.count(AgentMetric.id).label("total"),
                func.avg(AgentMetric.response_time_ms).label("avg_ms"),
                func.min(AgentMetric.response_time_ms).label("min_ms"),
                func.max(AgentMetric.response_time_ms).label("max_ms"),
                func.percentile_cont(0.5).within_group(
                    AgentMetric.response_time_ms
                ).label("p50_ms"),
                func.percentile_cont(0.95).within_group(
                    AgentMetric.response_time_ms
                ).label("p95_ms"),
            ).where(and_(*filters))
        )
        row = result.one()
        return {
            "total_runs": row.total or 0,
            "avg_ms": round(row.avg_ms, 1) if row.avg_ms else 0,
            "min_ms": row.min_ms or 0,
            "max_ms": row.max_ms or 0,
            "p50_ms": round(row.p50_ms, 1) if row.p50_ms else 0,
            "p95_ms": round(row.p95_ms, 1) if row.p95_ms else 0,
        }

    # ── 2. Message Count ─────────────────────────────────────

    async def message_counts(
        self,
        since: datetime | None = None,
    ) -> dict:
        """Total inbound and outbound messages, broken down by channel."""
        filters = []
        if since:
            filters.append(Message.created_at >= since)

        # Totals
        result = await self.session.execute(
            select(
                func.count(Message.id).label("total"),
                func.count(Message.id).filter(
                    Message.direction == MessageDirection.INBOUND
                ).label("inbound"),
                func.count(Message.id).filter(
                    Message.direction == MessageDirection.OUTBOUND
                ).label("outbound"),
            ).where(and_(*filters)) if filters else
            select(
                func.count(Message.id).label("total"),
                func.count(Message.id).filter(
                    Message.direction == MessageDirection.INBOUND
                ).label("inbound"),
                func.count(Message.id).filter(
                    Message.direction == MessageDirection.OUTBOUND
                ).label("outbound"),
            )
        )
        totals = result.one()

        # By channel
        channel_filters = []
        if since:
            channel_filters.append(Message.created_at >= since)

        by_channel_query = (
            select(
                Message.channel,
                func.count(Message.id).label("count"),
            )
            .group_by(Message.channel)
        )
        if channel_filters:
            by_channel_query = by_channel_query.where(and_(*channel_filters))

        result = await self.session.execute(by_channel_query)
        by_channel = {row.channel.value: row.count for row in result.all()}

        return {
            "total": totals.total or 0,
            "inbound": totals.inbound or 0,
            "outbound": totals.outbound or 0,
            "by_channel": by_channel,
        }

    # ── 3. Escalation Count ──────────────────────────────────

    async def escalation_stats(
        self,
        since: datetime | None = None,
    ) -> dict:
        """Total escalations, escalation rate, and breakdown by category."""
        filters = []
        if since:
            filters.append(AgentMetric.created_at >= since)

        # Total runs vs escalated runs
        result = await self.session.execute(
            select(
                func.count(AgentMetric.id).label("total_runs"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.escalated.is_(True)
                ).label("escalated_count"),
            ).where(and_(*filters)) if filters else
            select(
                func.count(AgentMetric.id).label("total_runs"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.escalated.is_(True)
                ).label("escalated_count"),
            )
        )
        row = result.one()
        total = row.total_runs or 0
        escalated = row.escalated_count or 0
        rate = round((escalated / total) * 100, 1) if total > 0 else 0

        # Breakdown by escalation category (from ticket tags)
        ticket_filters = [Ticket.status == TicketStatus.ESCALATED]
        if since:
            ticket_filters.append(Ticket.created_at >= since)

        result = await self.session.execute(
            select(
                func.unnest(Ticket.tags).label("tag"),
                func.count().label("count"),
            )
            .where(and_(*ticket_filters))
            .group_by(text("tag"))
            .order_by(text("count DESC"))
        )
        by_category = {row.tag: row.count for row in result.all()}

        return {
            "total_runs": total,
            "escalated_count": escalated,
            "escalation_rate_pct": rate,
            "by_category": by_category,
        }

    # ── 4. AI Resolution Rate ────────────────────────────────

    async def resolution_rate(
        self,
        since: datetime | None = None,
    ) -> dict:
        """Percentage of conversations resolved by AI without escalation."""
        filters = []
        if since:
            filters.append(AgentMetric.created_at >= since)

        result = await self.session.execute(
            select(
                func.count(AgentMetric.id).label("total_runs"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.resolved_by_ai.is_(True)
                ).label("resolved_by_ai"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.escalated.is_(True)
                ).label("escalated"),
            ).where(and_(*filters)) if filters else
            select(
                func.count(AgentMetric.id).label("total_runs"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.resolved_by_ai.is_(True)
                ).label("resolved_by_ai"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.escalated.is_(True)
                ).label("escalated"),
            )
        )
        row = result.one()
        total = row.total_runs or 0
        resolved = row.resolved_by_ai or 0
        rate = round((resolved / total) * 100, 1) if total > 0 else 0

        return {
            "total_runs": total,
            "resolved_by_ai": resolved,
            "escalated": row.escalated or 0,
            "ai_resolution_rate_pct": rate,
        }

    # ── 5. Error Rate ────────────────────────────────────────

    async def error_rate(
        self,
        since: datetime | None = None,
    ) -> dict:
        """Percentage of agent runs that resulted in errors."""
        filters = []
        if since:
            filters.append(AgentMetric.created_at >= since)

        result = await self.session.execute(
            select(
                func.count(AgentMetric.id).label("total"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.metadata_["error"].as_boolean().is_(True)
                ).label("errors"),
            ).where(and_(*filters)) if filters else
            select(
                func.count(AgentMetric.id).label("total"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.metadata_["error"].as_boolean().is_(True)
                ).label("errors"),
            )
        )
        row = result.one()
        total = row.total or 0
        errors = row.errors or 0
        rate = round((errors / total) * 100, 1) if total > 0 else 0

        return {
            "total_runs": total,
            "error_count": errors,
            "error_rate_pct": rate,
        }

    # ── Token Usage ──────────────────────────────────────────

    async def token_usage(
        self,
        since: datetime | None = None,
    ) -> dict:
        """Total and average token consumption."""
        filters = []
        if since:
            filters.append(AgentMetric.created_at >= since)

        result = await self.session.execute(
            select(
                func.count(AgentMetric.id).label("total_runs"),
                func.sum(AgentMetric.tokens_input).label("total_input"),
                func.sum(AgentMetric.tokens_output).label("total_output"),
                func.avg(AgentMetric.tokens_input).label("avg_input"),
                func.avg(AgentMetric.tokens_output).label("avg_output"),
            ).where(and_(*filters)) if filters else
            select(
                func.count(AgentMetric.id).label("total_runs"),
                func.sum(AgentMetric.tokens_input).label("total_input"),
                func.sum(AgentMetric.tokens_output).label("total_output"),
                func.avg(AgentMetric.tokens_input).label("avg_input"),
                func.avg(AgentMetric.tokens_output).label("avg_output"),
            )
        )
        row = result.one()
        total_in = row.total_input or 0
        total_out = row.total_output or 0

        return {
            "total_runs": row.total_runs or 0,
            "total_tokens_input": total_in,
            "total_tokens_output": total_out,
            "total_tokens": total_in + total_out,
            "avg_tokens_input": round(row.avg_input, 1) if row.avg_input else 0,
            "avg_tokens_output": round(row.avg_output, 1) if row.avg_output else 0,
        }

    # ── Channel Breakdown ────────────────────────────────────

    async def channel_breakdown(
        self,
        since: datetime | None = None,
    ) -> dict:
        """Agent runs broken down by channel."""
        filters = []
        if since:
            filters.append(AgentMetric.created_at >= since)

        query = (
            select(
                AgentMetric.channel,
                func.count(AgentMetric.id).label("total"),
                func.avg(AgentMetric.response_time_ms).label("avg_ms"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.resolved_by_ai.is_(True)
                ).label("resolved"),
                func.count(AgentMetric.id).filter(
                    AgentMetric.escalated.is_(True)
                ).label("escalated"),
            )
            .group_by(AgentMetric.channel)
        )
        if filters:
            query = query.where(and_(*filters))

        result = await self.session.execute(query)
        breakdown = {}
        for row in result.all():
            total = row.total or 0
            breakdown[row.channel.value] = {
                "total_runs": total,
                "avg_response_time_ms": round(row.avg_ms, 1) if row.avg_ms else 0,
                "resolved_by_ai": row.resolved or 0,
                "escalated": row.escalated or 0,
                "resolution_rate_pct": (
                    round(((row.resolved or 0) / total) * 100, 1) if total > 0 else 0
                ),
            }
        return breakdown

    # ── Full Dashboard ───────────────────────────────────────

    async def dashboard(
        self,
        since: datetime | None = None,
    ) -> dict:
        """All metrics combined into a single dashboard response."""
        return {
            "response_time": await self.response_time_stats(since),
            "messages": await self.message_counts(since),
            "escalations": await self.escalation_stats(since),
            "resolution": await self.resolution_rate(since),
            "errors": await self.error_rate(since),
            "tokens": await self.token_usage(since),
            "by_channel": await self.channel_breakdown(since),
        }
