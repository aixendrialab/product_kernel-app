"""
Built-in kernel routers.
──────────────────────────────────────────────────────────────
Currently includes:
 - /healthz
 - /dbz
 - /metrics
 - /info
──────────────────────────────────────────────────────────────
"""
from .health_router import router as health_router

__all__ = ["health_router"]
