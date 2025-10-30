# product_kernel/__init__.py
"""
product_kernel
──────────────────────────────────────────────────────────────
A flexible FastAPI + SQLAlchemy kernel.
Provides:
    - DB lifecycle (sync/async)
    - Context-based session management
    - Declarative Base
    - JWT & Principal
    - Optional Alembic integration
    - Optional seed & model discovery
──────────────────────────────────────────────────────────────
"""

__version__ = "0.2.0"

from product_kernel.web.api import create_app, mount_routers
from product_kernel.autodiscover import discover_models, discover_seed_scripts

__all__ = [
    "create_app",
    "mount_routers",
    "discover_models",
    "discover_seed_scripts",
]
