"""Fetch + normalize price history and Cala signals for a material."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from app.schemas.forecast import PricePoint
from app.schemas.signal import Signal

log = logging.getLogger("app.data.ingestion")

# Materials whose price data has a fixed end date (CSV-backed, not live)
_BARLEY_MATERIALS = {"barley"}


def get_price_history(material: str, lookback_days: int = 365) -> list[PricePoint]:
    try:
        from app.api.routes.prices import get_prices

        # Barley: end_date=None → defaults to last CSV date
        # All others: end_date=today so live data is fetched up to now
        if material in _BARLEY_MATERIALS:
            end_date = None
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")

        result = get_prices(commodity=material, days_back=lookback_days, end_date=end_date)
        points_raw = result.get("historicalData", {}).get("points", [])
        if not points_raw:
            raise ValueError("empty historicalData.points")

        points = [
            PricePoint(
                date=datetime.strptime(p["date"], "%Y-%m-%d").date(),
                price=float(p["value"]),
            )
            for p in points_raw
        ]
        log.info("get_price_history %s: %d points from get_prices", material, len(points))
        return points
    except Exception as exc:
        log.warning("get_price_history %s failed (%s) — using mock", material, exc)
        base_price = {"aluminium": 2400.0, "pet": 1100.0, "energy": 35.0, "barley": 210.0}.get(material, 100.0)
        now = datetime.now()
        history = []
        p = base_price
        for i in range(lookback_days, -1, -1):
            dt = (now - timedelta(days=i)).date()
            history.append(PricePoint(date=dt, price=p))
            p *= (1.0 + random.gauss(0, 0.02))
        return history


def get_cala_signals(material: str) -> list[Signal]:
    return []
