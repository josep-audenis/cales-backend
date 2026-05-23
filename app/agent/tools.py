"""
Tool registry for the procurement analyst agent.

Tools wrap existing deterministic services. Each tool returns JSON-serializable
dicts. Decorated with @function_tool from the OpenAI Agents SDK so the agent
can call them.

If `openai-agents` is not installed yet, the @function_tool decorator is
replaced with a no-op so this module still imports (callers can use the raw
functions directly).
"""

from __future__ import annotations

from typing import Any

from app.clients.cala_client import CalaClient
from app.data.ingestion import get_cala_signals, get_price_history
from app.decision.recommender import get_recommendation
from app.schemas.common import MaterialKey, PriorityProfileKey
from app.schemas.recommendation import RecommendationRequest

try:  # OpenAI Agents SDK
    from agents import function_tool  # type: ignore
except Exception:  # pragma: no cover - SDK optional at scaffold time

    def function_tool(fn):  # type: ignore
        return fn


# ---------------------------------------------------------------------------
# A. Data ingestion
# ---------------------------------------------------------------------------


@function_tool
def get_available_materials() -> dict[str, Any]:
    return {"materials": [m.value for m in MaterialKey]}


@function_tool
def get_price_history_tool(material: str, lookback_days: int = 365) -> dict[str, Any]:
    history = get_price_history(material, lookback_days=lookback_days)
    return {
        "material": material,
        "current_price": history[-1].price if history else None,
        "history": [{"date": p.date.isoformat(), "price": p.price} for p in history],
    }


@function_tool
def get_cala_market_signals(material: str, horizon_days: int = 180) -> dict[str, Any]:
    signals = get_cala_signals(material)
    return {
        "signals": [
            {
                "name": s.name,
                "direction": s.direction.value,
                "score": s.score,
                "confidence": s.confidence,
                "horizon_days": s.horizon_days,
                "source": s.source,
                "evidence": s.evidence,
            }
            for s in signals
        ]
    }


@function_tool
def get_source_registry(material: str) -> dict[str, Any]:
    return {
        "material": material,
        "sources": [
            {
                "name": "Cala.ai",
                "type": "structured_market_intelligence",
                "freshness": "daily",
                "reliability": 0.85,
                "used_for": ["prices", "geopolitical_signals", "supply_risk"],
            },
            {
                "name": "Internal price history",
                "type": "historical_dataset",
                "freshness": "weekly",
                "reliability": 0.95,
                "used_for": ["volatility", "analogues", "momentum"],
            },
        ],
    }


# ---------------------------------------------------------------------------
# G. Decision (delegates to existing deterministic recommender)
# ---------------------------------------------------------------------------


@function_tool
def compute_recommendation(
    material: str,
    priority_profile: str = "balanced",
    horizon_days: int = 180,
) -> dict[str, Any]:
    req = RecommendationRequest(
        material=MaterialKey(material),
        priority_profile=PriorityProfileKey(priority_profile),
        horizon_days=horizon_days,
    )
    rec = get_recommendation(req)
    return rec.model_dump(mode="json")


@function_tool
def fallback_full_analysis(
    material: str,
    priority_profile: str = "balanced",
) -> dict[str, Any]:
    """Demo-safety net. Runs deterministic chain end-to-end without LLM planning."""
    return compute_recommendation(material, priority_profile, 180)


# ---------------------------------------------------------------------------
# J. Agent control
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
def list_capabilities() -> dict[str, Any]:
    return {
        "capabilities": [
            "Recommend BUY_NOW / WAIT / HEDGE / MONITOR for raw materials",
            "Explain drivers and counter-drivers with evidence sources",
            "Compare materials by risk and opportunity",
            "Run what-if scenarios (geopolitical / weather / oil / FX shocks)",
            "Generate forecast risk cones with Cala.ai adjustments",
            "Produce an audit trail of every tool call",
        ],
        "materials": [m.value for m in MaterialKey],
        "priority_profiles": [p.value for p in PriorityProfileKey],
    }


# ---------------------------------------------------------------------------
# Tool registry — exported list for SDK Agent construction
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    get_available_materials,
    get_price_history_tool,
    get_cala_market_signals,
    get_source_registry,
    compute_recommendation,
    fallback_full_analysis,
    validate_material,
    validate_priority_profile,
    list_capabilities,
]


# Convenience for non-SDK callers / tests
def call_raw(tool_name: str, **kwargs: Any) -> Any:
    """Invoke a tool by name, bypassing the SDK wrapper."""
    registry = {
        "get_available_materials": get_available_materials,
        "get_price_history": get_price_history_tool,
        "get_cala_market_signals": get_cala_market_signals,
        "get_source_registry": get_source_registry,
        "compute_recommendation": compute_recommendation,
        "fallback_full_analysis": fallback_full_analysis,
        "validate_material": validate_material,
        "validate_priority_profile": validate_priority_profile,
        "list_capabilities": list_capabilities,
    }
    fn = registry[tool_name]
    inner = getattr(fn, "__wrapped__", fn)
    return inner(**kwargs)


__all__ = ["ALL_TOOLS", "call_raw", "CalaClient"]
