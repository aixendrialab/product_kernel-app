from __future__ import annotations
from contextvars import ContextVar, Token
from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

_session_cv: ContextVar[Optional[AsyncSession]] = ContextVar("_pk_session", default=None)

def set_session(session: AsyncSession) -> Token:
    if session is None:
        raise ValueError("set_session() requires a non-None AsyncSession")
    return _session_cv.set(session)

def reset_session(token: Token) -> None:
    _session_cv.reset(token)

def get_session() -> AsyncSession:
    sess = _session_cv.get()
    if sess is None:
        raise RuntimeError("No AsyncSession bound. Ensure DBSessionMiddleware runs for this request.")
    return sess

_tx_depth: ContextVar[int] = ContextVar("_pk_tx_depth", default=0)

@asynccontextmanager
async def session_in_transaction() -> AsyncIterator[AsyncSession]:
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

transactional_scope = session_in_transaction
current_session = get_session
