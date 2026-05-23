"""
Core decision engine scoring.
Implements the logic from wiki/concepts/decision-engine.md exactly.
"""

from __future__ import annotations

from app.features.priority_profiles import PriorityProfile
from app.schemas.common import Action, Direction, Hedgeable
from app.schemas.forecast import ForecastSummary
from app.schemas.material import Material
from app.schemas.signal import Signal


def _signal_score(signals: list[Signal], name: str) -> float:
    """Weighted score for a named signal (or 0 if absent)."""
    matching = [s for s in signals if s.name == name]
    if not matching:
        return 0.0
    s = matching[0]
    sign = 1.0 if s.direction == Direction.BULLISH else (-1.0 if s.direction == Direction.BEARISH else 0.0)
    return sign * s.score * (s.confidence / 100)


def compute_forecast_pressure(summary: ForecastSummary) -> float:
    """0–100: upward pressure from forecast."""
    direction_sign = 1.0 if summary.direction == "upward" else (-1.0 if summary.direction == "downward" else 0.0)
    magnitude = min(abs(summary.expected_change_pct) * 2.5, 100.0)
    return max(0.0, direction_sign * magnitude)


def compute_external_risk(signals: list[Signal], material: Material) -> float:
    """0–100: weighted external risk from Cala signals."""
    weight_map = material.weights.model_dump()
    total = 0.0
    weight_sum = 0.0
    for s in signals:
        w = weight_map.get(s.name, 0.0)
        if w == 0.0:
            continue
        sign = 1.0 if s.direction == Direction.BULLISH else (-1.0 if s.direction == Direction.BEARISH else 0.0)
        total += w * sign * s.score * (s.confidence / 100)
        weight_sum += w
    if weight_sum == 0:
        return 0.0
    return max(0.0, min(100.0, total / weight_sum * 100))


def compute_supply_risk(signals: list[Signal], criticality: float) -> float:
    """0–100: supply chain risk scaled by material criticality."""
    supply_score = _signal_score(signals, "supply_chain")
    geo_score = _signal_score(signals, "geopolitical_risk")
    raw = (supply_score * 0.5 + geo_score * 0.5)
    return max(0.0, min(100.0, raw * criticality))


def compute_opportunity(summary: ForecastSummary, signals: list[Signal]) -> float:
    """0–100: downside opportunity (price might fall — good time to wait)."""
    downside = max(0.0, -summary.expected_change_pct * 2.5)  # downward forecast
    momentum = max(0.0, -_signal_score(signals, "price_momentum"))
    return min(100.0, downside * 0.6 + momentum * 0.4)


def compute_uncertainty(summary: ForecastSummary, signals: list[Signal]) -> float:
    """0–100: combined uncertainty."""
    forecast_unc = summary.uncertainty * 100
    if signals:
        avg_conf = sum(s.confidence for s in signals) / len(signals)
        signal_unc = 100 - avg_conf
    else:
        signal_unc = 50.0
    return min(100.0, forecast_unc * 0.6 + signal_unc * 0.4)


def compute_confidence(summary: ForecastSummary, signals: list[Signal]) -> float:
    """0–100: inverse of uncertainty."""
    return 100.0 - compute_uncertainty(summary, signals)


def decide_action(
    summary: ForecastSummary,
    signals: list[Signal],
    material: Material,
    priority: PriorityProfile,
) -> tuple[Action, dict[str, float]]:
    """Returns (action, scores_dict)."""
    fp = compute_forecast_pressure(summary)
    er = compute_external_risk(signals, material)
    sr = compute_supply_risk(signals, material.criticality)
    opp = compute_opportunity(summary, signals)
    unc = compute_uncertainty(summary, signals)
    conf = compute_confidence(summary, signals)

    adj_upside = (0.35 * fp + 0.30 * er + 0.25 * sr + 0.10 * unc) * priority.upside_risk_weight
    adj_supply = sr * priority.supply_risk_weight
    adj_opp = opp * priority.downside_opportunity_weight
    adj_unc = unc * priority.uncertainty_penalty

    # Gate HEDGE by hedgeability
    can_hedge = material.hedgeable in (Hedgeable.YES, Hedgeable.PARTIAL)

    if adj_upside > 75 and adj_unc > 50 and can_hedge:
        action = Action.HEDGE
    elif adj_upside > 70 and conf > 60:
        action = Action.BUY_NOW
    elif adj_opp > 65 and adj_supply < 50:
        action = Action.WAIT
    else:
        action = Action.MONITOR

    # PET not hedgeable → collapse HEDGE to BUY_NOW
    if action == Action.HEDGE and not can_hedge:
        action = Action.BUY_NOW

    scores = {
        "forecast_pressure": round(fp, 1),
        "external_risk": round(er, 1),
        "supply_risk": round(sr, 1),
        "opportunity": round(opp, 1),
        "uncertainty": round(unc, 1),
        "confidence": round(conf, 1),
        "adjusted_upside_risk": round(adj_upside, 1),
    }
    return action, scores
