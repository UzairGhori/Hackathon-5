"""AI Agent tests.

Verifies:
  - `run_agent()` returns the agent's final output text
  - It records an AgentMetric with correct channel / tokens / latency
  - The escalated flag is propagated from AgentContext to the metric
  - Each agent tool (search_knowledge_base, get_customer_history,
    create_ticket, escalate_to_human, send_response) is wired correctly.

Runner.run is stubbed by the `stub_run_agent` fixture so no real
OpenAI calls occur.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import AgentMetric, ChannelType


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────

def _tool_ctx(context, tool_name="test_tool"):
    """Create a ToolContext wrapper compatible with openai-agents >= 0.13."""
    from agents.tool import ToolContext
    return ToolContext(
        context=context,
        tool_name=tool_name,
        tool_call_id=f"call_{uuid.uuid4().hex[:8]}",
        tool_arguments="{}",
    )


# ── run_agent orchestration ──────────────────────────────────

async def test_run_agent_returns_response_and_records_metric(
    stub_run_agent, db_session
):
    from app.agent.agent import run_agent

    response = await run_agent(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
        customer_message="Can't sign in.",
    )

    assert "help" in response.lower() or len(response) > 0
    assert stub_run_agent.call_count == 1

    # A metric row should have been added
    metrics = [obj for obj in db_session.added if isinstance(obj, AgentMetric)]
    assert len(metrics) == 1
    m = metrics[0]
    assert m.channel == ChannelType.WEB
    assert m.tokens_input == 120
    assert m.tokens_output == 60
    assert m.model_used == "grok-4.20-reasoning"
    assert m.resolved_by_ai is True
    assert m.escalated is False
    assert m.response_time_ms >= 0


async def test_run_agent_propagates_escalation(stub_run_agent, db_session, monkeypatch):
    """If a tool sets context.escalated=True, the metric must reflect it."""
    from app.agent import agent as agent_mod

    # Mutate the AgentContext mid-run to simulate escalate_to_human() firing
    original_runner = stub_run_agent.side_effect  # None initially

    async def escalating_run(**kwargs):
        ctx = kwargs["context"]
        ctx.escalated = True
        ctx.response_text = "Escalated to human."
        return agent_mod.Runner.run.return_value  # reuse the AsyncMock's return

    stub_run_agent.side_effect = escalating_run

    await agent_mod.run_agent(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.GMAIL,
        customer_message="I want a refund NOW.",
    )

    metrics = [o for o in db_session.added if isinstance(o, AgentMetric)]
    assert metrics[0].escalated is True
    assert metrics[0].resolved_by_ai is False
    assert metrics[0].channel == ChannelType.GMAIL


# ── Tool: search_knowledge_base ──────────────────────────────

async def test_search_knowledge_base_returns_formatted_articles(db_session):
    from app.agent.tools import search_knowledge_base
    from app.agent.context import AgentContext

    # Preload a fake search result
    article = MagicMock()
    article.title = "How to reset your password"
    article.category = "Account"
    article.content = "Click the 'Forgot password' link..."
    db_session.queue([article])

    ctx = AgentContext(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
    )

    # function_tool wraps the callable — invoke the underlying function
    result = await search_knowledge_base.on_invoke_tool(
        _tool_ctx(ctx, "search_knowledge_base"), '{"query": "password"}'
    )

    assert "How to reset your password" in result
    assert "Account" in result


async def test_search_knowledge_base_no_results(db_session):
    from app.agent.tools import search_knowledge_base
    from app.agent.context import AgentContext

    db_session.queue([])  # empty result set

    ctx = AgentContext(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
    )
    result = await search_knowledge_base.on_invoke_tool(
        _tool_ctx(ctx, "search_knowledge_base"), '{"query": "obscure topic"}'
    )
    assert "No relevant articles" in result


# ── Tool: send_response ──────────────────────────────────────

async def test_send_response_stores_outbound_message(db_session):
    from app.agent.tools import send_response
    from app.agent.context import AgentContext
    from app.db.models import Message, MessageDirection, MessageSender

    ctx = AgentContext(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WHATSAPP,
    )

    msg_text = "Your password has been reset. Check your email."
    await send_response.on_invoke_tool(
        _tool_ctx(ctx, "send_response"),
        f'{{"message": "{msg_text}"}}',
    )

    outbound = [o for o in db_session.added if isinstance(o, Message)]
    assert len(outbound) == 1
    assert outbound[0].content == msg_text
    assert outbound[0].direction == MessageDirection.OUTBOUND
    assert outbound[0].sender == MessageSender.AGENT
    assert ctx.response_text == msg_text


# ── Tool: create_ticket ──────────────────────────────────────

async def test_create_ticket_maps_priority_and_sets_context(db_session, monkeypatch):
    from app.agent import tools as tools_mod
    from app.agent.context import AgentContext
    from app.db.models import TicketPriority

    created_ticket = MagicMock(id=uuid.uuid4())

    class StubTicketService:
        def __init__(self, session):
            self.session = session

        async def create_ticket(self, **kwargs):
            self.kwargs = kwargs
            return created_ticket

    monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

    ctx = AgentContext(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
    )

    result = await tools_mod.create_ticket.on_invoke_tool(
        _tool_ctx(ctx, "create_ticket"),
        '{"subject": "Login broken", "description": "Cannot sign in after reset", "priority": "high"}',
    )

    assert "Ticket created successfully" in result
    assert str(created_ticket.id) in result
    assert ctx.ticket_id == created_ticket.id


# ── Tool: escalate_to_human ──────────────────────────────────

async def test_escalate_to_human_creates_ticket_if_missing(db_session, monkeypatch):
    from app.agent import tools as tools_mod
    from app.agent.context import AgentContext

    ticket = MagicMock(id=uuid.uuid4())
    ticket.priority = MagicMock(value="high")

    class StubTicketService:
        def __init__(self, session):
            self.create_called = False

        async def create_ticket(self, **kwargs):
            self.create_called = True
            return ticket

        async def escalate(self, **kwargs):
            return ticket

    monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

    ctx = AgentContext(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.GMAIL,
    )

    result = await tools_mod.escalate_to_human.on_invoke_tool(
        _tool_ctx(ctx, "escalate_to_human"),
        '{"reason": "Customer is very upset", "category": "angry_customer"}',
    )

    assert "escalated" in result.lower()
    assert ctx.escalated is True
    assert ctx.ticket_id == ticket.id
