# product_kernel/db/middleware.py
from __future__ import annotations
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from product_kernel.db.context import set_session, clear_session


class DBMiddleware(BaseHTTPMiddleware):
    """
    Unified per-request AsyncSession lifecycle middleware.
    """

    def __init__(self, app, *, db_url: str):
        super().__init__(app)
        self.db_url = db_url
        self.engine = None
        self.SessionMaker: async_sessionmaker[AsyncSession] | None = None

    async def _init_engine(self):
        if self.engine:
            return
        url = self.db_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.SessionMaker = async_sessionmaker(self.engine, expire_on_commit=False)
        print(f"✅ [kernel] DB engine initialized for {url}")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.SessionMaker:
            await self._init_engine()

        async with self.SessionMaker() as session:
            request.state.db = session
            set_session(session)
            try:
                response = await call_next(request)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                clear_session()
        return response

    async def shutdown(self):
        if self.engine:
            await self.engine.dispose()
            print("🧹 [kernel] DB engine disposed")
