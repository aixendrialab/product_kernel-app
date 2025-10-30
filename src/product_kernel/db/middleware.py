# src/product_kernel/db/middleware.py
from __future__ import annotations
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from product_kernel.db.context import set_session, reset_session


class DBMiddleware(BaseHTTPMiddleware):
    """
    Unified engine + session lifecycle middleware.

    Responsibilities:
      • Create AsyncEngine and async_sessionmaker on startup
      • Inject a per-request AsyncSession into request.state.db
      • Bind session to ContextVar for repository access
      • Dispose engine gracefully on shutdown

    Usage:
        app.add_middleware(DBMiddleware, db_url="postgresql://...")
    """

    def __init__(self, app, *, db_url: str):
        super().__init__(app)
        self.db_url = db_url
        self.engine = None
        self.SessionMaker: async_sessionmaker[AsyncSession] | None = None

    async def _init_engine(self):
        if self.engine:
            return
        if self.db_url.startswith("postgresql://"):
            self.db_url = self.db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.engine = create_async_engine(self.db_url, pool_pre_ping=True)
        self.SessionMaker = async_sessionmaker(self.engine, expire_on_commit=False)
        print(f"✅ [kernel] DB engine and sessionmaker initialized for {self.db_url}")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Ensure engine/sessionmaker are ready
        if not self.SessionMaker:
            await self._init_engine()

        # Create session and attach to request/context
        async with self.SessionMaker() as session:
            request.state.db = session
            token = set_session(session)
            try:
                response = await call_next(request)
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise
            finally:
                reset_session(token)
        return response

    async def shutdown(self):
        """Dispose engine cleanly during app shutdown."""
        if self.engine:
            await self.engine.dispose()
            print("🧹 [kernel] DB engine disposed")
