"""
──────────────────────────────────────────────────────────────────────────────
product_kernel.testing.fixtures
──────────────────────────────────────────────────────────────────────────────
Purpose:
    Provide reusable pytest fixtures for kernel-based applications.

Exports:
    - async_session  → yields a clean AsyncSession per test
    - override_session() → override app.state.async_sessionmaker in FastAPI

Usage in your test:
    from product_kernel.testing.fixtures import async_session

    async def test_repo_create(async_session):
        user = await UsersRepo().create(model=User, name="Alice")
        assert user.id
──────────────────────────────────────────────────────────────────────────────
"""

import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from product_kernel.db.context import set_session, reset_session


# ──────────────────────────────────────────────────────────────
# Utility: normalize_async_url (moved here from lifecycle.py)
# ──────────────────────────────────────────────────────────────
def normalize_async_url(url: str) -> str:
    """
    Convert asyncpg URLs into sync psycopg2 form,
    or ensure 'postgresql+psycopg2://'.
    Used by Alembic and test session creation.
    """
    if not url:
        raise RuntimeError("No DB URL provided.")
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg2")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


# ──────────────────────────────────────────────────────────────
# Event Loop Fixture (session scope)
# ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Ensure pytest-asyncio uses a global event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ──────────────────────────────────────────────────────────────
# AsyncSession Fixture (per test)
# ──────────────────────────────────────────────────────────────
@pytest.fixture()
async def async_session(monkeypatch):
    """
    Provide a clean AsyncSession for each test.
    Uses a test-specific engine (default: 'sqlite+aiosqlite:///:memory:')
    """
    db_url = "sqlite+aiosqlite:///:memory:"
    db_url = normalize_async_url(db_url)
    engine = create_async_engine(db_url, echo=False, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with Session() as session:
        token = set_session(session)
        yield session
        reset_session(token)
        await session.close()

    await engine.dispose()


# ──────────────────────────────────────────────────────────────
# Helper to override app's session factory in tests
# ──────────────────────────────────────────────────────────────
async def override_session(app, session_factory):
    """Helper to override app.state.async_sessionmaker during tests."""
    app.state.async_sessionmaker = session_factory
