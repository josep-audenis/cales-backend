"""Fetch + normalize price history and Cala signals for a material."""

from __future__ import annotations

from app.clients.cala_client import CalaClient
from app.data.normalization import cala_events_to_signals, price_points_to_schema
from app.schemas.forecast import PricePoint
from app.schemas.signal import Signal

_client = CalaClient()


def get_price_history(material: str, lookback_days: int = 365) -> list[PricePoint]:
    raw = _client.get_prices(material, lookback_days)
    return price_points_to_schema(raw)


def get_cala_signals(material: str) -> list[Signal]:
    events = _client.get_events(material)
    return cala_events_to_signals(events)
