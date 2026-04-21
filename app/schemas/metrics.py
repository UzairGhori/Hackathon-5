"""Pydantic schemas for metrics API responses."""

from pydantic import BaseModel


class ResponseTimeStats(BaseModel):
    total_runs: int
    avg_ms: float
    min_ms: int
    max_ms: int
    p50_ms: float
    p95_ms: float


class MessageCounts(BaseModel):
    total: int
    inbound: int
    outbound: int
    by_channel: dict[str, int]


class EscalationStats(BaseModel):
    total_runs: int
    escalated_count: int
    escalation_rate_pct: float
    by_category: dict[str, int]


class ResolutionRate(BaseModel):
    total_runs: int
    resolved_by_ai: int
    escalated: int
    ai_resolution_rate_pct: float


class ErrorRate(BaseModel):
    total_runs: int
    error_count: int
    error_rate_pct: float


class TokenUsage(BaseModel):
    total_runs: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    avg_tokens_input: float
    avg_tokens_output: float


class ChannelStats(BaseModel):
    total_runs: int
    avg_response_time_ms: float
    resolved_by_ai: int
    escalated: int
    resolution_rate_pct: float


class DashboardResponse(BaseModel):
    response_time: ResponseTimeStats
    messages: MessageCounts
    escalations: EscalationStats
    resolution: ResolutionRate
    errors: ErrorRate
    tokens: TokenUsage
    by_channel: dict[str, ChannelStats]
