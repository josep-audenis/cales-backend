"""Fetch + normalize price history and Cala signals for a material."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from app.schemas.forecast import PricePoint
from app.schemas.signal import Signal

def get_price_history(material: str, lookback_days: int = 365) -> list[PricePoint]:
    # Mock random walk
    base_price = {"aluminium": 2400.0, "pet": 1100.0, "energy": 35.0, "barley": 210.0}.get(material, 100.0)
    now = datetime.now()
    history = []
    p = base_price
    for i in range(lookback_days, -1, -1):
        dt = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        history.append(PricePoint(date=dt, price=p))
        p *= (1.0 + random.gauss(0, 0.02))
    return history

def get_cala_signals(material: str) -> list[Signal]:
    return []

