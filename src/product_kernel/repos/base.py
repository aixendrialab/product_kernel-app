# product_kernel/repos/base.py
from __future__ import annotations

import sys
from typing import Any, Optional, Sequence, Type, Generic, TypeVar, get_args, get_origin
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from product_kernel.db.context import get_session
from product_kernel.di.registry import register

T = TypeVar("T")

def _infer_model_from_generic(cls) -> Optional[Type[Any]]:
    """
    If class is declared as RepoBase[Model], extract Model from __orig_bases__.
    Handles forward-ref strings when 'from __future__ import annotations' is used.
    """
    for base in getattr(cls, "__orig_bases__", ()):
        if get_origin(base) is RepoBase:
            args = get_args(base)
            if not args:
                continue
            arg = args[0]
            # Forward ref string? evaluate in module globals.
            if isinstance(arg, str):
                try:
                    mod_globals = sys.modules[cls.__module__].__dict__
                    return eval(arg, mod_globals)
                except Exception:
                    return None
            # Normal type
            if isinstance(arg, type):
                return arg
    return None


class RepoBase(Generic[T]):
    """
    Versatile repo base:
      • Subclass as `class X(RepoBase[MyModel])`  ← model inferred automatically
      • or set class attr: `model = MyModel`
      • or bind in ctor:   `super().__init__(MyModel)`
      • or pass per call:  `get(id, model=MyModel)` / use `.bound(MyModel)`
    Auto-registers subclasses for DI so services can just annotate fields.
    """

    # Optional class-level default model (used if inference/ctor not provided)
    model: Optional[Type[Any]] = None

    # Auto-register subclass and infer model at class creation time
    def __init_subclass__(cls) -> None:
        # Infer generic type param if present and no class attr already set
        if getattr(cls, "model", None) is None:
            inferred = _infer_model_from_generic(cls)
            if inferred is not None:
                cls.model = inferred
        # Register provider for DI (no-arg ctor)
        register(cls, lambda: cls())

    def __init__(self, model: Optional[Type[Any]] = None) -> None:
        # Instance-level model takes precedence over class/inferred model
        self._model: Optional[Type[Any]] = model

    @property
    def session(self) -> AsyncSession:
        sess = get_session()
        if not sess:
            raise RuntimeError("No DB session in context; is DBSessionMiddleware installed?")
        return sess

    # Resolve the effective model for this call
    def _m(self, model: Optional[Type[Any]]) -> Type[Any]:
        m = model or self._model or self.model
        if m is None:
            raise RuntimeError(
                "No model set. Use RepoBase[Model], set class attr `model`, call super().__init__(Model), "
                "pass `model=...`, or use `bound(Model)`."
            )
        return m

    # ---- CRUD (optional model override) ----
    async def get(self, id_: Any, *, model: Optional[Type[Any]] = None) -> Optional[Any]:
        M = self._m(model)
        res = await self.session.execute(select(M).where(M.id == id_))
        return res.scalar_one_or_none()

    async def list(
        self,
        where: Optional[list] = None,
        *,
        model: Optional[Type[Any]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: Optional[list] = None,
    ) -> Sequence[Any]:
        M = self._m(model)
        stmt = select(M)
        for cond in (where or []): stmt = stmt.where(cond)
        for ob in (order_by or []): stmt = stmt.order_by(ob)
        if limit is not None: stmt = stmt.limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def create(self, *, model: Optional[Type[Any]] = None, **values) -> Any:
        M = self._m(model)
        obj = M(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, id_: Any, *, model: Optional[Type[Any]] = None, **values) -> int:
        M = self._m(model)
        res = await self.session.execute(update(M).where(M.id == id_).values(**values))
        return res.rowcount or 0

    async def delete(self, id_: Any, *, model: Optional[Type[Any]] = None) -> int:
        M = self._m(model)
        res = await self.session.execute(delete(M).where(M.id == id_))
        return res.rowcount or 0

    # Bind a model once and then call plain CRUD without model=
    def bound(self, model: Type[Any]) -> "ModelBoundRepo":
        return ModelBoundRepo(self, model)


class ModelBoundRepo:
    def __init__(self, base: RepoBase, model: Type[Any]) -> None:
        self._b = base
        self._m = model
    async def get(self, id_: Any): return await self._b.get(id_, model=self._m)
    async def list(self, where: Optional[list] = None, *, limit: Optional[int] = None, offset: int = 0, order_by: Optional[list] = None):
        return await self._b.list(where, model=self._m, limit=limit, offset=offset, order_by=order_by)
    async def create(self, **values): return await self._b.create(model=self._m, **values)
    async def update(self, id_: Any, **values): return await self._b.update(id_, model=self._m, **values)
    async def delete(self, id_: Any): return await self._b.delete(id_, model=self._m)
