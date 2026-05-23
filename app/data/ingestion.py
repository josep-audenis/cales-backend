"""Fetch + normalize price history and Cala signals for a material."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from app.schemas.forecast import PricePoint
from app.schemas.signal import Signal

log = logging.getLogger("app.data.ingestion")


def get_price_history(material: str, lookback_days: int = 365) -> list[PricePoint]:
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    try:
        from app.api.routes.prices import FETCHERS
        fetcher = FETCHERS.get(material)
        if fetcher is None:
            raise ValueError(f"no fetcher for {material}")
        df = fetcher(start, end)
        if df.empty:
            raise ValueError("empty dataframe")
        points = [
            PricePoint(date=row["date"].date(), price=float(row["price"]))
            for _, row in df.iterrows()
        ]
        log.info("get_price_history %s: %d points from real data", material, len(points))
        return points
    except Exception as exc:
        log.warning("get_price_history %s real data failed (%s) — using mock", material, exc)
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
