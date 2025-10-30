# product_kernel/db/session.py
"""
Lightweight AsyncSession context for CLI/Jobs/Tests
────────────────────────────────────────────
Creates sessions lazily using db.engine utilities.
Safe to call outside FastAPI.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from product_kernel.db.engine import get_sessionmaker

@asynccontextmanager
async def async_session() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as sess:
        yield sess

@asynccontextmanager
async def session_in_transaction() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm.begin() as sess:
        yield sess

async def healthcheck() -> bool:
    async with async_session() as s:
        await s.execute(text("SELECT 1"))
    return True
