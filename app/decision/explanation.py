"""Generate business-readable explanation + top drivers."""

from __future__ import annotations

from app.schemas.common import Action, Direction
from app.schemas.forecast import ForecastSummary
from app.schemas.recommendation import Driver
from app.schemas.signal import Signal

_ACTION_TEMPLATES: dict[Action, str] = {
    Action.BUY_NOW: (
        "Lock in supply now. Forecast shows {change} price movement over {horizon} days "
        "with {conf:.0f}% confidence. Risk of waiting outweighs potential savings."
    ),
    Action.WAIT: (
        "Prices expected to ease {change} over {horizon} days. Supply risk is low — "
        "deferring purchase likely yields better cost."
    ),
    Action.HEDGE: (
        "High uncertainty with upward price pressure ({change} expected). "
        "Partial hedging recommended over {horizon} days to cap worst-case cost."
    ),
    Action.MONITOR: (
        "Signals are mixed or low-confidence. No strong case for immediate action. "
        "Review again in 2–4 weeks or when new Cala.ai events arrive."
    ),
}


def build_drivers(signals: list[Signal], top_n: int = 3) -> list[Driver]:
    """Top signals ranked by score × confidence, expressed as Drivers."""
    ranked = sorted(
        signals,
        key=lambda s: s.score * (s.confidence / 100),
        reverse=True,
    )[:top_n]

    drivers: list[Driver] = []
    for s in ranked:
        sign = 1.0 if s.direction == Direction.BULLISH else (-1.0 if s.direction == Direction.BEARISH else 0.0)
        impact = round(sign * s.score * (s.confidence / 100), 1)
        note = s.evidence[0][:120] if s.evidence else None
        drivers.append(Driver(
            signal=s.name,
            direction=s.direction,
            impact=impact,
            source=s.source,
            note=note,
        ))
    return drivers


def build_explanation(
    action: Action,
    summary: ForecastSummary,
    horizon_days: int,
    confidence: float,
) -> str:
    template = _ACTION_TEMPLATES[action]
    change_pct = summary.expected_change_pct
    change_str = f"+{change_pct:.1f}%" if change_pct >= 0 else f"{change_pct:.1f}%"
    return template.format(change=change_str, horizon=horizon_days, conf=confidence)
