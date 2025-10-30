# product_kernel/services/base_service.py
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any
from product_kernel.db.context import get_session, set_session, reset_session
from product_kernel.db.session import async_session  # your lazy session factory
from product_kernel.db.context import session_in_transaction as transactional_scope
from product_kernel.di.inject import autowire
import asyncio
from functools import wraps

def non_transactional(fn):
    setattr(fn, "_pk_non_tx", True)
    return fn

def _tx_wrap(fn):
    if not asyncio.iscoroutinefunction(fn):
        return fn
    @wraps(fn)
    async def w(self, *args, **kwargs):
        autowire(self)
        async with transactional_scope():
            return await fn(self, *args, **kwargs)
    return w

class BaseService:
    # Wrap all async callables on subclass at first use
    def __getattribute__(self, name: str):
        attr = super().__getattribute__(name)
        if callable(attr) and getattr(attr, "__name__", "").startswith("_") is False:
            if getattr(attr, "_pk_non_tx", False):
                return attr
            return _tx_wrap(attr)
        return attr

    @classmethod
    @asynccontextmanager
    async def new_session(cls) -> AsyncIterator[Any]:
        """
        Bind a session to ContextVar WITHOUT starting a transaction.
        Transactions are owned by @transactional wrappers on methods.
        """
        try:
            # Already bound (FastAPI request)? Reuse.
            sess = get_session()
            yield sess
        except RuntimeError:
            # Standalone mode (seeders/CLI/jobs)
            async with async_session() as sess:
                token = set_session(sess)
                try:
                    yield sess
                finally:
                    reset_session(token)
