"""End-to-end scenario tests for the 4 core customer interaction types.

Scenarios tested:
  1. Normal question      → sahi reply, NO ticket, NO escalation
  2. Angry customer       → empathetic reply, ticket created, escalated (angry_customer)
  3. Refund request       → reply, ticket created, escalated (refund_request)
  4. Unknown query        → reply, ticket created, escalated (low_confidence)

Each test simulates the agent's tool-calling behaviour by directly
invoking agent tools in the sequence the system prompt prescribes.
No real OpenAI calls are made.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest
from agents.tool import ToolContext

from app.agent.context import AgentContext
from app.db.models import (
    AgentMetric,
    ChannelType,
    Message,
    MessageDirection,
    MessageSender,
    TicketPriority,
    TicketStatus,
)


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────

def _make_ctx(db_session, **overrides) -> AgentContext:
    defaults = dict(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


def _wrap(ctx: AgentContext, tool_name: str = "test_tool") -> ToolContext[AgentContext]:
    return ToolContext(
        context=ctx,
        tool_name=tool_name,
        tool_call_id=f"call_{uuid.uuid4().hex[:8]}",
        tool_arguments="{}",
    )


# ── Scenario 1: Normal Question ─────────────────────────────

class TestNormalQuestion:
    """Customer asks a simple question that KB can answer.
    Expected: reply sent, NO ticket, NO escalation.
    """

    async def test_kb_returns_answer(self, db_session):
        """search_knowledge_base finds a matching article."""
        from app.agent.tools import search_knowledge_base

        article = MagicMock()
        article.title = "How to reset your password"
        article.category = "Account"
        article.content = "Go to Settings > Security > Reset Password."
        db_session.queue([article])

        ctx = _make_ctx(db_session)
        result = await search_knowledge_base.on_invoke_tool(
            _wrap(ctx, "search_knowledge_base"), json.dumps({"query": "reset password"})
        )

        assert "How to reset your password" in result
        assert "No relevant articles" not in result

    async def test_reply_sent_no_ticket_no_escalation(self, db_session):
        """send_response stores the reply; no ticket/escalation flags set."""
        from app.agent.tools import send_response

        ctx = _make_ctx(db_session)
        reply = "To reset your password, go to Settings > Security > Reset Password."

        await send_response.on_invoke_tool(
            _wrap(ctx, "send_response"), json.dumps({"message": reply})
        )

        # ✅ Sahi reply?
        assert ctx.response_text == reply
        outbound = [o for o in db_session.added if isinstance(o, Message)]
        assert len(outbound) == 1
        assert outbound[0].direction == MessageDirection.OUTBOUND
        assert outbound[0].sender == MessageSender.AGENT
        assert "reset your password" in outbound[0].content.lower()

        # ✅ Ticket create NAHI hona chahiye
        assert ctx.ticket_id is None

        # ✅ Escalation NAHI honi chahiye
        assert ctx.escalated is False

    async def test_run_agent_normal_resolves_without_escalation(
        self, stub_run_agent, db_session
    ):
        """Full run_agent flow — metric shows resolved_by_ai=True."""
        from app.agent.agent import run_agent

        response = await run_agent(
            session=db_session,
            customer_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            channel=ChannelType.WEB,
            customer_message="How do I reset my password?",
        )

        assert len(response) > 0
        metrics = [o for o in db_session.added if isinstance(o, AgentMetric)]
        assert len(metrics) == 1
        assert metrics[0].resolved_by_ai is True
        assert metrics[0].escalated is False


# ── Scenario 2: Angry Customer ──────────────────────────────

class TestAngryCustomer:
    """Customer is furious — uses caps, exclamation marks, threats.
    Expected: empathetic reply, ticket created, escalated (angry_customer, HIGH).
    """

    async def test_ticket_created_for_angry_customer(self, db_session, monkeypatch):
        """create_ticket is called with high priority."""
        from app.agent import tools as tools_mod

        created_ticket = MagicMock(id=uuid.uuid4())
        captured = {}

        class StubTicketService:
            def __init__(self, session):
                pass

            async def create_ticket(self, **kwargs):
                captured.update(kwargs)
                return created_ticket

        monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

        ctx = _make_ctx(db_session)
        result = await tools_mod.create_ticket.on_invoke_tool(
            _wrap(ctx, "create_ticket"),
            json.dumps({
                "subject": "Angry customer - login issue",
                "description": "Customer is extremely frustrated about repeated login failures",
                "priority": "high",
            }),
        )

        # ✅ Ticket create ho raha?
        assert "Ticket created successfully" in result
        assert ctx.ticket_id == created_ticket.id
        assert captured["priority"] == TicketPriority.HIGH

    async def test_escalation_angry_customer(self, db_session, monkeypatch):
        """escalate_to_human fires with category=angry_customer."""
        from app.agent import tools as tools_mod

        ticket = MagicMock(id=uuid.uuid4())
        ticket.priority = MagicMock(value="high")
        escalate_kwargs = {}

        class StubTicketService:
            def __init__(self, session):
                pass

            async def create_ticket(self, **kwargs):
                return ticket

            async def escalate(self, **kwargs):
                escalate_kwargs.update(kwargs)
                return ticket

        monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

        ctx = _make_ctx(db_session)
        # Simulate agent already created ticket
        ctx.ticket_id = ticket.id

        result = await tools_mod.escalate_to_human.on_invoke_tool(
            _wrap(ctx, "escalate_to_human"),
            json.dumps({
                "reason": "Customer is extremely angry, using caps and threats",
                "category": "angry_customer",
            }),
        )

        # ✅ Escalation ho rahi?
        assert ctx.escalated is True
        assert "escalated" in result.lower()
        assert "angry_customer" in result
        assert escalate_kwargs["category"] == "angry_customer"

    async def test_empathetic_reply_sent(self, db_session):
        """send_response includes empathetic language after escalation."""
        from app.agent.tools import send_response

        ctx = _make_ctx(db_session)
        ctx.escalated = True
        ctx.ticket_id = uuid.uuid4()

        reply = (
            "I completely understand your frustration, and I'm sorry for the "
            "inconvenience. I've escalated your issue to our senior support team. "
            "A human agent will follow up with you shortly."
        )

        await send_response.on_invoke_tool(
            _wrap(ctx, "send_response"), json.dumps({"message": reply})
        )

        # ✅ Sahi reply — empathetic + escalation info
        assert ctx.response_text == reply
        assert "frustration" in ctx.response_text.lower()
        assert "human agent" in ctx.response_text.lower()

    async def test_run_agent_angry_escalation_metric(
        self, stub_run_agent, db_session
    ):
        """Full flow — metric reflects escalation."""
        from app.agent import agent as agent_mod

        async def escalating_run(**kwargs):
            ctx = kwargs["context"]
            ctx.escalated = True
            ctx.ticket_id = uuid.uuid4()
            ctx.response_text = "I understand your frustration. A human agent will follow up."
            return agent_mod.Runner.run.return_value

        stub_run_agent.side_effect = escalating_run

        response = await agent_mod.run_agent(
            session=db_session,
            customer_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            channel=ChannelType.WEB,
            customer_message="THIS IS UNACCEPTABLE!!! I've been waiting for HOURS! Fix this NOW or I'm leaving!!!",
        )

        assert "frustration" in response.lower() or "human" in response.lower()

        metrics = [o for o in db_session.added if isinstance(o, AgentMetric)]
        assert metrics[0].escalated is True
        assert metrics[0].resolved_by_ai is False
        assert metrics[0].ticket_id is not None


# ── Scenario 3: Refund Request ──────────────────────────────

class TestRefundRequest:
    """Customer asks for a refund.
    Expected: reply, ticket created, escalated (refund_request, HIGH).
    """

    async def test_ticket_created_for_refund(self, db_session, monkeypatch):
        from app.agent import tools as tools_mod

        created_ticket = MagicMock(id=uuid.uuid4())
        captured = {}

        class StubTicketService:
            def __init__(self, session):
                pass

            async def create_ticket(self, **kwargs):
                captured.update(kwargs)
                return created_ticket

        monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

        ctx = _make_ctx(db_session)
        result = await tools_mod.create_ticket.on_invoke_tool(
            _wrap(ctx, "create_ticket"),
            json.dumps({
                "subject": "Refund request",
                "description": "Customer wants a full refund for their subscription",
                "priority": "high",
            }),
        )

        # ✅ Ticket create ho raha?
        assert "Ticket created successfully" in result
        assert ctx.ticket_id == created_ticket.id

    async def test_escalation_refund_request(self, db_session, monkeypatch):
        from app.agent import tools as tools_mod

        ticket = MagicMock(id=uuid.uuid4())
        ticket.priority = MagicMock(value="high")
        escalate_kwargs = {}

        class StubTicketService:
            def __init__(self, session):
                pass

            async def create_ticket(self, **kwargs):
                return ticket

            async def escalate(self, **kwargs):
                escalate_kwargs.update(kwargs)
                return ticket

        monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

        ctx = _make_ctx(db_session)
        ctx.ticket_id = ticket.id

        result = await tools_mod.escalate_to_human.on_invoke_tool(
            _wrap(ctx, "escalate_to_human"),
            json.dumps({
                "reason": "Customer requesting a full refund for their subscription",
                "category": "refund_request",
            }),
        )

        # ✅ Escalation ho rahi?
        assert ctx.escalated is True
        assert "refund_request" in result
        assert escalate_kwargs["category"] == "refund_request"

    async def test_refund_priority_bumped_to_high(self):
        """TicketService._escalation_priority bumps refund to HIGH."""
        from app.services.ticket_service import TicketService

        result = TicketService._escalation_priority("refund_request", TicketPriority.MEDIUM)
        assert result == TicketPriority.HIGH

    async def test_refund_reply_mentions_human_followup(self, db_session):
        from app.agent.tools import send_response

        ctx = _make_ctx(db_session)
        ctx.escalated = True
        ctx.ticket_id = uuid.uuid4()

        reply = (
            "I understand you'd like a refund. I've created a ticket and escalated "
            "this to our billing team. A human agent will follow up with you shortly "
            "to process your refund request."
        )

        await send_response.on_invoke_tool(
            _wrap(ctx, "send_response"), json.dumps({"message": reply})
        )

        # ✅ Sahi reply?
        assert "refund" in ctx.response_text.lower()
        assert "human agent" in ctx.response_text.lower()

    async def test_run_agent_refund_full_flow(self, stub_run_agent, db_session):
        from app.agent import agent as agent_mod

        async def refund_run(**kwargs):
            ctx = kwargs["context"]
            ctx.escalated = True
            ctx.ticket_id = uuid.uuid4()
            ctx.response_text = "I've escalated your refund request. A human agent will assist you."
            return agent_mod.Runner.run.return_value

        stub_run_agent.side_effect = refund_run

        response = await agent_mod.run_agent(
            session=db_session,
            customer_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            channel=ChannelType.GMAIL,
            customer_message="I want a full refund. This product is not working as advertised.",
        )

        metrics = [o for o in db_session.added if isinstance(o, AgentMetric)]
        assert metrics[0].escalated is True
        assert metrics[0].resolved_by_ai is False
        assert metrics[0].channel == ChannelType.GMAIL


# ── Scenario 4: Unknown Query ──────────────────────────────

class TestUnknownQuery:
    """Customer asks something the KB has no answer for.
    Expected: honest reply, ticket created, escalated (low_confidence, MEDIUM).
    """

    async def test_kb_returns_no_results(self, db_session):
        """search_knowledge_base returns 'No relevant articles'."""
        from app.agent.tools import search_knowledge_base

        db_session.queue([])  # empty KB results

        ctx = _make_ctx(db_session)
        result = await search_knowledge_base.on_invoke_tool(
            _wrap(ctx, "search_knowledge_base"), json.dumps({"query": "quantum flux capacitor integration"})
        )

        assert "No relevant articles" in result

    async def test_escalation_low_confidence(self, db_session, monkeypatch):
        from app.agent import tools as tools_mod

        ticket = MagicMock(id=uuid.uuid4())
        ticket.priority = MagicMock(value="medium")
        escalate_kwargs = {}

        class StubTicketService:
            def __init__(self, session):
                pass

            async def create_ticket(self, **kwargs):
                return ticket

            async def escalate(self, **kwargs):
                escalate_kwargs.update(kwargs)
                return ticket

        monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

        ctx = _make_ctx(db_session)
        ctx.ticket_id = ticket.id

        result = await tools_mod.escalate_to_human.on_invoke_tool(
            _wrap(ctx, "escalate_to_human"),
            json.dumps({
                "reason": "No relevant knowledge base articles found. Cannot confidently answer.",
                "category": "low_confidence",
            }),
        )

        # ✅ Escalation ho rahi?
        assert ctx.escalated is True
        assert "low_confidence" in result
        assert escalate_kwargs["category"] == "low_confidence"

    async def test_low_confidence_priority_is_medium(self):
        from app.services.ticket_service import TicketService

        result = TicketService._escalation_priority("low_confidence", TicketPriority.LOW)
        assert result == TicketPriority.MEDIUM

    async def test_auto_ticket_creation_on_escalation(self, db_session, monkeypatch):
        """If no ticket exists, escalate_to_human creates one automatically."""
        from app.agent import tools as tools_mod

        ticket = MagicMock(id=uuid.uuid4())
        ticket.priority = MagicMock(value="medium")
        create_called = False

        class StubTicketService:
            def __init__(self, session):
                pass

            async def create_ticket(self, **kwargs):
                nonlocal create_called
                create_called = True
                assert kwargs["subject"] == "Escalated: low_confidence"
                assert kwargs["priority"] == TicketPriority.HIGH
                return ticket

            async def escalate(self, **kwargs):
                return ticket

        monkeypatch.setattr(tools_mod, "TicketService", StubTicketService)

        ctx = _make_ctx(db_session)
        assert ctx.ticket_id is None  # no ticket yet

        await tools_mod.escalate_to_human.on_invoke_tool(
            _wrap(ctx, "escalate_to_human"),
            json.dumps({
                "reason": "Cannot find answer in knowledge base",
                "category": "low_confidence",
            }),
        )

        # ✅ Auto-ticket create hua
        assert create_called is True
        assert ctx.ticket_id == ticket.id
        assert ctx.escalated is True

    async def test_unknown_reply_is_honest(self, db_session):
        from app.agent.tools import send_response

        ctx = _make_ctx(db_session)
        ctx.escalated = True
        ctx.ticket_id = uuid.uuid4()

        reply = (
            "I wasn't able to find an answer to your question in our knowledge base. "
            "I've created a ticket and escalated this to a specialist. "
            "A human agent will follow up with you shortly."
        )

        await send_response.on_invoke_tool(
            _wrap(ctx, "send_response"), json.dumps({"message": reply})
        )

        # ✅ Sahi reply — honest + escalation
        assert "wasn't able to find" in ctx.response_text.lower() or "knowledge base" in ctx.response_text.lower()
        assert "human agent" in ctx.response_text.lower()

    async def test_run_agent_unknown_full_flow(self, stub_run_agent, db_session):
        from app.agent import agent as agent_mod

        async def unknown_run(**kwargs):
            ctx = kwargs["context"]
            ctx.escalated = True
            ctx.ticket_id = uuid.uuid4()
            ctx.response_text = "I couldn't find relevant info. A human agent will help you."
            return agent_mod.Runner.run.return_value

        stub_run_agent.side_effect = unknown_run

        response = await agent_mod.run_agent(
            session=db_session,
            customer_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            channel=ChannelType.WHATSAPP,
            customer_message="How do I integrate the quantum flux capacitor with your API?",
        )

        metrics = [o for o in db_session.added if isinstance(o, AgentMetric)]
        assert metrics[0].escalated is True
        assert metrics[0].resolved_by_ai is False
        assert metrics[0].channel == ChannelType.WHATSAPP
