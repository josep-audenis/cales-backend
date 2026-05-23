"""
Orchestrate full recommendation: fetch data → forecast → signals → decision.
"""

from __future__ import annotations

from app.data.ingestion import get_cala_signals, get_price_history
from app.decision.explanation import build_drivers, build_explanation
from app.decision.scoring import decide_action
from app.features.material_profiles import get_profile
from app.features.priority_profiles import get_priority_profile
from app.forecasting.fallback_model import build_forecast
from app.schemas.common import MaterialKey, PriorityProfileKey
from app.schemas.recommendation import ForecastBrief, Recommendation, RecommendationRequest
from app.signals.price_momentum_signal import get_price_momentum_signal
from app.signals.seasonality_signal import get_seasonality_signal


def get_recommendation(req: RecommendationRequest) -> Recommendation:
    mat = req.material
    profile = get_profile(mat)
    priority = get_priority_profile(req.priority_profile)

    # Data
    history = get_price_history(mat.value, lookback_days=365)
    cala_signals = get_cala_signals(mat.value)

    # Internal signals
    prices = [p.price for p in history]
    momentum_signal = get_price_momentum_signal(prices)
    seasonality_signal = get_seasonality_signal(mat.value)

    all_signals = cala_signals + [momentum_signal, seasonality_signal]

    # Forecast
    history_tuples = [(p.date, p.price) for p in history]
    _, forecast_summary = build_forecast(history_tuples, req.horizon_days, all_signals)

    # Decision
    action, scores = decide_action(forecast_summary, all_signals, profile, priority)

    # Hedge horizon: weighted avg signal horizon, clamped [30, 90]
    if all_signals:
        weighted_horizon = sum(
            s.horizon_days * (s.confidence / 100) for s in all_signals
        ) / max(sum(s.confidence / 100 for s in all_signals), 1)
        horizon_days = int(max(30, min(90, weighted_horizon)))
    else:
        horizon_days = req.horizon_days

    drivers = build_drivers(all_signals)
    explanation = build_explanation(action, forecast_summary, horizon_days, scores["confidence"])

    return Recommendation(
        material=mat,
        priority_profile=req.priority_profile,
        action=action,
        horizon_days=horizon_days,
        confidence=scores["confidence"],
        risk_score=scores["adjusted_upside_risk"],
        opportunity_score=scores["opportunity"],
        forecast_summary=ForecastBrief(
            expected_change_pct=forecast_summary.expected_change_pct,
            range_low_pct=forecast_summary.range_low_pct,
            range_high_pct=forecast_summary.range_high_pct,
        ),
        main_drivers=drivers,
        explanation=explanation,
    )
