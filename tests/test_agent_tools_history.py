"""Direct tests for the `get_customer_history` agent tool.

This tool performs four sequential queries:
  1. Customer
  2. Conversations (last 5)
  3. Tickets (last 5)
  4. Messages in current conversation (all)

We drive it with FakeSession.queue_many so the four execute() calls return
our canned objects, then assert the formatted output contains everything
the agent needs for context.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.db.models import ChannelType, MessageSender


pytestmark = pytest.mark.asyncio


def _fake_customer(name: str = "Alice Smith", company: str = "Acme") -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), full_name=name, company=company)


def _fake_ticket(subject: str, status: str, priority: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        subject=subject,
        status=SimpleNamespace(value=status),
        priority=SimpleNamespace(value=priority),
    )


def _fake_message(content: str, sender: MessageSender) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        sender=sender,
    )


async def test_get_customer_history_full_context(db_session):
    from app.agent.tools import get_customer_history
    from app.agent.context import AgentContext
    from agents.tool import ToolContext

    customer = _fake_customer("Alice Smith", "Acme Inc")
    conversations = [SimpleNamespace(id=uuid.uuid4()) for _ in range(3)]
    tickets = [
        _fake_ticket("Cannot log in", "open", "high"),
        _fake_ticket("Billing issue", "resolved", "medium"),
    ]
    messages = [
        _fake_message("Hi, I can't log in to my account.", MessageSender.CUSTOMER),
        _fake_message("I've reset my password twice.", MessageSender.CUSTOMER),
        _fake_message("Have you tried clearing cookies?", MessageSender.AGENT),
    ]

    # Four execute() calls → four queued results
    db_session.queue_many([customer, conversations, tickets, messages])

    ctx = AgentContext(
        session=db_session,
        customer_id=customer.id,
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
    )
    result = await get_customer_history.on_invoke_tool(
        ToolContext(context=ctx, tool_name="get_customer_history", tool_call_id="call_test", tool_arguments="{}"), "{}"
    )

    # Customer header
    assert "Alice Smith" in result
    assert "Acme Inc" in result
    assert "Total conversations: 3" in result

    # Tickets
    assert "Recent tickets:" in result
    assert "Cannot log in" in result
    assert "[open]" in result
    assert "priority: high" in result
    assert "Billing issue" in result
    assert "[resolved]" in result

    # Messages with both sender labels
    assert "Current conversation (3 messages):" in result
    assert "[Customer]" in result
    assert "[Agent]" in result
    assert "Have you tried clearing cookies?" in result


async def test_get_customer_history_customer_not_found(db_session):
    """If the customer lookup returns None, the tool must return an error string."""
    from app.agent.tools import get_customer_history
    from app.agent.context import AgentContext
    from agents.tool import ToolContext

    db_session.queue_many([None])  # customer lookup → miss

    ctx = AgentContext(
        session=db_session,
        customer_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        channel=ChannelType.GMAIL,
    )
    result = await get_customer_history.on_invoke_tool(
        ToolContext(context=ctx, tool_name="get_customer_history", tool_call_id="call_test", tool_arguments="{}"), "{}"
    )
    assert result == "Customer not found."


async def test_get_customer_history_no_tickets_no_messages(db_session):
    """Customer with no tickets and no prior messages."""
    from app.agent.tools import get_customer_history
    from app.agent.context import AgentContext
    from agents.tool import ToolContext

    customer = _fake_customer("Dana Dew", "")
    db_session.queue_many([customer, [], [], []])

    ctx = AgentContext(
        session=db_session,
        customer_id=customer.id,
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WHATSAPP,
    )
    result = await get_customer_history.on_invoke_tool(
        ToolContext(context=ctx, tool_name="get_customer_history", tool_call_id="call_test", tool_arguments="{}"), "{}"
    )

    assert "Dana Dew" in result
    assert "Total conversations: 0" in result
    # No "Recent tickets" header when list is empty
    assert "Recent tickets:" not in result
    # No "Current conversation" header when there are no messages
    assert "Current conversation" not in result


async def test_get_customer_history_message_truncation(db_session):
    """Messages longer than 200 chars should be truncated in the formatted output."""
    from app.agent.tools import get_customer_history
    from app.agent.context import AgentContext
    from agents.tool import ToolContext

    customer = _fake_customer()
    long_text = "x" * 500
    msg = _fake_message(long_text, MessageSender.CUSTOMER)
    db_session.queue_many([customer, [], [], [msg]])

    ctx = AgentContext(
        session=db_session,
        customer_id=customer.id,
        conversation_id=uuid.uuid4(),
        channel=ChannelType.WEB,
    )
    result = await get_customer_history.on_invoke_tool(
        ToolContext(context=ctx, tool_name="get_customer_history", tool_call_id="call_test", tool_arguments="{}"), "{}"
    )
    # The rendered message body is capped at 200 chars
    # (everything before that is the "[Customer]: " prefix)
    assert "x" * 200 in result
    assert "x" * 201 not in result
