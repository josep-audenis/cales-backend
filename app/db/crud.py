"""CRUD helpers for the four DB tables."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from app.db.models import CalaEventDB, MarketSignalDB, PricePointDB, RecommendationLogDB
from app.schemas.recommendation import Recommendation


# ---------------------------------------------------------------------------
# Price history
# ---------------------------------------------------------------------------

def upsert_price_points(session: Session, material: str, points: list[tuple[date, float]]) -> None:
    """Insert price points, skipping any (material, date) pair already stored."""
    if not points:
        return
    rows = [{"material": material, "date": d, "price": p, "fetched_at": datetime.utcnow()} for d, p in points]
    stmt = sqlite_insert(PricePointDB).values(rows).on_conflict_do_nothing(
        constraint="uq_price_material_date"
    )
    session.execute(stmt)
    session.commit()


def get_price_points(session: Session, material: str, lookback_days: int = 365) -> list[PricePointDB]:
    cutoff = date.today() - timedelta(days=lookback_days)
    return list(
        session.exec(
            select(PricePointDB)
            .where(PricePointDB.material == material, PricePointDB.date >= cutoff)
            .order_by(PricePointDB.date)
        ).all()
    )


# ---------------------------------------------------------------------------
# Cala events
# ---------------------------------------------------------------------------

def save_cala_event(session: Session, event: CalaEventDB) -> CalaEventDB:
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def get_cala_events(session: Session, material: str) -> list[CalaEventDB]:
    return list(
        session.exec(
            select(CalaEventDB)
            .where(CalaEventDB.material == material)
            .order_by(CalaEventDB.event_date.desc())
        ).all()
    )


# ---------------------------------------------------------------------------
# Recommendation log
# ---------------------------------------------------------------------------

def log_recommendation(session: Session, rec: Recommendation) -> RecommendationLogDB:
    row = RecommendationLogDB(
        material=rec.material.value,
        priority_profile=rec.priority_profile.value,
        action=rec.action.value,
        horizon_days=rec.horizon_days,
        confidence=rec.confidence,
        risk_score=rec.risk_score,
        opportunity_score=rec.opportunity_score,
        expected_change_pct=rec.forecast_summary.expected_change_pct,
        explanation=rec.explanation,
        drivers_json=json.dumps([d.model_dump() for d in rec.main_drivers]),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_recommendation_history(
    session: Session, material: str, limit: int = 50
) -> list[RecommendationLogDB]:
    return list(
        session.exec(
            select(RecommendationLogDB)
            .where(RecommendationLogDB.material == material)
            .order_by(RecommendationLogDB.created_at.desc())
            .limit(limit)
        ).all()
    )


# ---------------------------------------------------------------------------
# Market signals
# ---------------------------------------------------------------------------

def save_market_signal(session: Session, signal: MarketSignalDB) -> MarketSignalDB:
    session.add(signal)
    session.commit()
    session.refresh(signal)
    return signal


def get_market_signals(
    session: Session,
    material: str | None = None,
    impact: str | None = None,
    limit: int = 100,
) -> list[MarketSignalDB]:
    q = select(MarketSignalDB).order_by(MarketSignalDB.published_at.desc()).limit(limit)
    if material:
        q = q.where(MarketSignalDB.material == material)
    if impact:
        q = q.where(MarketSignalDB.impact == impact)
    return list(session.exec(q).all())
