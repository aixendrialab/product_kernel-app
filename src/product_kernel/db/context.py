from __future__ import annotations
from contextvars import ContextVar, Token
from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

"""
──────────────────────────────────────────────────────────────────────────────
Context-based Session Management
──────────────────────────────────────────────────────────────────────────────
Purpose:
    Provide a coroutine-safe, request-safe AsyncSession that can be accessed
    anywhere in the domain layer (Repos, Services, etc.) without passing it
    through constructors.

Core APIs:
    - set_session(session): bind session to current coroutine context
    - get_session(): get currently bound AsyncSession
    - reset_session(token): restore previous context binding
    - session_in_transaction(): begin+commit transaction context
──────────────────────────────────────────────────────────────────────────────
"""

# ContextVar to store the AsyncSession for this coroutine/task
_session_cv: ContextVar[Optional[AsyncSession]] = ContextVar("_pk_session", default=None)

# Depth counter for nested @transactional calls
_tx_depth: ContextVar[int] = ContextVar("_pk_tx_depth", default=0)


# ──────────────────────────────────────────────────────────────
# Session binding helpers
# ──────────────────────────────────────────────────────────────
def set_session(session: AsyncSession) -> Token:
    if session is None:
        raise ValueError("set_session() requires a non-None AsyncSession")
    return _session_cv.set(session)


def reset_session(token: Token) -> None:
    """Reset ContextVar binding to its previous value."""
    _session_cv.reset(token)


def get_session() -> AsyncSession:
    """
    Retrieve the AsyncSession bound to this coroutine.
    Works for both FastAPI (middleware-bound) and seed_runner contexts.
    """
    sess = _session_cv.get()
    if sess is None:
        raise RuntimeError(
            "No AsyncSession bound in current context. "
            "Did you call set_session(sess) in seed_runner or middleware?"
        )
    return sess


# ──────────────────────────────────────────────────────────────
# Transactional context manager
# ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def session_in_transaction() -> AsyncIterator[AsyncSession]:
    """
    Start or reuse a transaction for the current AsyncSession.
    Supports nested usage via depth counter.
    """
    sess = get_session()
    depth = _tx_depth.get()
    if depth == 0:
        token = _tx_depth.set(1)
        async with sess.begin():
            try:
                yield sess
            finally:
                _tx_depth.reset(token)
    else:
        token = _tx_depth.set(depth + 1)
        try:
            yield sess
        finally:
            _tx_depth.reset(token)


# Alias for clarity
transactional_scope = session_in_transaction
current_session = get_session
