"""
Volatility-cone fallback forecast.
Produces median (moving-average trend) + asymmetric uncertainty band.
No external deps beyond stdlib + basic math.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from app.schemas.forecast import ForecastDirection, ForecastPoint, ForecastSummary
from app.schemas.signal import Signal


def _net_signal_pressure(signals: list[Signal]) -> float:
    """Weighted directional pressure from signals, range [-1, 1]."""
    if not signals:
        return 0.0
    total_weight = sum(s.confidence for s in signals)
    if total_weight == 0:
        return 0.0
    pressure = 0.0
    for s in signals:
        sign = 1.0 if s.direction == "bullish" else (-1.0 if s.direction == "bearish" else 0.0)
        pressure += sign * (s.score / 100) * (s.confidence / total_weight)
    return max(-1.0, min(1.0, pressure))


def build_forecast(
    history: list[tuple[date, float]],
    horizon_days: int,
    signals: list[Signal],
) -> tuple[list[ForecastPoint], ForecastSummary]:
    """
    history: list of (date, price) sorted ascending.
    Returns forecast points + summary.
    """
    if not history:
        raise ValueError("history must not be empty")

    prices = [p for _, p in history]
    returns = [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
    ]

    # rolling vol (last 60 days or all available)
    window = returns[-60:] if len(returns) >= 60 else returns
    if len(window) > 1:
        mean_r = sum(window) / len(window)
        variance = sum((r - mean_r) ** 2 for r in window) / (len(window) - 1)
        daily_vol = math.sqrt(variance)
    else:
        daily_vol = 0.01

    # MA trend from last 20 days — use median daily log-return, cap at ±0.10% per day
    trend_window = prices[-20:] if len(prices) >= 20 else prices
    raw_drift = (trend_window[-1] / trend_window[0]) ** (1 / max(len(trend_window) - 1, 1)) - 1
    daily_drift = max(-0.0005, min(0.0005, raw_drift))  # cap: ±0.05%/day = ±4.5% over 90d

    net_pressure = _net_signal_pressure(signals)
    # Signal nudge: ±1% total over horizon
    signal_adjustment = net_pressure * 0.01

    last_date, last_price = history[-1]
    forecast_points: list[ForecastPoint] = []

    # Cap grows with sqrt(step/horizon_days): monotone, reaches max_total_swing at final step
    max_total_swing = 0.18

    for step in range(1, horizon_days + 1):
        fc_date = last_date + timedelta(days=step)
        # Uncapped vol — step_cap below is sole ceiling
        horizon_vol = daily_vol * math.sqrt(step)

        median = last_price * (1 + daily_drift) ** step * (1 + signal_adjustment)

        risk_mult = 1.0 + abs(net_pressure) * 0.25
        if net_pressure > 0:
            upper = last_price * (1 + 1.96 * horizon_vol * 1.2 * risk_mult)
            lower = last_price * (1 - 1.96 * horizon_vol * 0.8)
        else:
            upper = last_price * (1 + 1.96 * horizon_vol * 0.8)
            lower = last_price * (1 - 1.96 * horizon_vol * 1.2 * risk_mult)

        # Single monotone ceiling: both proportional to sqrt(step) → always growing
        step_cap = max_total_swing * math.sqrt(step / horizon_days)
        upper = min(upper, last_price * (1 + step_cap))
        lower = max(lower, last_price * (1 - step_cap))
        # Ensure median stays within band
        median = max(lower, min(upper, median))

        forecast_points.append(ForecastPoint(
            date=fc_date,
            median=round(median, 2),
            lower=round(lower, 2),
            upper=round(upper, 2),
        ))

    final_median = forecast_points[-1].median
    expected_change_pct = round((final_median - last_price) / last_price * 100, 2)
    final_lower = forecast_points[-1].lower
    final_upper = forecast_points[-1].upper
    range_low_pct = round((final_lower - last_price) / last_price * 100, 2)
    range_high_pct = round((final_upper - last_price) / last_price * 100, 2)

    if expected_change_pct > 1.0:
        direction = ForecastDirection.UPWARD
    elif expected_change_pct < -1.0:
        direction = ForecastDirection.DOWNWARD
    else:
        direction = ForecastDirection.FLAT

    avg_band_pct = (range_high_pct - range_low_pct) / 2 / 100
    uncertainty = round(min(avg_band_pct / 0.20, 1.0), 3)  # normalise: 20% band = max uncertainty

    summary = ForecastSummary(
        expected_change_pct=expected_change_pct,
        range_low_pct=range_low_pct,
        range_high_pct=range_high_pct,
        direction=direction,
        uncertainty=uncertainty,
    )

    return forecast_points, summary
