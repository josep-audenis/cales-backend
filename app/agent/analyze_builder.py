"""Deterministic builder: AgentRunResult -> AnalyzeResponse."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.schemas.analyze_response import (
    AnalyzeResponse,
    AuditTrail,
    ChangeCondition,
    ContextUsed,
    DataQuality,
    Driver,
    Evidence,
    ForecastBlock,
    GraphPoint,
    Explainability,
    MarketContext,
    PricePath,
    ReasoningStep,
    Recommendation,
    SpotPrice,
    WatchItem,
)
from app.schemas.common import MaterialKey

log = logging.getLogger("app.agent.analyze_builder")


# ---------------------------------------------------------------------------
# Static lookups
# ---------------------------------------------------------------------------

MATERIAL_UNITS: dict[str, str] = {
    "aluminium": "USD/t",
    "barley": "EUR/t",
    "pet": "USD/t",
    "energy": "EUR/MWh",
}

RELIABILITY_BY_DOMAIN: dict[str, str] = {
    "lme.com": "high",
    "fastmarkets.com": "high",
    "reuters.com": "high",
    "bloomberg.com": "high",
    "wsj.com": "high",
    "ft.com": "high",
    "ing.com": "high",
    "stats.gov.cn": "medium",
    "thomasnet.com": "medium",
    "cala.ai": "medium",
    "investing.com": "medium",
    "cnbc.com": "medium",
    "mining.com": "medium",
    "metal.com": "medium",
    "yahoo.com": "medium",
    "oilandgas360.com": "medium",
}

SOURCE_NAME_OVERRIDES: dict[str, str] = {
    "wsj.com": "WSJ",
    "ft.com": "Financial Times",
    "ing.com": "ING Think",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "lme.com": "LME",
    "fastmarkets.com": "Fastmarkets",
    "cnbc.com": "CNBC",
    "investing.com": "Investing.com",
    "mining.com": "Mining.com",
    "metal.com": "Metal.com",
    "oilandgas360.com": "OilAndGas360",
}

SIGNAL_LABELS: dict[str, str] = {
    "price_momentum": "Price momentum",
    "seasonality": "Seasonal pattern",
    "supply_chain": "Supply concentration",
    "geopolitical_risk": "Geopolitical disruption risk",
    "weather": "Weather / crop conditions",
    "inventory_pressure": "Warehouse stock drawdown",
    "energy_cost": "Energy cost pressure",
    "energy_pressure": "Energy cost pressure",
    "freight": "Freight & logistics cost",
    "currency": "Currency / FX exposure",
    "demand": "Demand-side pressure",
    "china_demand": "China industrial demand",
}

SIGNAL_EXPLANATIONS: dict[str, str] = {
    "price_momentum": "Recent price trajectory indicates directional pressure.",
    "seasonality": "Historical seasonality skews the price path in this window.",
    "supply_chain": "Producer concentration affects supply tightness.",
    "geopolitical_risk": "Geopolitical events can disrupt sourcing or logistics.",
    "weather": "Weather conditions affect crop yields and availability.",
    "inventory_pressure": "Lower stock coverage reduces the buffer against shocks.",
    "energy_cost": "Energy is a key input cost driving production economics.",
    "energy_pressure": "Higher energy costs increase smelter and production expenses.",
    "freight": "Shipping and logistics costs affect delivered material prices.",
    "currency": "FX movements alter the effective cost of imported materials.",
    "demand": "Demand-side shifts influence price equilibrium.",
    "china_demand": "China drives ~50% of global metals demand; shifts move prices.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash8(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def _ev_id(url: str) -> str:
    return f"ev_{_hash8(url.strip().lower())}"


def _drv_id(name: str) -> str:
    return f"drv_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}"


def _domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        host = host.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _domain_matches(domain: str, key: str) -> bool:
    """Exact domain match or subdomain match. Avoids 'ing.com' matching 'investing.com'."""
    return domain == key or domain.endswith("." + key)


def _reliability(url: str) -> str:
    d = _domain(url)
    for key, rel in RELIABILITY_BY_DOMAIN.items():
        if _domain_matches(d, key):
            return rel
    return "medium"


def _source_name(url: str) -> str:
    d = _domain(url)
    if not d:
        return "Unknown"
    if d in SOURCE_NAME_OVERRIDES:
        return SOURCE_NAME_OVERRIDES[d]
    for key, name in SOURCE_NAME_OVERRIDES.items():
        if _domain_matches(d, key):
            return name
    parts = d.split(".")
    return parts[-2].capitalize() if len(parts) >= 2 else d


def _pressure_direction(direction: str, score: float) -> str:
    if direction == "bullish":
        return "strong_upward_price_pressure" if score >= 70 else (
            "upward_price_pressure" if score >= 40 else "moderate_upward_price_pressure"
        )
    if direction == "bearish":
        return "strong_downward_price_pressure" if score >= 70 else (
            "downward_price_pressure" if score >= 40 else "moderate_downward_price_pressure"
        )
    return "neutral"


def _buyer_impact(direction: str) -> str:
    if direction == "bullish":
        return "negative"
    if direction == "bearish":
        return "positive"
    return "neutral"


def _impact_bucket(score: float) -> str:
    a = abs(score)
    if a >= 0.30:
        return "high"
    if a >= 0.15:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

_INTERNAL_ORIGIN: dict[str, str] = {
    "price_momentum": "momentum",
    "seasonality": "seasonality",
    "inventory_pressure": "warehouse",
}


def _internal_rationale(signal: dict[str, Any]) -> str:
    name = signal.get("name") or ""
    direction = signal.get("direction") or "neutral"
    score = float(signal.get("score") or 0.0)
    meta = signal.get("meta") or {}

    if name == "price_momentum":
        short_ma = meta.get("short_ma")
        long_ma = meta.get("long_ma")
        if short_ma and long_ma:
            diff_pct = round((short_ma - long_ma) / long_ma * 100, 2)
            trend = "above" if short_ma > long_ma else "below"
            return (
                f"Short-term MA ({short_ma:.0f}) is {trend} long-term MA ({long_ma:.0f}) "
                f"by {abs(diff_pct):.1f}%, indicating {'upward' if direction == 'bullish' else 'downward'} momentum."
            )
        return f"Price momentum signal is {direction} (score {score:.0f}/100) based on moving average crossover."

    if name == "seasonality":
        month = meta.get("month") or ""
        hist_avg = meta.get("historical_avg_pct")
        if hist_avg is not None:
            return (
                f"Historical seasonality for {month or 'this period'}: average price change {hist_avg:+.1f}%. "
                f"Pattern suggests {'upward' if direction == 'bullish' else 'downward'} pressure."
            )
        return f"Seasonal pattern signal is {direction} (score {score:.0f}/100) based on historical price cycles."

    if name == "inventory_pressure":
        fill = meta.get("fill_pct")
        if fill is not None:
            return (
                f"Warehouse fill at {fill:.0f}%. "
                f"{'Low stock increases supply risk and urgency.' if direction == 'bullish' else 'High stock reduces near-term buying urgency.'}"
            )
        return f"Inventory pressure is {direction} (score {score:.0f}/100) based on warehouse stock levels."

    return f"{SIGNAL_LABELS.get(name, name)} signal is {direction} (score {score:.0f}/100)."


def _build_evidence(
    signals: list[dict[str, Any]],
    extra_urls: list[str],
    spot_url: str | None,
    today: date,
    warehouse_fill: float | None = None,
) -> tuple[list[Evidence], dict[str, str]]:
    """Return evidence list + (url|key) -> id map."""
    url_to_id: dict[str, str] = {}
    ev_list: list[Evidence] = []
    seen: set[str] = set()

    if spot_url:
        eid = "ev_lme_spot"
        url_to_id[spot_url] = eid
        ev_list.append(Evidence(
            id=eid,
            source="LME",
            title="LME reference price",
            date=today,
            reliability="high",
            url=spot_url,
            evidence_origin="url",
            evidence_rationale="Official LME spot price used as forecast anchor and base for all price path calculations.",
            signal_extracted="Reference spot price used as forecast anchor.",
            used_for=["market_context.spot_price", "base_case"],
        ))
        seen.add(spot_url)

    def _is_valid_url(url: str) -> bool:
        try:
            from urllib.parse import urlparse as _up
            p = _up(url)
            return p.scheme in ("http", "https") and bool(p.netloc)
        except Exception:
            return False

    def _add_url(url: str, src_signal: str | None) -> None:
        if not url or not _is_valid_url(url) or url in seen:
            return
        eid = _ev_id(url)
        url_to_id[url] = eid
        src_name = _source_name(url)
        from urllib.parse import urlparse as _up
        path_parts = [p for p in _up(url).path.split("/") if p]
        slug = path_parts[-1] if path_parts else ""
        # Strip file extension (.html, .php, etc.)
        slug = re.sub(r"\.[a-z]{2,4}$", "", slug, flags=re.IGNORECASE)
        # Strip trailing numeric or hex IDs (≥6 chars, e.g. -200678325 or -b1e9fdae)
        slug = re.sub(r"[-_][0-9a-f]{6,}$", "", slug, flags=re.IGNORECASE)
        # Strip trailing short dangling word left after ID removal (e.g. "at", "in")
        slug = re.sub(r"[-_]\w{1,3}$", "", slug)
        # Strip leading numeric prefix (e.g. "103909247-Tsingshan...")
        slug = re.sub(r"^\d+[-_]?", "", slug)
        slug_title = slug.replace("-", " ").replace("_", " ").title()[:80] if slug else src_name
        base_explanation = SIGNAL_EXPLANATIONS.get(src_signal or "", "Market intelligence from external source.")
        article_title = slug_title or f"{src_name} article"
        rationale = f"{src_name}: \"{article_title}\" — {base_explanation}"
        ev_list.append(Evidence(
            id=eid,
            source=src_name,
            title=article_title,
            date=today,
            reliability=_reliability(url),
            url=url,
            evidence_origin="url",
            evidence_rationale=rationale,
            signal_extracted=base_explanation,
            used_for=[],
        ))
        seen.add(url)

    def _add_internal(signal: dict[str, Any]) -> str | None:
        name = signal.get("name") or ""
        origin = _INTERNAL_ORIGIN.get(name, "internal")
        eid = f"ev_{name}"
        if eid in seen:
            return eid
        rationale = _internal_rationale(signal)
        label = SIGNAL_LABELS.get(name, name.replace("_", " ").capitalize())
        ev_list.append(Evidence(
            id=eid,
            source="Internal computation",
            title=label,
            date=today,
            reliability="medium",
            url="",
            evidence_origin=origin,  # type: ignore[arg-type]
            evidence_rationale=rationale,
            signal_extracted=rationale,
            used_for=[],
        ))
        seen.add(eid)
        url_to_id[eid] = eid
        return eid

    for s in signals:
        name = s.get("name") or ""
        signal_source = (s.get("source") or "").lower()
        urls = s.get("evidence") or []
        if signal_source == "internal" or not urls:
            _add_internal(s)
        else:
            for url in urls:
                _add_url(url, name)

    # Standalone warehouse evidence (from context, not a signal)
    if warehouse_fill is not None and "ev_warehouse_fill" not in seen:
        direction = "bullish" if (100 - warehouse_fill) >= 50 else "bearish"
        fill_pct = warehouse_fill
        rationale = (
            f"Current warehouse fill is {fill_pct:.0f}%. "
            f"{'Low inventory creates supply risk and increases buying urgency.' if direction == 'bullish' else 'High inventory reduces near-term urgency and provides buffer.'}"
        )
        eid = "ev_warehouse_fill"
        ev_list.append(Evidence(
            id=eid,
            source="Internal computation",
            title="Warehouse fill level",
            date=today,
            reliability="medium",
            url="",
            evidence_origin="warehouse",
            evidence_rationale=rationale,
            signal_extracted=rationale,
            used_for=[],
        ))
        seen.add("ev_warehouse_fill")
        url_to_id["ev_warehouse_fill"] = eid

    for url in extra_urls:
        _add_url(url, None)

    return ev_list, url_to_id


def _build_drivers(signals: list[dict[str, Any]], url_to_id: dict[str, str]) -> list[Driver]:
    drivers: list[Driver] = []
    for s in signals:
        name = s.get("name") or "unknown"
        direction = s.get("direction") or "neutral"
        score = float(s.get("score") or 0.0)
        conf = float(s.get("confidence") or 0.0)
        sign = 1.0 if direction == "bullish" else (-1.0 if direction == "bearish" else 0.0)
        impact_score = round(sign * (score / 100.0) * (conf / 100.0), 3)
        is_internal = (s.get("source") or "").lower() == "internal"
        if is_internal:
            internal_key = f"ev_{name}"
            ev_ids = [internal_key] if internal_key in url_to_id else []
        else:
            ev_ids = [url_to_id[u] for u in (s.get("evidence") or []) if u in url_to_id]
        drivers.append(Driver(
            id=_drv_id(name),
            label=SIGNAL_LABELS.get(name, name.replace("_", " ").capitalize()),
            direction=_pressure_direction(direction, score),
            buyer_impact=_buyer_impact(direction),
            impact=_impact_bucket(impact_score),
            impact_score=impact_score,
            confidence=round(conf / 100.0, 2),
            explanation=SIGNAL_EXPLANATIONS.get(name, f"Signal: {name}"),
            evidence_ids=ev_ids,
        ))
    return drivers


def _build_inventory_driver(warehouse_fill: float | None, url_to_id: dict[str, str]) -> Driver | None:
    if warehouse_fill is None:
        return None
    pressure = 100.0 - float(warehouse_fill)
    direction = "bullish" if pressure >= 50 else "bearish"
    score = abs(pressure - 50) * 2
    impact_score = round((1.0 if direction == "bullish" else -1.0) * (score / 100.0) * 0.7, 3)
    return Driver(
        id="drv_warehouse_drawdown",
        label="Warehouse stock level",
        direction=_pressure_direction(direction, score),
        buyer_impact=_buyer_impact(direction),
        impact=_impact_bucket(impact_score),
        impact_score=impact_score,
        confidence=0.8,
        explanation=f"Current warehouse fill is {warehouse_fill:.0f}%. Lower fill increases urgency; higher fill reduces it.",
        evidence_ids=["ev_warehouse_fill"] if "ev_warehouse_fill" in url_to_id else [],
    )


def _sample_points(forecast_points: list[dict[str, Any]], anchor_price: float, anchor_date: date, target_field: str = "median") -> list[GraphPoint]:
    """Pick anchor + ~3 evenly spaced points along forecast."""
    points: list[GraphPoint] = [GraphPoint(date=anchor_date, value=round(anchor_price, 2))]
    if not forecast_points:
        return points
    n = len(forecast_points)
    idxs = [n // 3, (2 * n) // 3, n - 1] if n >= 3 else [n - 1]
    for i in idxs:
        fp = forecast_points[i]
        points.append(GraphPoint(date=fp["date"], value=round(float(fp[target_field]), 2)))
    return points


def _build_price_paths(
    forecast_points: list[dict[str, Any]],
    anchor_price: float | None,
    anchor_date: date | None,
    summary: dict[str, Any],
    drivers: list[Driver],
    url_to_id: dict[str, str],
) -> list[PricePath]:
    if not forecast_points or anchor_price is None or anchor_date is None:
        return []
    last = forecast_points[-1]
    median_end = float(last["median"])
    upper_end = float(last["upper"])
    lower_end = float(last["lower"])

    base_change = float(summary.get("expected_change_pct", 0.0))
    low_change = float(summary.get("range_low_pct", 0.0))
    high_change = float(summary.get("range_high_pct", 0.0))

    bullish_drivers = [d for d in drivers if d.buyer_impact == "negative"]
    bearish_drivers = [d for d in drivers if d.buyer_impact == "positive"]
    all_ev = list({eid for d in drivers for eid in d.evidence_ids})
    bullish_ev = list({eid for d in bullish_drivers for eid in d.evidence_ids})
    bearish_ev = list({eid for d in bearish_drivers for eid in d.evidence_ids})

    base_path = PricePath(
        id="base_case",
        label="Base case",
        graph_line_key="base",
        buyer_impact="negative" if base_change > 1 else ("positive" if base_change < -1 else "neutral"),
        direction=_pressure_direction(
            "bullish" if base_change > 0 else ("bearish" if base_change < 0 else "neutral"),
            min(abs(base_change) * 5, 100),
        ),
        summary="Current signals continue without a major new shock.",
        expected_change_pct=base_change,
        range_low_pct=low_change,
        range_high_pct=high_change,
        driver_ids=[d.id for d in drivers],
        evidence_ids=all_ev,
        graph_points=_sample_points(forecast_points, anchor_price, anchor_date, "median"),
        explainability=Explainability(
            plain_language="Base path reflects the weighted balance of all current signals.",
            click_title="Why the base path moves this way",
            click_evidence_ids=all_ev[:5],
        ),
    )

    worst_change = round((upper_end - anchor_price) / anchor_price * 100, 2)
    worst_path = PricePath(
        id="worst_case",
        label="Worst case",
        graph_line_key="upside",
        buyer_impact="negative",
        direction="strong_upward_price_pressure",
        summary="Bullish drivers compound: price moves toward the upper band.",
        expected_change_pct=worst_change,
        range_low_pct=base_change,
        range_high_pct=high_change,
        driver_ids=[d.id for d in bullish_drivers] or [d.id for d in drivers],
        evidence_ids=bullish_ev or all_ev,
        graph_points=_sample_points(forecast_points, anchor_price, anchor_date, "upper"),
        explainability=Explainability(
            plain_language="Bad-news path: upside drivers dominate and price climbs faster.",
            click_title="Why the worst-case line is higher",
            click_evidence_ids=(bullish_ev or all_ev)[:5],
        ),
    )

    relief_change = round((lower_end - anchor_price) / anchor_price * 100, 2)
    relief_path = PricePath(
        id="relief_case",
        label="Relief case",
        graph_line_key="downside",
        buyer_impact="positive",
        direction="downward_price_pressure",
        summary="Bearish drivers dominate: price drifts toward the lower band.",
        expected_change_pct=relief_change,
        range_low_pct=low_change,
        range_high_pct=base_change,
        driver_ids=[d.id for d in bearish_drivers] or [d.id for d in drivers],
        evidence_ids=bearish_ev or all_ev,
        graph_points=_sample_points(forecast_points, anchor_price, anchor_date, "lower"),
        explainability=Explainability(
            plain_language="Good-news path: downside drivers reduce buying pressure.",
            click_title="Why the relief-case line is lower",
            click_evidence_ids=(bearish_ev or all_ev)[:5],
        ),
    )

    return [base_path, worst_path, relief_path]


def _link_evidence_back(evidence: list[Evidence], drivers: list[Driver], paths: list[PricePath]) -> None:
    by_id = {e.id: e for e in evidence}
    for d in drivers:
        for eid in d.evidence_ids:
            if eid in by_id and d.id not in by_id[eid].used_for:
                by_id[eid].used_for.append(d.id)
    for p in paths:
        for eid in p.evidence_ids:
            if eid in by_id and p.id not in by_id[eid].used_for:
                by_id[eid].used_for.append(p.id)


def _build_reasoning(drivers: list[Driver], action: str, material: str) -> list[ReasoningStep]:
    # Always include top Cala-evidenced driver + top internal driver (max 3 total)
    cala_drivers = [d for d in drivers if d.evidence_ids]
    internal_drivers = [d for d in drivers if not d.evidence_ids]
    top_cala = sorted(cala_drivers, key=lambda d: abs(d.impact_score), reverse=True)[:2]
    top_internal = sorted(internal_drivers, key=lambda d: abs(d.impact_score), reverse=True)[:1]
    strong = sorted(top_cala + top_internal, key=lambda d: abs(d.impact_score), reverse=True)[:3]
    steps: list[ReasoningStep] = []
    step = 1
    for d in strong:
        steps.append(ReasoningStep(
            step=step,
            type="evidence",
            text=f"{d.label} ({d.direction.replace('_', ' ')}) — {d.explanation}",
            evidence_ids=d.evidence_ids[:3],
        ))
        step += 1
        steps.append(ReasoningStep(
            step=step,
            type="signal",
            text=f"{d.label} contributes impact_score {d.impact_score:+.2f}.",
            driver_ids=[d.id],
        ))
        step += 1
    steps.append(ReasoningStep(
        step=step,
        type="market_mechanism",
        text=f"Combined drivers determine the {material} price corridor over the horizon.",
    ))
    step += 1
    steps.append(ReasoningStep(
        step=step,
        type="decision",
        text=f"Recommendation is {action} based on the balance of upside risk, supply risk, and confidence.",
    ))
    return steps


def _build_change_conditions(drivers: list[Driver], action: str) -> list[ChangeCondition]:
    out: list[ChangeCondition] = []
    strong = sorted(drivers, key=lambda d: abs(d.impact_score), reverse=True)[:3]
    for d in strong:
        if d.buyer_impact == "negative":
            shift = f"{action} to MONITOR" if action in ("BUY_NOW", "HEDGE") else f"{action} to WAIT"
            cond = f"{d.label} weakens or reverses"
            reason = f"Reduces upward pressure from {d.label.lower()}."
        elif d.buyer_impact == "positive":
            shift = f"{action} to BUY_NOW" if action in ("MONITOR", "WAIT") else f"{action} to HEDGE"
            cond = f"{d.label} fades"
            reason = f"Removes the offsetting downward pressure from {d.label.lower()}."
        else:
            continue
        out.append(ChangeCondition(
            condition=cond,
            likely_shift=shift,
            reason=reason,
            evidence_to_watch=d.evidence_ids[:3],
        ))
    return out


def _build_watch(drivers: list[Driver]) -> list[WatchItem]:
    out: list[WatchItem] = []
    strong = sorted(drivers, key=lambda d: abs(d.impact_score), reverse=True)[:3]
    for d in strong:
        out.append(WatchItem(
            item=d.label,
            why=d.explanation,
            evidence_source_ids=d.evidence_ids[:3],
        ))
    return out


def _spot_url_for(material: str) -> str | None:
    return {
        "aluminium": "https://www.lme.com/en/metals/non-ferrous/lme-aluminium",
        "barley": None,
        "pet": None,
        "energy": None,
    }.get(material)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def build_analyze_response(
    *,
    material: str,
    horizon_days: int,
    horizon_label: str,
    analysis_type: str,
    requested_at: datetime | None,
    context_flags: dict[str, Any],
    include_market_drivers: bool,
    decision: dict[str, Any] | None,
    signals: list[dict[str, Any]] | None,
    evidence_urls: list[str] | None,
    forecast_points: list[dict[str, Any]] | None,
    spot_price: float | None,
    spot_date: Any | None,
    tool_calls: list[dict[str, Any]] | None,
    answer_text: str,
) -> AnalyzeResponse:
    decision = decision or {}
    signals = signals or []
    evidence_urls = evidence_urls or []
    tool_calls = tool_calls or []

    today: date
    if isinstance(spot_date, date):
        today = spot_date
    elif isinstance(spot_date, str):
        try:
            today = date.fromisoformat(spot_date[:10])
        except Exception:
            today = datetime.now(timezone.utc).date()
    else:
        today = datetime.now(timezone.utc).date()

    gen_at = requested_at or datetime.now(timezone.utc)

    spot_url = _spot_url_for(material) if context_flags.get("spot_price", True) else None
    warehouse_fill_raw = decision.get("warehouse_fill_pct")
    if not isinstance(warehouse_fill_raw, (int, float)):
        warehouse_fill_raw = context_flags.get("warehouse_fill_pct") if isinstance(context_flags.get("warehouse_fill_pct"), (int, float)) else None
    evidence, url_to_id = _build_evidence(signals, evidence_urls, spot_url, today, warehouse_fill=warehouse_fill_raw)

    drivers = _build_drivers(signals, url_to_id)
    warehouse_fill = warehouse_fill_raw
    inv_driver = _build_inventory_driver(warehouse_fill if isinstance(warehouse_fill, (int, float)) else None, url_to_id)
    if inv_driver:
        drivers.append(inv_driver)

    scores = decision.get("scores") or {}
    summary_forecast = decision.get("forecast_summary") or {}

    price_paths = _build_price_paths(
        forecast_points=forecast_points or [],
        anchor_price=spot_price,
        anchor_date=today,
        summary=summary_forecast,
        drivers=drivers,
        url_to_id=url_to_id,
    )

    _link_evidence_back(evidence, drivers, price_paths)

    action = decision.get("action") or "MONITOR"
    confidence_raw = float(scores.get("confidence") or 0.0)
    confidence = round(confidence_raw / 100.0 if confidence_raw > 1.0 else confidence_raw, 2)
    risk_score = float(scores.get("adjusted_upside_risk") or scores.get("external_risk") or 0.0)
    opportunity_score = float(scores.get("opportunity") or 0.0)

    rec_summary = decision.get("explanation") or answer_text.split("\n")[0][:200]
    rationale_bits = []
    for d in sorted(drivers, key=lambda x: abs(x.impact_score), reverse=True)[:3]:
        rationale_bits.append(f"{d.label} ({d.direction.replace('_', ' ')})")
    decision_rationale = (
        f"Action {action} driven by: " + "; ".join(rationale_bits)
        if rationale_bits
        else f"Action {action} based on available signals."
    )

    recommendation = Recommendation(
        action=action,
        recommended_horizon_days=int(decision.get("horizon_days") or horizon_days),
        confidence=max(0.0, min(1.0, confidence)),
        risk_score=round(risk_score, 1),
        opportunity_score=round(opportunity_score, 1),
        summary=rec_summary,
        decision_rationale=decision_rationale,
        months_to_buy=decision.get("months_to_buy"),
        current_coverage_months=decision.get("current_coverage_months"),
        target_coverage_months=decision.get("target_coverage_months"),
    )

    spot = None
    if spot_url and spot_price is not None and context_flags.get("spot_price", True):
        spot = SpotPrice(
            value=round(float(spot_price), 2),
            unit=MATERIAL_UNITS.get(material, "USD/t"),
            as_of=today,
            source_id="ev_lme_spot",
        )
    elif spot_price is not None and context_flags.get("spot_price", True):
        spot = SpotPrice(
            value=round(float(spot_price), 2),
            unit=MATERIAL_UNITS.get(material, "USD/t"),
            as_of=today,
            source_id="ev_spot",
        )

    market_context = MarketContext(
        current_date=today,
        spot_price=spot,
        warehouse_fill_pct=warehouse_fill if isinstance(warehouse_fill, (int, float)) else None,
        context_used=ContextUsed(
            current_date=bool(context_flags.get("current_date", True)),
            spot_price=bool(context_flags.get("spot_price", True)),
            warehouse_fill_pct=isinstance(warehouse_fill, (int, float)),
            related_news=bool(context_flags.get("related_news", True)),
            source_reliability=bool(context_flags.get("source_reliability", True)),
            market_drivers=bool(include_market_drivers),
        ),
    )

    fc_dir = summary_forecast.get("direction") or "flat"
    forecast_block = ForecastBlock(
        direction=fc_dir if fc_dir in ("upward", "downward", "flat") else "flat",
        expected_change_pct=float(summary_forecast.get("expected_change_pct") or 0.0),
        range_low_pct=float(summary_forecast.get("range_low_pct") or 0.0),
        range_high_pct=float(summary_forecast.get("range_high_pct") or 0.0),
        interpretation=(
            "Forecast corridor asymmetric: upside tail wider than downside."
            if abs(float(summary_forecast.get("range_high_pct") or 0.0)) > abs(float(summary_forecast.get("range_low_pct") or 0.0))
            else "Forecast corridor asymmetric: downside tail wider than upside."
            if abs(float(summary_forecast.get("range_low_pct") or 0.0)) > abs(float(summary_forecast.get("range_high_pct") or 0.0)) * 1.2
            else "Forecast corridor roughly symmetric around base path."
        ),
    )

    reasoning = _build_reasoning(drivers, action, material)
    changes = _build_change_conditions(drivers, action)
    watch = _build_watch(drivers)

    tools_called = sorted({tc.get("tool") for tc in tool_calls if tc.get("tool")})
    audit = AuditTrail(
        tools_called=[t for t in tools_called if t],
        data_quality=DataQuality(
            price_data_available=spot_price is not None,
            warehouse_data_available=isinstance(warehouse_fill, (int, float)),
            external_news_available=bool(evidence_urls),
            source_urls_available=bool(evidence),
        ),
    )

    limitations = [
        "Recommendation is based on signals available at generation time.",
        "Confidence should be reduced if external market-intelligence sources are unavailable.",
        "This is a procurement decision aid, not financial advice.",
    ]

    return AnalyzeResponse(
        schema_version="1.0",
        analysis_type=analysis_type if analysis_type in ("base_case", "stress_test", "what_if") else "base_case",
        material=MaterialKey(material),
        generated_at=gen_at,
        horizon_days=horizon_days,
        horizon_label=horizon_label,
        recommendation=recommendation,
        market_context=market_context,
        forecast=forecast_block,
        reasoning_chain=reasoning,
        drivers=drivers,
        price_paths=price_paths,
        evidence=evidence,
        what_would_change_the_recommendation=changes,
        what_to_monitor=watch,
        limitations=limitations,
        audit_trail=audit,
    )
