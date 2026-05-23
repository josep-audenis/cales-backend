"""
Assemble a full Forecast response for a material.
Uses fallback_model today; swap in TimesFM by replacing build_forecast call.
"""

from __future__ import annotations

from app.data.ingestion import get_cala_signals, get_price_history
from app.forecasting.fallback_model import build_forecast
from app.schemas.forecast import CalaEventMark, Forecast
from app.schemas.common import MaterialKey


def get_forecast(material: MaterialKey, horizon_days: int = 180) -> Forecast:
    mat = material.value
    history_schema = get_price_history(mat, lookback_days=365)
    signals = get_cala_signals(mat)

    history_tuples = [(p.date, p.price) for p in history_schema]
    forecast_points, summary = build_forecast(history_tuples, horizon_days, signals)

    # Derive Cala event markers from signals that have observed_at
    events: list[CalaEventMark] = []
    from app.clients.cala_client import CalaClient
    raw_events = CalaClient().get_events(mat)
    for e in raw_events:
        events.append(CalaEventMark(
            date=e.date,
            label=f"{e.event_type.replace('_', ' ').title()}: {e.summary[:60]}",
            direction=e.direction,
        ))

    return Forecast(
        material=material,
        horizon_days=horizon_days,
        history=history_schema,
        forecast=forecast_points,
        summary=summary,
        events=events,
    )
