"""
──────────────────────────────────────────────────────────────
Default Kernel Router: Health, DB, Metrics, Info
──────────────────────────────────────────────────────────────
Purpose:
    Provide universal operational endpoints for all kernel-based apps.

Exports:
    router → FastAPI APIRouter instance
──────────────────────────────────────────────────────────────
"""

import time
import platform
from fastapi import APIRouter
from sqlalchemy import text
from product_kernel.db.context import get_session

_router_start_time = time.time()
_request_counter = 0

router = APIRouter(prefix="", tags=["system"])

@router.get("/healthz")
async def healthz():
    """Simple health check endpoint."""
    return {"ok": True, "uptime": round(time.time() - _router_start_time, 1)}

@router.get("/dbz")
async def db_health():
    """Verify DB connectivity using the current AsyncSession."""
    try:
        db = get_session()
        res = await db.execute(text("SELECT version()"))
        version = res.scalar_one()
        return {"db_ok": True, "version": version}
    except Exception as e:
        return {"db_ok": False, "error": str(e)}

@router.get("/metrics")
async def metrics():
    """Return lightweight runtime stats (uptime, request count)."""
    uptime = round(time.time() - _router_start_time, 1)
    return {
        "uptime_seconds": uptime,
        "requests": _request_counter,
        "python": platform.python_version(),
    }

@router.get("/info")
async def info():
    """Kernel + app build info (environment, version)."""
    import os
    return {
        "app": os.getenv("APP_NAME", "unknown"),
        "kernel_version": "0.1.0",
        "python": platform.python_version(),
    }
