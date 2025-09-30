# product_kernel/services/base_service.py
from __future__ import annotations
import asyncio
from functools import wraps
from typing import Callable, Any
from product_kernel.db.context import transactional_scope
from product_kernel.di.inject import autowire

def non_transactional(fn: Callable[..., Any]) -> Callable[..., Any]:
    setattr(fn, "_pk_non_tx", True)
    return fn

def _tx_wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
    if not asyncio.iscoroutinefunction(fn):
        return fn
    @wraps(fn)
    async def w(self, *args, **kwargs):
        # Ensure dependencies are injected for this request
        autowire(self)
        # Run in per-method transactional scope (nesting-aware)
        async with transactional_scope():
            return await fn(self, *args, **kwargs)
    return w

class BaseService:
    def __init__(self, **_: Any) -> None:
        pass

    def __init_subclass__(cls) -> None:
        for name, attr in list(cls.__dict__.items()):
            if asyncio.iscoroutinefunction(attr) and not getattr(attr, "_pk_non_tx", False):
                setattr(cls, name, _tx_wrap(attr))
