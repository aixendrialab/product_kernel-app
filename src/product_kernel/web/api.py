# src/product_kernel/web/api.py
from __future__ import annotations
import os, time
from typing import Iterable, Optional, Any, List, Dict, Set
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import json
from starlette.requests import Request
from starlette.responses import JSONResponse

from product_kernel.db.middleware import DBMiddleware
from product_kernel.api.health_router import router as kernel_health_router
from product_kernel.security.jwt_provider import get_provider
from product_kernel.security.principal import Principal
from product_kernel.web.errors import add_error_handlers


"""
──────────────────────────────────────────────────────────────
product_kernel.web.api
──────────────────────────────────────────────────────────────
Purpose:
    Unified FastAPI app factory for all product_kernel-based
    systems (TOS, PetCare, Campus, etc.).

Responsibilities:
    • Attach unified DB lifecycle + session middleware
    • Setup optional JWT authentication (if required)
    • Add CORS and global error handlers
    • Include standard kernel routers (health, metrics, etc.)
    • Provide optional request logging middleware
──────────────────────────────────────────────────────────────
"""


# ──────────────────────────────────────────────────────────────
# Request Logging Middleware (with inline JWT decoding)
# ──────────────────────────────────────────────────────────────
class RequestLoggerMiddleware:
    """Logs request details, body (JSON-safe), and decodes JWT if available."""

    def __init__(self, app, allowlist: Set[str]):
        self.app = app
        self.token_service = get_provider()
        self.allowlist = allowlist

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)
        path = request.url.path
        start_time = time.time()
        headers = dict(request.headers)

        # ──────────────────────────────────────────────
        # Capture the raw body before it’s consumed
        # ──────────────────────────────────────────────
        try:
            body_bytes = await request.body()
            body_str = body_bytes.decode("utf-8") if body_bytes else ""
            if len(body_str) > 800:
                body_str = body_str[:800] + "… [truncated]"
            try:
                parsed = json.loads(body_str) if body_str else None
                body_repr = json.dumps(parsed, indent=None) if parsed is not None else "<empty>"
            except Exception:
                body_repr = body_str or "<non-JSON body>"
        except Exception:
            body_bytes = b""
            body_repr = "<body read error>"

        print(f"🛰️ [REQ] {request.method} {path}")
        print(f"   ↳ Authorization: {headers.get('authorization', '<none>')}")
        print(f"   ↳ Origin: {headers.get('origin')}")
        print(f"   ↳ Content-Type: {headers.get('content-type')}")
        print(f"   ↳ Referer: {headers.get('referer')}")
        print(f"   ↳ Body: {body_repr}")

        # Reinject the body so downstream handlers can still read it
        async def receive_reconstructed():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        scope["app"] = self.app  # ensure scope continuity
        request._receive = receive_reconstructed  # type: ignore

        # ──────────────────────────────────────────────
        # Allowlisted endpoints skip auth
        # ──────────────────────────────────────────────
        if any(path.startswith(p) for p in self.allowlist):
            return await self.app(scope, receive_reconstructed, send)

        # ──────────────────────────────────────────────
        # JWT handling
        # ──────────────────────────────────────────────
        auth = headers.get("authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return await JSONResponse({"detail": "Missing Authorization"}, status_code=401)(
                scope, receive_reconstructed, send
            )

        token = auth.split(" ", 1)[1]
        try:
            claims = self.token_service.decode(token)
            principal = Principal.from_claims(claims)
            request.state.principal = principal
            request.state.claims = claims
            request.state.uid = claims.get("uid") or claims.get("sub")
            print(
                f"👤 Principal: {request.state.principal.uid} "
                f"(tenant={request.state.principal.tenant_id}, "
                f"roles={request.state.principal.roles})"
            )
        except Exception as e:
            print(f"⚠️ JWT decode error: {e}")
            return await JSONResponse({"detail": "Invalid token"}, status_code=401)(
                scope, receive_reconstructed, send
            )

        # ──────────────────────────────────────────────
        # Continue request flow
        # ──────────────────────────────────────────────
        try:
            response = await self.app(scope, receive_reconstructed, send)
        finally:
            elapsed = (time.time() - start_time) * 1000
            print(f"🛰️ [RES] {request.method} {path} ({elapsed:.2f} ms)\n")

        return response
    
# ──────────────────────────────────────────────────────────────
# App Factory
# ──────────────────────────────────────────────────────────────
def create_app(
    *,
    title: str = "App",
    db_url: Optional[str] = None,
    token_service: Any = None,
    middlewares: Optional[List[Dict[str, Any]]] = None,
    auth_allow_anonymous: Iterable[str] = ("/healthz",),
    cors_allow_origins: Iterable[str] = ("*",),
    enable_request_logging: bool = True,
) -> FastAPI:
    """
    Centralized FastAPI factory for product_kernel apps.
    Handles DB, JWT, CORS, errors, and routers.
    """
    app = FastAPI(title=title)
    middlewares = middlewares or []

    # ──────────────────────────────────────────────────────────
    # 🔹 Unified DB middleware (engine + session)
    # ──────────────────────────────────────────────────────────
    db_url = db_url or os.getenv("DATABASE_URL")
    if db_url:
        app.add_middleware(DBMiddleware, db_url=db_url)
        print(f"✅ [kernel] Unified DB middleware active for {db_url}")
    else:
        print("⚠️ [kernel] No DATABASE_URL provided — DB middleware skipped")

    # ──────────────────────────────────────────────────────────
    # 🔹 Custom middlewares (before request logger)
    # ──────────────────────────────────────────────────────────
    for mw in middlewares:
        app.add_middleware(mw["cls"], **mw.get("kwargs", {}))

    # ──────────────────────────────────────────────────────────
    # 🔹 Request Logger (auth integrated)
    # ──────────────────────────────────────────────────────────
    allowlist = set(auth_allow_anonymous or [])
    if enable_request_logging:
        app.add_middleware(RequestLoggerMiddleware, allowlist=allowlist)
        print("✅ [kernel] Request logger active")

    # ──────────────────────────────────────────────────────────
    # 🔹 CORS Setup
    # ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    print("✅ [kernel] CORS enabled")

    # ──────────────────────────────────────────────────────────
    # 🔹 Global Error Handlers
    # ──────────────────────────────────────────────────────────
    add_error_handlers(app)
    print("✅ [kernel] Global error handlers registered")

    # ──────────────────────────────────────────────────────────
    # 🔹 Kernel Health Router
    # ──────────────────────────────────────────────────────────
    app.include_router(kernel_health_router)
    print("✅ [kernel] Health endpoint mounted")

    # ──────────────────────────────────────────────────────────
    # 🔹 Summary
    # ──────────────────────────────────────────────────────────
    print("🧩 FINAL MIDDLEWARE STACK:")
    for mw in app.user_middleware:
        print("   -", mw.cls.__name__)

    print(f"🚀 [kernel] App '{title}' ready.")
    return app


# ──────────────────────────────────────────────────────────────
# Router Helper
# ──────────────────────────────────────────────────────────────
def mount_routers(app: FastAPI, routers: list) -> None:
    """Mount multiple routers safely."""
    for r in routers:
        app.include_router(r)
