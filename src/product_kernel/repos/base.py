"""
Generic Repository Base (Enhanced)
────────────────────────────────────────────
Focus:
    • CRUD operations
    • ContextVar-bound AsyncSession
    • Bulk helpers (update_where, delete_where, first_where, exists_where)
    • Registered in DI registry
────────────────────────────────────────────
"""
from __future__ import annotations
from typing import TypeVar, Generic, Type, Optional, Sequence, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from product_kernel.db.context import get_session
from product_kernel.di.registry import register

T = TypeVar("T")


class RepoBase(Generic[T]):
    """Generic repository providing async CRUD + query helpers."""

    model: Optional[Type[T]] = None

    # ------------------------------------------------------------------
    # Class registration
    # ------------------------------------------------------------------
    def __init_subclass__(cls) -> None:
        if cls.model is None:
            raise RuntimeError(f"{cls.__name__} must define class attr `model`")
        register(cls, lambda: cls())

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------
    @property
    def session(self) -> AsyncSession:
        """
        Always fetch the AsyncSession from ContextVar.
        No explicit constructor passing needed.
        """
        sess = get_session()
        if not sess:
            raise RuntimeError(
                "No active AsyncSession; ensure DBSessionMiddleware or seed_runner set_session() is called."
            )
        return sess

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    async def get(self, id_: Any) -> Optional[T]:
        res = await self.session.execute(select(self.model).where(self.model.id == id_))
        return res.scalar_one_or_none()

    async def list(self, *, where=None, order_by=None, limit=None, offset=0) -> Sequence[T]:
        stmt = select(self.model)
        if where is not None:
            for cond in (where if isinstance(where, (list, tuple)) else [where]):
                stmt = stmt.where(cond)
        if order_by is not None:
            stmt = stmt.order_by(*order_by if isinstance(order_by, (list, tuple)) else [order_by])
        if limit:
            stmt = stmt.limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def create(self, **values) -> T:
        obj = self.model(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, id_: Any, **values) -> int:
        res = await self.session.execute(
            update(self.model).where(self.model.id == id_).values(**values)
        )
        return res.rowcount or 0

    async def delete(self, id_: Any) -> int:
        res = await self.session.execute(delete(self.model).where(self.model.id == id_))
        return res.rowcount or 0

    async def count(self, where=None) -> int:
        stmt = select(func.count()).select_from(self.model)
        if where is not None:
            stmt = stmt.where(where)
        res = await self.session.execute(stmt)
        return int(res.scalar_one())

    # ------------------------------------------------------------------
    # Extended helpers
    # ------------------------------------------------------------------
    async def first_where(self, where) -> Optional[T]:
        """Return first matching row or None."""
        stmt = select(self.model).where(where).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def exists_where(self, where) -> bool:
        """Return True if any row matches."""
        return (await self.first_where(where)) is not None

    async def update_where(self, where, **values) -> int:
        """Bulk update by predicate."""
        stmt = update(self.model).where(where).values(**values)
        res = await self.session.execute(stmt)
        return res.rowcount or 0

    async def delete_where(self, where) -> int:
        """Bulk delete by predicate."""
        stmt = delete(self.model).where(where)
        res = await self.session.execute(stmt)
        return res.rowcount or 0
