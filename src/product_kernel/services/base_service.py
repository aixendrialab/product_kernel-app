# product_kernel/services/base_service.py
"""
Base class for all domain services
──────────────────────────────────────────────
Responsibilities:
    • Provide the active request-scoped AsyncSession
    • Support dependency autowiring for repositories
    • Offer optional utilities like commit()
    • Allow standalone (CLI/test) session binding via new_session()
──────────────────────────────────────────────
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any
from sqlalchemy.ext.asyncio import AsyncSession

from product_kernel.db.context import get_session, set_session, clear_session
from product_kernel.db.session import async_session
from product_kernel.di.inject import autowire


class BaseService:
    """
    Base class for all services.

    Provides:
      - request-scoped DB session (from ContextVar)
      - dependency autowiring for repos
      - optional utilities like commit()
    """

    def __init__(self, session: AsyncSession | None = None):
        # Use existing request session (middleware) or injected session
        self.session: AsyncSession = session or get_session()
        autowire(self)

    # ──────────────────────────────────────────────
    # Common utilities
    # ──────────────────────────────────────────────
    async def commit(self) -> None:
        """Manually commit the current session."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Manually rollback the current session."""
        await self.session.rollback()

    # ──────────────────────────────────────────────
    # Standalone usage (CLI, seeders, tests)
    # ──────────────────────────────────────────────
    @classmethod
    @asynccontextmanager
    async def new_session(cls) -> AsyncIterator[AsyncSession]:
        """
        Bind a temporary AsyncSession to ContextVar for standalone tasks.
        Middleware handles this automatically in FastAPI apps.
        """
        try:
            sess = get_session()
            # Already bound (HTTP request or external context)
            yield sess
        except RuntimeError:
            # No bound session → create one manually
            async with async_session() as sess:
                set_session(sess)
                try:
                    yield sess
                    await sess.commit()
                except Exception:
                    await sess.rollback()
                    raise
                finally:
                    clear_session()
