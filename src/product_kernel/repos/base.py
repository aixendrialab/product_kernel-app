"""
Generic Repository Base (Enhanced)
────────────────────────────────────────────
Focus:
    • CRUD operations using the active request AsyncSession
    • Clean fail-fast if session not bound (no temp sessions)
    • Bulk helpers (update_where, delete_where, first_where, exists_where)
    • Auto-registers each Repo in DI registry
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

    # Each subclass must set this:
    model: Optional[Type[T]] = None

    # ------------------------------------------------------------------
    # Class registration (for autowiring)
    # ------------------------------------------------------------------
    def __init_subclass__(cls) -> None:
        if cls.model is None:
            raise RuntimeError(f"{cls.__name__} must define class attr `model`")
        register(cls, lambda: cls())

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self):
        # Obtain the request-scoped session. Will raise if none bound.
        self.session: AsyncSession = get_session()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    async def get(self, id_: Any) -> Optional[T]:
        res = await self.session.execute(select(self.model).where(self.model.id == id_))
        return res.scalar_one_or_none()

    async def list(
        self, *, where=None, order_by=None, limit: Optional[int] = None, offset: int = 0
    ) -> Sequence[T]:
        stmt = select(self.model)
        if where is not None:
            items = where if isinstance(where, (list, tuple)) else [where]
            for cond in items:
                stmt = stmt.where(cond)
        if order_by is not None:
            items = order_by if isinstance(order_by, (list, tuple)) else [order_by]
            stmt = stmt.order_by(*items)
        if limit:
            stmt = stmt.limit(limit).offset(offset)

        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def create(self, **values) -> T:
        obj = self.model(**values)
        self.session.add(obj)
        await self.session.flush()  # populate PKs
        return obj

    async def update(self, id_: Any, **values) -> int:
        res = await self.session.execute(
            update(self.model).where(self.model.id == id_).values(**values)
        )
        return int(res.rowcount or 0)

    async def delete(self, id_: Any) -> int:
        res = await self.session.execute(delete(self.model).where(self.model.id == id_))
        return int(res.rowcount or 0)

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
        stmt = select(self.model).where(where).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def exists_where(self, where) -> bool:
        return (await self.first_where(where)) is not None

    async def update_where(self, where, **values) -> int:
        stmt = update(self.model).where(where).values(**values)
        res = await self.session.execute(stmt)
        return int(res.rowcount or 0)

    async def delete_where(self, where) -> int:
        stmt = delete(self.model).where(where)
        res = await self.session.execute(stmt)
        return int(res.rowcount or 0)
