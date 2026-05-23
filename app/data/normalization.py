"""Convert raw Cala prices/events into internal domain objects."""

from __future__ import annotations

from datetime import datetime

from app.clients.cala_client import CalaEvent, CalaPricePoint
from app.schemas.forecast import PricePoint
from app.schemas.signal import Signal


def price_points_to_schema(points: list[CalaPricePoint]) -> list[PricePoint]:
    return [PricePoint(date=p.date, price=p.price) for p in points]


def cala_event_to_signal(event: CalaEvent) -> Signal:
    return Signal(
        name=event.event_type,
        direction=event.direction,  # type: ignore[arg-type]
        score=round(event.severity * 100, 1),
        confidence=round(event.confidence * 100, 1),
        horizon_days=event.horizon_days,
        source=event.source,
        evidence=[event.summary] if event.summary else [],
        observed_at=datetime.combine(event.date, datetime.min.time()),
    )


def cala_events_to_signals(events: list[CalaEvent]) -> list[Signal]:
    return [cala_event_to_signal(e) for e in events]
