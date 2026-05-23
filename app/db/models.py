from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class PricePointDB(SQLModel, table=True):
    """Cached price history fetched from Cala.ai or local CSV."""

    __tablename__ = "price_point"
    __table_args__ = (UniqueConstraint("material", "date", name="uq_price_material_date"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    material: str = Field(index=True)
    date: date
    price: float
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class CalaEventDB(SQLModel, table=True):
    """Cached Cala.ai events (market signals from the external feed)."""

    __tablename__ = "cala_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    material: str = Field(index=True)
    event_type: str
    summary: str
    direction: str  # bullish | bearish | neutral
    severity: float
    confidence: float
    horizon_days: int
    event_date: date
    source: str = "Cala.ai"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class RecommendationLogDB(SQLModel, table=True):
    """Audit log of every recommendation produced by the engine."""

    __tablename__ = "recommendation_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    material: str = Field(index=True)
    priority_profile: str
    action: str  # BUY_NOW | WAIT | HEDGE | MONITOR
    horizon_days: int
    confidence: float
    risk_score: float
    opportunity_score: float
    expected_change_pct: float
    explanation: str
    drivers_json: str  # JSON-serialized list[Driver]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MarketSignalDB(SQLModel, table=True):
    """Ingested market news and signals for the live feed."""

    __tablename__ = "market_signal"

    id: Optional[int] = Field(default=None, primary_key=True)
    material: str = Field(index=True)  # MaterialKey or "macro"
    impact: str  # bullish | bearish | neutral
    category: str  # e.g. Sector news, Regulation, Logistics costs …
    headline: str
    detail: str = ""
    source: str
    reliability: str = "medium"  # high | medium | low
    published_at: datetime = Field(default_factory=datetime.utcnow)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
