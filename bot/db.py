from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    credits: Mapped[int] = mapped_column(Integer, default=10)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class JobRecord(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    service: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    credits: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    credits: Mapped[int] = mapped_column(Integer)
    proof_file_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ServiceConfig(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), index=True)
    credits: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


async def init_db(database_url: str):
    if database_url.startswith("sqlite:///"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
