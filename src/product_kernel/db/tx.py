# product_kernel/db/tx.py
"""
Transactional Decorator
────────────────────────────────────────────
Wraps service methods in an explicit DB transaction.
Intended for domain services, analogous to Spring @Transactional.
"""
from __future__ import annotations
from functools import wraps
from typing import Callable, Any, Awaitable
from product_kernel.db.context import session_in_transaction

def transactional(fn: Callable[..., Awaitable[Any]]):
    """Wraps async function inside session_in_transaction()"""
    @wraps(fn)
    async def _w(*a, **kw):
        async with session_in_transaction():
            return await fn(*a, **kw)
    return _w
