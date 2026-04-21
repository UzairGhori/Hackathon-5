"""Agent runtime context — passed to every tool call via RunContextWrapper."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChannelType


@dataclass
class AgentContext:
    """Holds everything the agent tools need during a single run."""

    session: AsyncSession
    customer_id: uuid.UUID
    conversation_id: uuid.UUID
    channel: ChannelType
    # Populated by tools during execution
    response_text: str = ""
    escalated: bool = False
    ticket_id: uuid.UUID | None = None
    metadata: dict = field(default_factory=dict)
    # Tool invocation trace for demo visibility — each entry:
    # {"tool": name, "args": {...}, "ts_ms": elapsed_since_run_start}
    tool_trace: list[dict] = field(default_factory=list)
