"""
Testing utilities for product-kernel apps.
──────────────────────────────────────────────────────────────
Provides pytest fixtures and helpers to run isolated async DB sessions.
──────────────────────────────────────────────────────────────
"""
from .fixtures import async_session, override_session

__all__ = ["async_session", "override_session"]
