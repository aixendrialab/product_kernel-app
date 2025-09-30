# product_kernel/fastapi.py (framework)
from __future__ import annotations

from typing import Iterable, Optional, Set, Dict, Any, Callable
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# NOTE: We keep the old signature compatible and add auth_allow_anonymous.
# If you don't pass auth_allow_anonymous, behavior is unchanged.

class _KernelAuthMiddleware:
    """
    Minimal, self-contained auth middleware with a public-path allowlist.

    It supports three auth paths:
      1) 'X-User-Id' header (trusted upstream / tests)
      2) 'Dev-Uid' header (developer override)
      3) 'Authorization: Bearer <jwt>' using the provided token_service

    If the request path is in allowlist, it bypasses auth.
    On success, sets request.state.uid and request.state.claims (dict).
    On failure, returns 401 JSON with {"detail": "Missing Authorization"}.
    """

    def __init__(
        self,
        app,
        *,
        token_service: Optional[object],
        allowlist: Set[str],
        on_error: Optional[Callable[[Request, Exception], Any]] = None,
    ):
        self.app = app
        self.token_service = token_service
        self.allowlist = allowlist
        self.on_error = on_error

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)

        path = request.url.path
        if path in self.allowlist:
            return await self.app(scope, receive, send)

        # 1) X-User-Id (trusted)
        uid_hdr = request.headers.get("x-user-id")
        if uid_hdr:
            try:
                uid_val = int(uid_hdr)
            except Exception:
                return await JSONResponse({"detail": "Invalid X-User-Id"}, status_code=400)(scope, receive, send)
            request.state.uid = uid_val
            request.state.claims = {"uid": uid_val}
            return await self.app(scope, receive, send)

        # 2) Dev-Uid (developer override)
        dev_uid = request.headers.get("dev-uid")
        if dev_uid:
            try:
                uid_val = int(dev_uid)
            except Exception:
                return await JSONResponse({"detail": "Invalid Dev-Uid"}, status_code=400)(scope, receive, send)
            request.state.uid = uid_val
            request.state.claims = {"uid": uid_val, "dev": True}
            return await self.app(scope, receive, send)

        # 3) Bearer token via token_service
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if not self.token_service:
                return await JSONResponse({"detail": "Missing Authorization"}, status_code=401)(scope, receive, send)

            try:
                # We try a few common method names to avoid breaking your existing token service
                # Expected to return a dict-like claims with 'sub' or 'uid'
                if hasattr(self.token_service, "verify"):
                    claims = self.token_service.verify(token)  # type: ignore[attr-defined]
                elif hasattr(self.token_service, "decode"):
                    claims = self.token_service.decode(token)  # type: ignore[attr-defined]
                else:
                    # last resort: call as a function
                    claims = self.token_service(token)  # type: ignore[call-arg]

                # Extract uid from claims
                uid = None
                if isinstance(claims, dict):
                    uid = claims.get("uid") or claims.get("sub") or claims.get("user_id")
                    if isinstance(uid, str) and uid.isdigit():
                        uid = int(uid)
                if uid is None:
                    # don't hard-fail; attach claims but no uid
                    request.state.claims = claims
                else:
                    request.state.uid = int(uid)
                    request.state.claims = claims

                return await self.app(scope, receive, send)

            except Exception as e:
                if self.on_error:
                    self.on_error(request, e)
                return await JSONResponse({"detail": "Invalid token"}, status_code=401)(scope, receive, send)

        # No auth presented
        return await JSONResponse({"detail": "Missing Authorization"}, status_code=401)(scope, receive, send)


def create_kernel_app(
    *,
    title: str = "App",
    token_service=None,
    middlewares=(),
    auth_allow_anonymous: Iterable[str] = (),
) -> FastAPI:
    """
    Create app with optional auth middleware and a public-path allowlist.

    - middlewares: same behavior as before (class-based middlewares).
    - token_service: if provided, we attach a minimal auth middleware.
    - auth_allow_anonymous: iterable of paths (strings) that bypass auth.
    """
    app = FastAPI(title=title)

    # Add previously-specified middlewares (kept for compatibility)
    for mw in middlewares:
        app.add_middleware(mw.cls, **mw.kwargs)

    public_paths = set(auth_allow_anonymous or ())

    if token_service:
        # Use our own allowlist-aware middleware to avoid 401 on health/otp endpoints.
        app.add_middleware(
            _KernelAuthMiddleware,  # ASGI-style middleware
            token_service=token_service,
            allowlist=public_paths,
        )

    return app


def mount_routers(app: FastAPI, routers: list) -> None:
    for r in routers:
        app.include_router(r)
