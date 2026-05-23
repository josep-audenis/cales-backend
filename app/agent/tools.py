"""
Tool registry for the procurement analyst agent.

Tools wrap deterministic services. Cala market intelligence is NOT wrapped
here — it is exposed natively via the Cala MCP server (see app/agent/runtime).
The agent calls knowledge_search / knowledge_query / entity_search directly.

The recommender chain is decomposed into small steps the agent can orchestrate:
  get_price_history -> compute_price_features -> compute_momentum_signal
                    -> build_forecast_summary -> score_and_decide
                    -> generate_explanation
A single-call shortcut `fallback_full_analysis` runs the whole chain.
"""

from __future__ import annotations

from typing import Any

from app.data.ingestion import get_price_history
from app.decision.explanation import build_drivers, build_explanation
from app.decision.recommender import get_recommendation
from app.decision.scoring import decide_action
from app.features.material_profiles import get_profile
from app.features.priority_profiles import get_priority_profile
from app.forecasting.fallback_model import build_forecast
from app.schemas.common import MaterialKey, PriorityProfileKey
from app.schemas.recommendation import RecommendationRequest
from app.schemas.signal import Signal
from app.signals.price_momentum_signal import get_price_momentum_signal
from app.signals.seasonality_signal import get_seasonality_signal

try:
    from agents import function_tool  # type: ignore
except Exception:  # pragma: no cover

    def function_tool(fn):  # type: ignore
        return fn


# ---------------------------------------------------------------------------
# A. Data
# ---------------------------------------------------------------------------


@function_tool
def get_available_materials(noop: str = "") -> dict[str, Any]:
    return {"materials": [m.value for m in MaterialKey]}


@function_tool
def get_price_history_tool(material: str, lookback_days: int = 365) -> dict[str, Any]:
    history = get_price_history(material, lookback_days=lookback_days)
    return {
        "material": material,
        "current_price": history[-1].price if history else None,
        "history": [{"date": p.date.isoformat(), "price": p.price} for p in history],
    }


# ---------------------------------------------------------------------------
# B. Price-derived signals
# ---------------------------------------------------------------------------


@function_tool
def compute_price_features(material: str, lookback_days: int = 365) -> dict[str, Any]:
    history = get_price_history(material, lookback_days=lookback_days)
    prices = [p.price for p in history]
    if len(prices) < 2:
        return {"material": material, "error": "insufficient history"}
    return {
        "material": material,
        "current_price": prices[-1],
        "return_1m": (prices[-1] / prices[-21] - 1) if len(prices) > 21 else None,
        "return_3m": (prices[-1] / prices[-63] - 1) if len(prices) > 63 else None,
        "return_6m": (prices[-1] / prices[-126] - 1) if len(prices) > 126 else None,
        "ma_20": sum(prices[-20:]) / min(20, len(prices)),
        "ma_60": sum(prices[-60:]) / min(60, len(prices)),
        "high_1y": max(prices[-252:]) if len(prices) >= 252 else max(prices),
        "low_1y": min(prices[-252:]) if len(prices) >= 252 else min(prices),
    }


@function_tool
def compute_momentum_signal(material: str) -> dict[str, Any]:
    history = get_price_history(material, lookback_days=365)
    sig = get_price_momentum_signal([p.price for p in history])
    return sig.model_dump(mode="json")


@function_tool
def compute_seasonality_signal_tool(material: str) -> dict[str, Any]:
    return get_seasonality_signal(material).model_dump(mode="json")


# ---------------------------------------------------------------------------
# C. Forecast
# ---------------------------------------------------------------------------


def _signals_from_payload(raw: list[dict[str, Any]]) -> list[Signal]:
    return [Signal(**s) for s in raw]


@function_tool(strict_mode=False)
def build_forecast_summary(
    material: str,
    horizon_days: int = 180,
    extra_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Volatility-cone forecast. `extra_signals` lets the agent inject Cala-derived signals."""
    history = get_price_history(material, lookback_days=365)
    history_tuples = [(p.date, p.price) for p in history]
    momentum = get_price_momentum_signal([p.price for p in history])
    seasonality = get_seasonality_signal(material)
    signals = [momentum, seasonality]
    if extra_signals:
        signals.extend(_signals_from_payload(extra_signals))
    _, summary = build_forecast(history_tuples, horizon_days, signals)
    return summary.model_dump(mode="json")


# ---------------------------------------------------------------------------
# D. Decision
# ---------------------------------------------------------------------------


@function_tool(strict_mode=False)
def score_and_decide(
    material: str,
    priority_profile: str = "balanced",
    horizon_days: int = 180,
    extra_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score signals + forecast and pick BUY_NOW / WAIT / HEDGE / MONITOR."""
    mat_profile = get_profile(MaterialKey(material))
    priority = get_priority_profile(PriorityProfileKey(priority_profile))
    history = get_price_history(material, lookback_days=365)
    history_tuples = [(p.date, p.price) for p in history]
    momentum = get_price_momentum_signal([p.price for p in history])
    seasonality = get_seasonality_signal(material)
    signals = [momentum, seasonality]
    if extra_signals:
        signals.extend(_signals_from_payload(extra_signals))
    _, summary = build_forecast(history_tuples, horizon_days, signals)
    action, scores = decide_action(summary, signals, mat_profile, priority)
    return {
        "material": material,
        "action": action.value,
        "horizon_days": horizon_days,
        "scores": scores,
        "forecast_summary": summary.model_dump(mode="json"),
        "drivers": [d.model_dump(mode="json") for d in build_drivers(signals)],
        "explanation": build_explanation(action, summary, horizon_days, scores["confidence"]),
    }


# ---------------------------------------------------------------------------
# E. One-shot fallback (demo safety net)
# ---------------------------------------------------------------------------


def _run_recommendation(
    material: str, priority_profile: str = "balanced", horizon_days: int = 180
) -> dict[str, Any]:
    req = RecommendationRequest(
        material=MaterialKey(material),
        priority_profile=PriorityProfileKey(priority_profile),
        horizon_days=horizon_days,
    )
    return get_recommendation(req).model_dump(mode="json")


@function_tool
def fallback_full_analysis(
    material: str,
    priority_profile: str = "balanced",
) -> dict[str, Any]:
    """One-shot deterministic recommendation. Use only if smaller tools fail."""
    return _run_recommendation(material, priority_profile, 180)


# ---------------------------------------------------------------------------
# F. Agent control
# ---------------------------------------------------------------------------


@function_tool
def validate_material(material: str) -> dict[str, Any]:
    try:
        MaterialKey(material)
        return {"valid": True, "material": material}
    except ValueError:
        return {
            "valid": False,
            "material": material,
            "allowed": [m.value for m in MaterialKey],
        }


@function_tool
def validate_priority_profile(profile: str) -> dict[str, Any]:
    try:
        PriorityProfileKey(profile)
        return {"valid": True, "profile": profile}
    except ValueError:
        return {
            "valid": False,
            "profile": profile,
            "allowed": [p.value for p in PriorityProfileKey],
        }


@function_tool
def list_capabilities(noop: str = "") -> dict[str, Any]:
    return {
        "capabilities": [
            "Recommend BUY_NOW / WAIT / HEDGE / MONITOR for raw materials",
            "Explain drivers and counter-drivers with evidence sources",
            "Run what-if scenarios and compare materials",
            "Pull live market intelligence from Cala via MCP",
        ],
        "materials": [m.value for m in MaterialKey],
        "priority_profiles": [p.value for p in PriorityProfileKey],
        "cala_mcp_tools": [
            "knowledge_search",
            "knowledge_query",
            "entity_search",
            "entity_introspection",
            "retrieve_entity",
        ],
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    get_price_history_tool,
    build_forecast_summary,
    score_and_decide,
    fallback_full_analysis,
]

__all__ = ["ALL_TOOLS", "_run_recommendation"]
