# product_kernel/db/engine.py
"""
Async Engine / Session Factory Accessors
────────────────────────────────────────────
This module isolates engine/sessionmaker creation.

Used by:
    • db.session (CLI / seeds)
    • db.lifecycle (FastAPI startup)
    • tests (to inject test sessionmaker)
"""

from __future__ import annotations
import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession, create_async_engine

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None

def ensure_engine() -> AsyncEngine:
    """Create global engine lazily from DATABASE_URL if not yet created."""
    global _engine, _sessionmaker
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL not set")
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        _engine = create_async_engine(url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine

def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the active async_sessionmaker (create if missing)."""
    global _sessionmaker
    if _sessionmaker is None:
        ensure_engine()
    assert _sessionmaker is not None
    return _sessionmaker

def set_sessionmaker(sm: async_sessionmaker[AsyncSession]) -> None:
    """Allow overriding sessionmaker (e.g., in FastAPI lifespan)."""
    global _sessionmaker
    _sessionmaker = sm
