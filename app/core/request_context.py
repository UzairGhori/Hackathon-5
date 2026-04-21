"""Request-scoped context using contextvars.

Provides a request ID that is accessible anywhere in the call stack
without passing it through every function signature.
"""

import contextvars
import uuid

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def generate_request_id() -> str:
    return uuid.uuid4().hex[:16]


def get_request_id() -> str:
    return request_id_ctx.get()
