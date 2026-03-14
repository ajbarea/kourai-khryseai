"""SQLAlchemy 2.0 models — mapped_column declarative style."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings

engine = create_async_engine(str(settings.database_url))
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models."""


class Item(Base):
    """Example model — replace with your domain entity."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
