"""
Tenant context management.
Maintains the active user context for MCP tool invocations.
Phase 2: Defaults to TEST_USER_ID.
Phase 3: Populated from verified JWT claims in auth middleware.
"""

from contextvars import ContextVar
from src.mcp_server.config import TEST_USER_ID

# ContextVar for request-scoped tenant identity
_current_user_ctx: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def get_current_user_id() -> str:
    """
    Return the authenticated user ID for the current tool execution.

    In Phase 2: Returns the constant TEST_USER_ID.
    In Phase 3: Returns the verified user UUID extracted from the OAuth 2.1 token.
    """
    return _current_user_ctx.get() or TEST_USER_ID


def set_current_user_id(user_id: str | None) -> None:
    """
    Set the active tenant user UUID for the current context/request.
    Primarily used by authentication middleware in Phase 3 and unit tests.
    """
    _current_user_ctx.set(user_id)
