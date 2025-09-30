from __future__ import annotations
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from product_kernel.db.context import set_session, reset_session

class DBSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        super().__init__(app)
        self._sf = session_factory

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        sf = self._sf or getattr(request.app.state, "async_sessionmaker", None)
        if sf is None:
            raise RuntimeError("DBSessionMiddleware needs app.state.async_sessionmaker set during startup.")
        session = sf()
        token = set_session(session)
        try:
            return await call_next(request)
        except Exception:
            try: await session.rollback()
            except Exception: pass
            raise
        finally:
            reset_session(token)
            await session.close()
