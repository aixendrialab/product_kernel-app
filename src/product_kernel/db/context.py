# product_kernel/db/context.py
"""
ContextVar-based AsyncSession management
──────────────────────────────────────────────
• Each request (or task) binds one AsyncSession via DBMiddleware
• get_session() retrieves it; raises if none bound
• clear_session() cleans up after request
• set_session() allows manual binding for CLI/tests
"""
from contextvars import ContextVar
from sqlalchemy.ext.asyncio import AsyncSession

_session_cv: ContextVar[AsyncSession | None] = ContextVar("_pk_session", default=None)


def set_session(session: AsyncSession) -> None:
    """Bind an AsyncSession to current coroutine context."""
    _session_cv.set(session)


def get_session() -> AsyncSession:
    """Return the current AsyncSession or raise if none bound."""
    session = _session_cv.get()
    if not session:
        raise RuntimeError(
            "❌ No active AsyncSession found. "
            "Did you enable DBMiddleware or call set_session()?"
        )
    return session


def clear_session() -> None:
    """Clear ContextVar binding (usually called by middleware)."""
    _session_cv.set(None)
