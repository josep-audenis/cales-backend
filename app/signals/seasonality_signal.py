"""Simple calendar-based seasonality signal per material."""

from __future__ import annotations

import math
from datetime import date

from app.schemas.common import Direction
from app.schemas.signal import Signal

# Peak pressure month (1-based) per material — when demand/supply imbalance peaks
_PEAK_MONTH: dict[str, int] = {
    "barley": 7,    # N-hemisphere harvest pressure Jun-Aug
    "energy": 1,    # winter peak Jan
    "aluminium": 4, # construction season ramp
    "pet": 7,       # beverage summer demand
}


def get_seasonality_signal(material: str, reference_date: date | None = None) -> Signal:
    today = reference_date or date.today()
    peak_month = _PEAK_MONTH.get(material, 6)

    # Distance from peak in months (circular), range [0, 6]
    month_diff = abs(today.month - peak_month)
    month_diff = min(month_diff, 12 - month_diff)

    # Score: 100 at peak, 0 at 6 months away
    score = round(100 * math.cos(math.pi * month_diff / 6) ** 2, 1)
    direction = Direction.BULLISH if score > 50 else (Direction.BEARISH if score < 20 else Direction.NEUTRAL)

    return Signal(
        name="seasonality",
        direction=direction,
        score=score,
        confidence=70.0,
        horizon_days=30,
        source="Internal",
        evidence=[f"Seasonal peak for {material} in month {peak_month}; currently month {today.month}."],
    )
