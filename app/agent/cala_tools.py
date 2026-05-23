"""
Wrapped Cala tools — REST-backed.

Replaces raw MCP knowledge_search for the three signals that feed `decide_action`:
  - cala_producer_graph: supply concentration (MANUFACTURED_BY relationships)
  - cala_disruption_scan: chokepoint/event mapping (knowledge_query)
  - cala_weather_signal: crop weather signal (knowledge_query; barley/wheat only)

Each tool returns a `Signal`-shaped dict with `evidence` URLs sourced directly
from Cala's `properties.sources[*].document` — so the explainability layer can
cite without a second round-trip.

Raw MCP `knowledge_search` stays available in the agent runtime for open-ended
narrative — these wrapped tools are only for the deterministic prediction path.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.common import Direction

try:
    from agents import function_tool  # type: ignore
except Exception:  # pragma: no cover

    def function_tool(*args, **kwargs):  # type: ignore
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def _wrap(fn):
            return fn

        return _wrap


log = logging.getLogger("app.agent.cala")


# ---------------------------------------------------------------------------
# UUID cache — skip entity_search round-trips. Verified 2026-05-23.
# ---------------------------------------------------------------------------

MATERIAL_UUIDS: dict[str, dict[str, str]] = {
    "aluminium": {"product": "2c446fc9-2426-4f08-89bb-8e0fe9c279d5"},
    "barley": {
        "product": "b7d8cc09-893d-43fc-8afe-38dce97cb676",
        "plant": "4cbebdb2-3b48-4bb2-8ab9-ea09f77c7d4d",
    },
    "pet": {  # PET sparse — use PTA feedstock as proxy
        "product": "b874688d-4489-48e3-ba68-3def390bd8ec",
    },
    "energy": {  # natural gas Commodity
        "commodity": "17e8b7c6-1db2-5ee2-bb04-16550cebe8d9",
    },
}

# Material → display name used in free-text queries
MATERIAL_QUERY_NAME: dict[str, str] = {
    "aluminium": "aluminium",
    "barley": "barley",
    "pet": "PET resin",
    "energy": "natural gas",
}


# ---------------------------------------------------------------------------
# REST helper
# ---------------------------------------------------------------------------

_BASE = "https://api.cala.ai/v1"


def _headers() -> dict[str, str]:
    return {"X-API-KEY": settings.cala_api_key, "Content-Type": "application/json"}


def _post(path: str, body: dict[str, Any], timeout: float = 90.0) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout) as c:
                r = c.post(f"{_BASE}{path}", headers=_headers(), json=body)
                r.raise_for_status()
                return r.json()
        except httpx.ReadTimeout as e:
            last_exc = e
            log.warning("Cala POST %s timeout (attempt %d/2)", path, attempt + 1)
            continue
    raise last_exc if last_exc else RuntimeError("Cala POST failed")


def _retrieve_entity(uuid: str, properties: list[str], relationships: dict[str, Any]) -> dict[str, Any]:
    return _post(
        f"/entities/{uuid}",
        {"properties": properties, "relationships": relationships},
    )


def _knowledge_query(q: str) -> dict[str, Any]:
    return _post("/knowledge/query", {"input": q, "return_entities": False})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Signal builders
# ---------------------------------------------------------------------------


def _signal(
    name: str,
    direction: str,
    score: float,
    confidence: float,
    horizon_days: int,
    evidence: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": name,
        "direction": direction,
        "score": max(0.0, min(100.0, score)),
        "confidence": max(0.0, min(100.0, confidence)),
        "horizon_days": horizon_days,
        "source": "cala",
        "evidence": evidence,
        "observed_at": _now_iso(),
    }
    if extra:
        out["meta"] = extra
    return out


# ---------------------------------------------------------------------------
# A. Producer concentration
# ---------------------------------------------------------------------------


@function_tool
def cala_producer_graph(material: str) -> dict[str, Any]:
    """Pull producers via Product.MANUFACTURED_BY. Returns concentration signal + evidence URLs."""
    cache = MATERIAL_UUIDS.get(material)
    if not cache or "product" not in cache:
        return {"error": f"no product UUID cached for {material}"}

    try:
        data = _retrieve_entity(
            cache["product"],
            properties=["name", "category"],
            relationships={"outgoing": {"MANUFACTURED_BY": {"limit": 10}}},
        )
    except Exception as e:
        log.exception("producer_graph failed for %s", material)
        return {"error": str(e)}

    rels = (data.get("relationships") or {}).get("outgoing", {}).get("MANUFACTURED_BY", [])
    producers: list[dict[str, Any]] = []
    evidence: list[str] = []
    for r in rels:
        srcs = (r.get("properties") or {}).get("sources") or []
        url = srcs[0].get("document") if srcs else None
        producers.append({"name": r.get("name"), "entity_type": r.get("entity_type"), "source_url": url})
        if url:
            evidence.append(url)

    n = len(producers)
    # crude concentration heuristic: ≤3 producers => bullish (supply-concentrated)
    if n == 0:
        return {"signal": None, "producers": [], "note": "no producers returned"}
    if n <= 3:
        direction, score = Direction.BULLISH.value, 70.0
    elif n <= 6:
        direction, score = Direction.NEUTRAL.value, 50.0
    else:
        direction, score = Direction.BEARISH.value, 35.0

    # dedupe + cap evidence
    seen: set[str] = set()
    deduped_evidence: list[str] = []
    for u in evidence:
        if u and u not in seen:
            seen.add(u)
            deduped_evidence.append(u)
        if len(deduped_evidence) >= 5:
            break

    sig = _signal(
        name="cala_producer_concentration",
        direction=direction,
        score=score,
        confidence=60.0,
        horizon_days=180,
        evidence=deduped_evidence,
        extra={"producer_count": n, "top": [p["name"] for p in producers[:5]]},
    )
    return {"signal": sig}


# ---------------------------------------------------------------------------
# B. Disruption / chokepoint
# ---------------------------------------------------------------------------


@function_tool
def cala_disruption_scan(material: str, year: int = 2026) -> dict[str, Any]:
    """Knowledge_query for supply disruptions + chokepoint contagion. Bullish if material flagged."""
    name = MATERIAL_QUERY_NAME.get(material, material)
    queries = [
        f"{name} supply disruption {year}",
        f"Strait of Hormuz disruption affected commodities",
    ]
    hits: list[dict[str, Any]] = []
    for q in queries:
        try:
            data = _knowledge_query(q)
        except Exception:
            log.exception("disruption_scan query failed: %s", q)
            continue
        for row in data.get("results", []) or []:
            if isinstance(row, dict) and not row.get("error"):
                hits.append({"query": q, **row})

    # Heuristic: any hit mentioning material → bullish
    name_l = name.lower()
    relevant = [h for h in hits if name_l in str(h).lower()]
    if relevant:
        sig = _signal(
            name="cala_supply_disruption",
            direction=Direction.BULLISH.value,
            score=72.0,
            confidence=55.0,
            horizon_days=120,
            evidence=[],  # narrative-only — no per-row URLs in knowledge_query
            extra={"hit_count": len(relevant)},
        )
    else:
        sig = _signal(
            name="cala_supply_disruption",
            direction=Direction.NEUTRAL.value,
            score=40.0,
            confidence=30.0,
            horizon_days=120,
            evidence=[],
            extra={"hit_count": 0},
        )
    return {"signal": sig}


# ---------------------------------------------------------------------------
# C. Weather (agri only)
# ---------------------------------------------------------------------------


@function_tool
def cala_weather_signal(material: str, region: str = "Europe", year: int = 2025) -> dict[str, Any]:
    """Crop weather events. Agri-only (barley, wheat). Drought/frost/flood → bullish price."""
    if material not in {"barley", "wheat"}:
        return {"signal": None, "note": f"weather_signal not applicable to {material}"}

    q = f"weather events affecting {material} harvest {region} {year}"
    try:
        data = _knowledge_query(q)
    except Exception as e:
        log.exception("weather_signal failed")
        return {"error": str(e)}

    rows = [r for r in (data.get("results") or []) if isinstance(r, dict) and not r.get("error")]
    bullish_kw = ("drought", "frost", "flood", "disease", "whiplash")
    bearish_kw = ("ample rain", "recovery", "favorable", "strong yield")
    bull_hits = sum(1 for r in rows for kw in bullish_kw if kw in str(r).lower())
    bear_hits = sum(1 for r in rows for kw in bearish_kw if kw in str(r).lower())

    if bull_hits > bear_hits:
        direction = Direction.BULLISH.value
        score = 60.0 + min(20.0, 5.0 * (bull_hits - bear_hits))
    elif bear_hits > bull_hits:
        direction = Direction.BEARISH.value
        score = 60.0 + min(20.0, 5.0 * (bear_hits - bull_hits))
    else:
        direction, score = Direction.NEUTRAL.value, 45.0

    sig = _signal(
        name="cala_weather",
        direction=direction,
        score=score,
        confidence=50.0,
        horizon_days=90,
        evidence=[],
        extra={"region": region, "year": year},
    )
    return {"signal": sig}


CALA_TOOLS = [cala_producer_graph, cala_disruption_scan, cala_weather_signal]

__all__ = ["CALA_TOOLS", "MATERIAL_UUIDS", "MATERIAL_QUERY_NAME"]
