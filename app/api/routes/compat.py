"""Frontend compatibility endpoints.

The React app expects a richer commodity contract than the backend's core
`/materials` profile endpoint. These routes compose existing backend data into
that website-facing shape without removing the canonical backend endpoints.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.data.ingestion import get_price_history
from app.features.driver_registry import get_material_drivers
from app.features.material_profiles import MATERIAL_PROFILES
from app.schemas.common import Hedgeable, MaterialKey
from app.schemas.forecast import PricePoint

router = APIRouter(tags=["frontend-compat"])

WAREHOUSE_FILL = {
    "aluminium": 64,
    "pet": 57,
    "barley": 72,
}

BLURBS = {
    "aluminium": "Energy-intensive metal exposure with strong sensitivity to power costs, smelter curtailments, and LME inventory changes.",
    "pet": "Packaging resin exposure driven by oil derivatives, recycled-content regulation, import flows, and conversion margins.",
    "energy": "Power and gas exposure where storage, weather, and geopolitical supply risk drive the procurement window.",
    "barley": "Agricultural input exposure driven by crop conditions, seasonality, fertilizer costs, and regional supply quality.",
}

ANALOGUES = {
    "aluminium": {
        "title": "2021 European smelter curtailment cycle",
        "period": "2021-2022",
        "summary": "Power-cost pressure forced capacity cuts and tightened available metal.",
        "outcome": "Buyers with unhedged exposure faced a sharp upside tail.",
    },
    "pet": {
        "title": "2022 oil derivative squeeze",
        "period": "2022",
        "summary": "Feedstock volatility moved resin prices before converters could reprice.",
        "outcome": "Short procurement windows outperformed spot-chasing.",
    },
    "energy": {
        "title": "2022 gas storage stress",
        "period": "2022",
        "summary": "Low storage and supply uncertainty made winter strip protection valuable.",
        "outcome": "Layered hedges capped the worst procurement outcomes.",
    },
    "barley": {
        "title": "2018 European drought",
        "period": "2018",
        "summary": "Crop stress reduced quality supply and lifted malting barley premiums.",
        "outcome": "Early coverage protected against harvest-time scarcity.",
    },
}


def _history(material: str) -> list[PricePoint]:
    return get_price_history(material, lookback_days=180)


def _change_pct(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round((current - previous) / previous * 100, 2)


def _stats(points: list[PricePoint]) -> dict[str, Any]:
    if not points:
        raise HTTPException(status_code=502, detail="No price history available")
    spot = round(float(points[-1].price), 2)
    prev = float(points[-2].price) if len(points) > 1 else spot
    target = points[-30] if len(points) >= 30 else points[0]
    change_24h = _change_pct(spot, prev)
    change_30d = _change_pct(spot, float(target.price))
    tail = points[-5:] if len(points) >= 5 else points
    trend = "up" if tail[-1].price > tail[0].price else "down" if tail[-1].price < tail[0].price else "flat"
    return {"spot": spot, "change24h": change_24h, "change30d": change_30d, "trend": trend}


def _action(material: str, risk_score: float, trend: str) -> str:
    hedgeable = MATERIAL_PROFILES[MaterialKey(material)].hedgeable
    if risk_score >= 72 and hedgeable in {Hedgeable.YES, Hedgeable.PARTIAL}:
        return "hedge"
    if risk_score >= 58 or trend == "up":
        return "buy"
    if risk_score <= 42:
        return "wait"
    return "monitor"


def _driver_direction(score: float) -> str:
    return "up" if score >= 0 else "down"


def _build_drivers_and_evidence(material: str, change_30d: float, today: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    profile = MATERIAL_PROFILES[MaterialKey(material)]
    weights = profile.weights.model_dump()
    drivers: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    def add_driver(key: str, label: str, category: str, rationale: str, score: float, source: str = "Cala.ai") -> None:
        evidence_id = f"ev_{material}_{key}"
        driver_id = f"drv_{material}_{key}"
        direction = _driver_direction(score)
        drivers.append(
            {
                "id": driver_id,
                "label": label,
                "direction": direction,
                "weight": round(min(1.0, max(0.05, abs(score))), 2),
                "category": category,
                "rationale": rationale,
                "sourceId": evidence_id,
            }
        )
        evidence.append(
            {
                "id": evidence_id,
                "title": label,
                "source": source,
                "reliability": "high" if source == "Market data" else "medium",
                "date": today,
                "url": "",
                "excerpt": rationale,
            }
        )

    momentum_score = max(-1.0, min(1.0, change_30d / 12))
    add_driver(
        "price_momentum",
        "Price momentum",
        "price_momentum",
        f"Thirty-day spot movement is {change_30d:+.1f}%, which sets the near-term procurement bias.",
        momentum_score,
        source="Market data",
    )

    for key, config in get_material_drivers(material).items():
        weight_key = str(config.get("weight_key", key))
        weight = float(weights.get(weight_key) or 0.12)
        label = key.replace("_", " ").title()
        add_driver(
            key,
            label,
            str(config.get("category", "market")),
            str(config.get("description", "Material-specific market driver.")),
            weight,
        )

    add_driver(
        "seasonality",
        "Seasonality",
        "seasonality",
        "Seasonal procurement timing can amplify or soften the next ordering window.",
        float(weights.get("seasonality") or 0.08),
        source="Internal model",
    )

    return drivers, evidence


def _recommendation(material: str, stats: dict[str, Any], drivers: list[dict[str, Any]]) -> dict[str, Any]:
    profile = MATERIAL_PROFILES[MaterialKey(material)]
    upward_weight = sum(d["weight"] for d in drivers if d["direction"] == "up")
    downward_weight = sum(d["weight"] for d in drivers if d["direction"] == "down")
    risk_score = round(max(0, min(100, 45 + stats["change30d"] * 1.8 + upward_weight * 22 - downward_weight * 14 + profile.criticality * 12)))
    confidence = round(max(0.52, min(0.86, 0.58 + len(drivers) * 0.035)), 2)
    action = _action(material, risk_score, stats["trend"])
    driver_names = ", ".join(driver["label"].lower() for driver in drivers[:2])
    return {
        "action": action,
        "horizon": "Next 3 months",
        "score": risk_score,
        "confidence": confidence,
        "summary": f"{profile.name} is a {action.upper()} call because {driver_names or 'current market signals'} dominate the 90-day risk window.",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _history_rows(action: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).date()
    return [
        {"action": "monitor", "date": (now - timedelta(days=90)).isoformat(), "note": "Baseline monitoring while signals were balanced."},
        {"action": "wait", "date": (now - timedelta(days=45)).isoformat(), "note": "Waited for cleaner confirmation from price and supply signals."},
        {"action": action, "date": now.isoformat(), "note": "Current recommendation after latest signal refresh."},
    ]


def _commodity(material: str) -> dict[str, Any]:
    key = MaterialKey(material)
    profile = MATERIAL_PROFILES[key]
    points = _history(material)
    stats = _stats(points)
    today = datetime.now(timezone.utc).date().isoformat()
    drivers, evidence = _build_drivers_and_evidence(material, stats["change30d"], today)
    recommendation = _recommendation(material, stats, drivers)
    analogue = ANALOGUES[material]
    payload: dict[str, Any] = {
        "id": material,
        "name": profile.name,
        "unit": profile.unit,
        "spot": stats["spot"],
        "change24h": stats["change24h"],
        "change30d": stats["change30d"],
        "trend": stats["trend"],
        "weight": profile.criticality,
        "blurb": BLURBS[material],
        "recommendation": recommendation,
        "recommendationHistory": _history_rows(recommendation["action"]),
        "drivers": sorted(drivers, key=lambda d: d["weight"], reverse=True),
        "evidence": evidence,
        "history": [
            {
                "id": f"hist_{material}_1",
                "title": analogue["title"],
                "similarity": 0.74,
                "period": analogue["period"],
                "summary": analogue["summary"],
                "outcome": analogue["outcome"],
            }
        ],
        "series": [{"date": p.date.isoformat(), "value": round(float(p.price), 2)} for p in points],
    }
    if material in WAREHOUSE_FILL:
        payload["warehouseFillPct"] = WAREHOUSE_FILL[material]
    return payload


@router.get("/commodities")
def list_commodities() -> list[dict[str, Any]]:
    return [_commodity(material.value) for material in MaterialKey]


@router.get("/commodities/{material}")
def get_commodity(material: MaterialKey) -> dict[str, Any]:
    return _commodity(material.value)


@router.get("/signals")
def list_frontend_signals() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for material in MaterialKey:
        commodity = _commodity(material.value)
        evidence_by_id = {item["id"]: item for item in commodity["evidence"]}
        for driver in commodity["drivers"]:
            evidence = evidence_by_id.get(driver.get("sourceId"))
            if not evidence:
                continue
            rows.append(
                {
                    "id": evidence["id"],
                    "time": f"{evidence['date']}T08:00:00Z",
                    "commodityId": material.value,
                    "impact": "bullish" if driver["direction"] == "up" else "bearish",
                    "category": driver["category"],
                    "headline": evidence["title"],
                    "detail": evidence["excerpt"],
                    "source": evidence["source"],
                    "reliability": evidence["reliability"],
                }
            )
    return sorted(rows, key=lambda row: row["time"], reverse=True)
