# central_server/database.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Database Layer
# SQLite for development; swap DATABASE_URL in .env for
# PostgreSQL in production:
#   DATABASE_URL=postgresql+asyncpg://user:pass@host/rescuegrid
# ─────────────────────────────────────────────────────────────

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text
from datetime import datetime, timezone

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./rescuegrid.db"
)

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

# ── ORM Tables ───────────────────────────────────────────────

class AmbulanceRecord(Base):
    __tablename__ = "ambulances"
    id             = Column(String, primary_key=True)  # e.g. "AMB-001"
    last_lat       = Column(Float)
    last_lon       = Column(Float)
    speed_kmh      = Column(Float, default=0)
    heading        = Column(Float, default=0)
    criticality    = Column(Integer, default=3)
    priority_active= Column(Boolean, default=False)
    last_seen      = Column(DateTime, default=datetime.now)
    active         = Column(Boolean, default=True)

class JunctionRecord(Base):
    __tablename__ = "junctions"
    id         = Column(String, primary_key=True)   # e.g. "JN001"
    name       = Column(String)
    lat        = Column(Float)
    lon        = Column(Float)
    url        = Column(String)                     # http://192.168.x.x:5000
    state      = Column(String, default="normal")   # normal/emergency/failsafe
    updated_at = Column(DateTime, default=datetime.now)

class SignalLog(Base):
    __tablename__ = "signal_logs"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    junction_id  = Column(String)
    ambulance_id = Column(String)
    state        = Column(String)
    issued_at    = Column(DateTime)
    acked_at     = Column(DateTime, nullable=True)
    success      = Column(Boolean, nullable=True)
    notes        = Column(Text, nullable=True)

class GPSLog(Base):
    __tablename__ = "gps_logs"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    ambulance_id = Column(String)
    lat          = Column(Float)
    lon          = Column(Float)
    speed_kmh    = Column(Float)
    heading      = Column(Float)
    recorded_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# ── Helpers ──────────────────────────────────────────────────

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
