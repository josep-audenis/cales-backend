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


def _knowledge_search(q: str, explainability: bool = True) -> dict[str, Any]:
    return _post("/knowledge/search", {"input": q, "explainability": explainability, "return_entities": False})


def _extract_urls(data: dict[str, Any]) -> list[str]:
    """Pull all citable URLs from knowledge_search context[].origins[].document.url."""
    seen: set[str] = set()
    urls: list[str] = []
    for ctx in (data.get("context") or []):
        for origin in (ctx.get("origins") or []):
            doc = origin.get("document") or {}
            url = doc.get("url") if isinstance(doc, dict) else None
            if url and isinstance(url, str) and url.startswith("http") and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def _extract_source_names(data: dict[str, Any]) -> list[str]:
    """Unique publisher names from knowledge_search context origins."""
    seen: set[str] = set()
    names: list[str] = []
    for ctx in (data.get("context") or []):
        for origin in (ctx.get("origins") or []):
            name = (origin.get("source") or {}).get("name")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _score_from_explainability(data: dict[str, Any], bullish_kw: tuple[str, ...], bearish_kw: tuple[str, ...]) -> tuple[str, float]:
    """Score direction from explainability claims. Returns (direction, score)."""
    bull = 0
    bear = 0
    for exp in (data.get("explainability") or []):
        text = (exp.get("content") or "").lower()
        for kw in bullish_kw:
            if kw in text:
                bull += 1
        for kw in bearish_kw:
            if kw in text:
                bear += 1
    if bull > bear:
        return Direction.BULLISH.value, min(60.0 + 5.0 * (bull - bear), 80.0)
    if bear > bull:
        return Direction.BEARISH.value, min(60.0 + 5.0 * (bear - bull), 80.0)
    return Direction.NEUTRAL.value, 45.0


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


def _cala_producer_graph_impl(material: str) -> dict[str, Any]:
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
        name="supply_chain",
        direction=direction,
        score=score,
        confidence=60.0,
        horizon_days=180,
        evidence=deduped_evidence,
        extra={"producer_count": n, "top": [p["name"] for p in producers[:5]]},
    )
    return {"signal": sig}


@function_tool
def cala_producer_graph(material: str) -> dict[str, Any]:
    """Pull producers via Product.MANUFACTURED_BY. Returns concentration signal + evidence URLs."""
    return _cala_producer_graph_impl(material)


# ---------------------------------------------------------------------------
# B. Disruption / chokepoint
# ---------------------------------------------------------------------------


_DISRUPTION_BULLISH = ("disruption", "shortage", "sanction", "conflict", "war", "strike", "curtailment", "halt", "outage", "tariff")
_DISRUPTION_BEARISH = ("recovery", "easing", "surplus", "ample supply", "oversupply")


def _cala_disruption_scan_impl(material: str, year: int = 2026) -> dict[str, Any]:
    name = MATERIAL_QUERY_NAME.get(material, material)
    evidence_urls: list[str] = []
    direction = Direction.NEUTRAL.value
    score = 40.0

    for q in [
        f"{name} supply disruption geopolitical risk {year}",
        f"{name} supply chain shortage sanctions {year}",
    ]:
        try:
            data = _knowledge_search(q)
        except Exception:
            log.exception("disruption_scan query failed: %s", q)
            continue
        for url in _extract_urls(data):
            if url not in evidence_urls:
                evidence_urls.append(url)
        d, s = _score_from_explainability(data, _DISRUPTION_BULLISH, _DISRUPTION_BEARISH)
        if s > score:
            direction, score = d, s

    evidence_urls = evidence_urls[:6]
    sig = _signal(
        name="geopolitical_risk",
        direction=direction,
        score=score,
        confidence=55.0 if evidence_urls else 30.0,
        horizon_days=120,
        evidence=evidence_urls,
    )
    return {"signal": sig}


@function_tool
def cala_disruption_scan(material: str, year: int = 2026) -> dict[str, Any]:
    """Knowledge_query for supply disruptions + chokepoint contagion. Bullish if material flagged."""
    return _cala_disruption_scan_impl(material, year)


# ---------------------------------------------------------------------------
# C. Weather (agri only)
# ---------------------------------------------------------------------------


_WEATHER_BULLISH = ("drought", "frost", "flood", "disease", "crop failure", "poor harvest", "heat stress")
_WEATHER_BEARISH = ("ample rain", "recovery", "favorable", "strong yield", "bumper crop", "good harvest")


def _cala_weather_signal_impl(material: str, region: str = "Europe", year: int = 2025) -> dict[str, Any]:
    if material not in {"barley", "wheat"}:
        return {"signal": None, "note": f"weather_signal not applicable to {material}"}

    try:
        data = _knowledge_search(f"{material} harvest weather conditions {region} {year}")
    except Exception as e:
        log.exception("weather_signal failed")
        return {"error": str(e)}

    evidence_urls = _extract_urls(data)[:5]
    direction, score = _score_from_explainability(data, _WEATHER_BULLISH, _WEATHER_BEARISH)
    sig = _signal(
        name="weather",
        direction=direction,
        score=score,
        confidence=50.0 if evidence_urls else 35.0,
        horizon_days=90,
        evidence=evidence_urls,
        extra={"region": region, "year": year},
    )
    return {"signal": sig}


@function_tool
def cala_weather_signal(material: str, region: str = "Europe", year: int = 2025) -> dict[str, Any]:
    """Crop weather events. Agri-only (barley, wheat). Drought/frost/flood → bullish price."""
    return _cala_weather_signal_impl(material, region, year)


# ---------------------------------------------------------------------------
# D. Dynamic Registry Signals
# ---------------------------------------------------------------------------

def _cala_dynamic_signals_impl(material: str, region: str = "Europe", year: int = 2026) -> dict[str, Any]:
    from app.features.driver_registry import get_material_drivers

    drivers = get_material_drivers(material)
    signals = []

    for d_key, d_conf in drivers.items():
        q = d_conf["query_template"].format(region=region, year=year)
        try:
            data = _knowledge_search(q)
        except Exception:
            log.exception("dynamic signal failed for %s", d_key)
            continue

        evidence_urls = _extract_urls(data)[:5]
        bullish_kw = tuple(d_conf.get("bullish_keywords") or ())
        bearish_kw = tuple(d_conf.get("bearish_keywords") or ())
        direction, score = _score_from_explainability(data, bullish_kw, bearish_kw)

        sig = _signal(
            name=d_conf["weight_key"],
            direction=direction,
            score=score,
            confidence=50.0 if evidence_urls else 35.0,
            horizon_days=d_conf.get("horizon_days", 90),
            evidence=evidence_urls,
            extra={"region": region, "year": year, "driver_key": d_key},
        )
        signals.append(sig)
        
    return {"signals": signals}


@function_tool
def cala_dynamic_signals(material: str, region: str = "Europe", year: int = 2026) -> dict[str, Any]:
    """Pull all dynamic signals for the material defined in the driver registry."""
    return _cala_dynamic_signals_impl(material, region, year)


def gather_cala_signals(material: str, region: str = "Europe", year: int = 2026) -> dict[str, Any]:
    """Deterministic synchronous gather of all Cala signals + evidence URLs. No LLM."""
    signals: list[dict[str, Any]] = []
    evidence_urls: list[str] = []

    prod = _cala_producer_graph_impl(material)
    if prod and prod.get("signal"):
        signals.append(prod["signal"])
        evidence_urls.extend(prod["signal"].get("evidence") or [])

    disr = _cala_disruption_scan_impl(material, year=year)
    if disr and disr.get("signal"):
        signals.append(disr["signal"])

    if material in {"barley", "wheat"}:
        wx = _cala_weather_signal_impl(material, region=region, year=year - 1)
        if wx and wx.get("signal"):
            signals.append(wx["signal"])

    dyn = _cala_dynamic_signals_impl(material, region=region, year=year)
    for s in dyn.get("signals") or []:
        signals.append(s)

    # dedupe URLs
    seen: set[str] = set()
    deduped: list[str] = []
    for u in evidence_urls:
        if u and u not in seen:
            seen.add(u)
            deduped.append(u)

    return {"signals": signals, "evidence_urls": deduped}


CALA_TOOLS = [cala_producer_graph, cala_disruption_scan, cala_weather_signal, cala_dynamic_signals]

__all__ = ["CALA_TOOLS", "MATERIAL_UUIDS", "MATERIAL_QUERY_NAME"]
