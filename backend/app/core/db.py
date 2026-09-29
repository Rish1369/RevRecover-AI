"""
Async SQLAlchemy engine + session factory.

RLS integration: before each query we set the Postgres session variable
`app.current_merchant_id` so that every RLS policy fires automatically
without any application-layer filtering.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uuid

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event

from app.core.settings import get_settings

settings = get_settings()

from sqlalchemy.pool import NullPool

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


async def get_db(merchant_id: uuid.UUID | None = None) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a scoped AsyncSession.

    If `merchant_id` is supplied (extracted from the auth token / path),
    the Postgres session variable is set so RLS policies fire automatically.
    """
    async with AsyncSessionLocal() as session:
        if merchant_id:
            # SET is DDL — PostgreSQL does not support bind params here.
            # UUIDs are safe to interpolate (only hex + hyphens).
            await session.execute(
                text(f"SET LOCAL app.current_merchant_id = '{merchant_id}'")
            )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session(merchant_id: uuid.UUID | None = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Context-manager version for use outside FastAPI dependency injection
    (e.g. Celery tasks, seed scripts).
    """
    async with AsyncSessionLocal() as session:
        if merchant_id:
            await session.execute(
                text(f"SET LOCAL app.current_merchant_id = '{merchant_id}'")
            )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
