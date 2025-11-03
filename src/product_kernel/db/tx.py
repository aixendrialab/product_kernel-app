# product_kernel/db/tx.py
"""
Transactional decorator for service methods
──────────────────────────────────────────────
Explicitly wraps a service method in a commit/rollback boundary.
"""
from functools import wraps
from product_kernel.db.context import get_session


def transactional(fn):
    """Wraps async service methods in an explicit transaction."""
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        session = get_session()
        try:
            result = await fn(*args, **kwargs)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
    return wrapper
