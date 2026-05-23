"""
Multi-agent orchestrator.

Star topology under an Orchestrator that hands off to 5 specialized subagents:

    Orchestrator (user-facing)
     ├─ FundamentalsAgent  → price-derived signals
     ├─ CalaSignalAgent    → producer / disruption / weather signals
     ├─ ForecastAgent      → corridor (consumes upstream signals)
     ├─ DecisionAgent      → action + scores (consumes forecast + signals)
     └─ ExplanationAgent   → user-facing narrative + citations

Fundamentals + CalaSignal run in parallel via asyncio.gather. Forecast →
Decision → Explanation are serial because each consumes the previous output.

Subagent I/O is JSON-only (see prompts) so the orchestrator can parse without
LLM-mediated handoffs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from app.agent.cala_tools import CALA_TOOLS, gather_cala_signals
from app.signals.price_momentum_signal import get_price_momentum_signal
from app.signals.seasonality_signal import get_seasonality_signal
from app.agent.prompts import (
    CALA_SIGNAL_AGENT_SYSTEM,
    EXPLANATION_AGENT_SYSTEM,
    FUNDAMENTALS_AGENT_SYSTEM,
)
from app.agent.tools import (
    FUNDAMENTALS_TOOLS,
    _run_recommendation,
)
from app.core.config import settings
from app.data.ingestion import get_price_history
from app.agent.guardrails import confidence_guardrail, missing_data_guardrail
from app.decision.explanation import build_drivers, build_explanation, enrich_driver_context
from app.decision.scoring import decide_action
from app.features.material_profiles import get_profile
from app.features.priority_profiles import get_priority_profile
from app.forecasting.fallback_model import build_forecast
from app.schemas.common import Action, MaterialKey, PriorityProfileKey
from app.schemas.signal import Signal

log = logging.getLogger("app.agent.orchestrator")


try:
    from agents import Agent, Runner, set_tracing_disabled  # type: ignore
    from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter  # type: ignore
    from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel  # type: ignore
    from openai import AsyncOpenAI  # type: ignore

    set_tracing_disabled(True)
    _SDK_AVAILABLE = True
except Exception as e:  # pragma: no cover
    log.warning("openai-agents SDK unavailable: %s", e)
    _SDK_AVAILABLE = False


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorResult:
    answer: str
    tool_calls: list[dict[str, Any]]
    decision: dict[str, Any] | None
    signals: list[dict[str, Any]]
    evidence_urls: list[str]
    timings: dict[str, float]
    raw: dict[str, Any] | None = None
    forecast_points: list[dict[str, Any]] | None = None
    spot_price: float | None = None
    spot_date: Any | None = None


# ---------------------------------------------------------------------------
# Model + subagent factories
# ---------------------------------------------------------------------------


def _make_model() -> Any:
    if settings.llm_provider == "hf":
        from app.clients.hf_tgi_client import make_tgi_async_openai

        client = make_tgi_async_openai(api_key=settings.hf_token, base_url=settings.hf_space_base_url)
        return OpenAIChatCompletionsModel(model=settings.hf_model, openai_client=client)
    client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return OpenAIChatCompletionsModel(model=settings.agent_model, openai_client=client)


def _make_fundamentals_agent() -> Any:
    return Agent(
        name="FundamentalsAgent",
        instructions=FUNDAMENTALS_AGENT_SYSTEM,
        model=_make_model(),
        tools=FUNDAMENTALS_TOOLS,
    )


def _make_cala_signal_agent() -> Any:
    return Agent(
        name="CalaSignalAgent",
        instructions=CALA_SIGNAL_AGENT_SYSTEM,
        model=_make_model(),
        tools=CALA_TOOLS,
    )


def _make_explanation_agent(mcp_servers: list[Any]) -> Any:
    return Agent(
        name="ExplanationAgent",
        instructions=EXPLANATION_AGENT_SYSTEM,
        model=_make_model(),
        tools=[],
        mcp_servers=mcp_servers,
    )


# ---------------------------------------------------------------------------
# JSON extraction (subagents are prompted to emit JSON-only)
# ---------------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    # Strip ```json fences
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        return json.loads(text)
    except Exception:
        m = _JSON_BLOCK.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    log.warning("subagent did not return parseable JSON: %r", text[:200])
    return {}


def _collect_tool_calls(result: Any, agent_name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in getattr(result, "new_items", []) or []:
        cls_name = type(item).__name__
        if cls_name == "ToolCallItem":
            raw = getattr(item, "raw_item", None)
            out.append(
                {
                    "agent": agent_name,
                    "tool": getattr(raw, "name", None),
                    "args": getattr(raw, "arguments", None),
                }
            )
        elif cls_name == "ToolCallOutputItem":
            if out:
                out[-1]["output_preview"] = str(getattr(item, "output", ""))[:300]
    return out


# ---------------------------------------------------------------------------
# Per-subagent runners
# ---------------------------------------------------------------------------


async def _run_subagent(agent: Any, prompt: str, ctx: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], float]:
    t0 = time.perf_counter()
    log.info("%s | start | prompt_len=%d", agent.name, len(prompt))
    try:
        result = await Runner.run(agent, input=prompt, context=ctx, max_turns=25)
    except Exception as exc:
        log.error("%s | Runner.run failed after %.1fs | %s: %s", agent.name, time.perf_counter() - t0, type(exc).__name__, exc)
        # Log per-turn tool calls if result partially built (MaxTurnsExceeded attaches result)
        partial = getattr(exc, "run", None) or getattr(exc, "result", None)
        if partial is not None:
            for i, item in enumerate(getattr(partial, "new_items", []) or []):
                cls = type(item).__name__
                if cls == "ToolCallItem":
                    raw = getattr(item, "raw_item", None)
                    log.error("  item[%d] TOOL_CALL tool=%s args=%s", i, getattr(raw, "name", "?"), str(getattr(raw, "arguments", "?"))[:200])
                elif cls == "ToolCallOutputItem":
                    log.error("  item[%d] TOOL_OUTPUT output=%s", i, str(getattr(item, "output", ""))[:200])
                elif cls == "MessageOutputItem":
                    log.error("  item[%d] MESSAGE content=%s", i, str(getattr(item, "raw_item", ""))[:200])
        raise
    dt = time.perf_counter() - t0
    # Log every tool call in order so we can see if model loops.
    for i, item in enumerate(getattr(result, "new_items", []) or []):
        cls = type(item).__name__
        if cls == "ToolCallItem":
            raw = getattr(item, "raw_item", None)
            log.info("%s | TOOL_CALL: %s", agent.name, getattr(raw, "name", "?"))
        elif cls == "ToolCallOutputItem":
            log.debug("%s | item[%d] TOOL_OUTPUT preview=%s", agent.name, i, str(getattr(item, "output", ""))[:150])
        elif cls == "MessageOutputItem":
            log.debug("%s | item[%d] MESSAGE content=%s", agent.name, i, str(getattr(item, "raw_item", ""))[:150])
    log.info("%s | done | dt=%.2fs final_output=%s", agent.name, dt, str(result.final_output)[:300])
    text = str(result.final_output)
    parsed = _parse_json(text)
    if not parsed:
        parsed = {"_raw": text}
    return parsed, _collect_tool_calls(result, agent.name), dt


# ---------------------------------------------------------------------------
# Orchestrator entry point
# ---------------------------------------------------------------------------


async def run_orchestrator(message: str, ctx: dict[str, Any]) -> OrchestratorResult:
    """Run the 5-agent crew. Returns final card + audit trail."""
    material = ctx.get("material", "barley")
    priority = ctx.get("priority_profile", "balanced")
    horizon = int(ctx.get("horizon_days", 180))
    horizon_label = ctx.get("horizon_label") or f"{horizon}d"
    analysis_type = ctx.get("analysis_type", "base_case")
    ctx_flags = ctx.get("context") or {}
    warehouse_fill = ctx_flags.get("warehouse_fill_pct") if isinstance(ctx_flags, dict) else None

    timings: dict[str, float] = {}
    tool_calls: list[dict[str, Any]] = []

    # ----- Phase 1: Fundamentals + CalaSignal deterministic (no LLM) -----
    log.info("phase1 start | deterministic fundamentals + cala_signal")
    t1 = time.perf_counter()

    def _run_fundamentals() -> dict[str, Any]:
        signals: list[dict[str, Any]] = []
        try:
            history = get_price_history(material, lookback_days=365)
            prices = [p.price for p in history]
            mom = get_price_momentum_signal(prices).model_dump(mode="json")
            if mom:
                signals.append(mom)
        except Exception:
            log.exception("fundamentals momentum failed")
        try:
            seas = get_seasonality_signal(material).model_dump(mode="json")
            if seas:
                signals.append(seas)
        except Exception:
            log.exception("fundamentals seasonality failed")
        return {"signals": signals}

    def _run_cala() -> dict[str, Any]:
        try:
            return gather_cala_signals(material, region="Europe", year=2026)
        except Exception:
            log.exception("cala signals gather failed")
            return {"signals": [], "evidence_urls": []}

    fund_out = await asyncio.to_thread(_run_fundamentals)
    cala_out = await asyncio.to_thread(_run_cala)
    fund_dt = cala_dt = time.perf_counter() - t1
    timings["phase1_parallel"] = time.perf_counter() - t1
    timings["fundamentals"] = fund_dt
    timings["cala_signal"] = cala_dt
    tool_calls.append({"agent": "FundamentalsAgent", "tool": "compute_fundamentals", "args": {"material": material}})
    tool_calls.append({"agent": "CalaSignalAgent", "tool": "gather_cala_signals", "args": {"material": material}})

    fund_signals: list[dict[str, Any]] = list(fund_out.get("signals") or [])
    cala_signals: list[dict[str, Any]] = list(cala_out.get("signals") or [])
    all_signals = [s for s in (fund_signals + cala_signals) if isinstance(s, dict) and s]
    evidence_urls: list[str] = list({u for s in all_signals for u in (s.get("evidence") or [])})
    # Also collect any URLs the cala_signal agent surfaced separately
    for u in cala_out.get("evidence_urls") or []:
        if u and u not in evidence_urls:
            evidence_urls.append(u)

    log.info("phase1 done | signals=%d evidence=%d", len(all_signals), len(evidence_urls))

    # ----- Phase 2 + 3: Forecast + Decision (deterministic, no LLM) -----
    # Groq tool-use validator chokes on large nested signal arrays passed through
    # an LLM; the underlying logic is pure math anyway. Call directly.
    t_det = time.perf_counter()
    target_coverage_months = 6.0
    current_months = None
    months_to_buy = 0
    try:
        signal_objs: list[Signal] = []
        for s in all_signals:
            try:
                signal_objs.append(Signal(**{k: v for k, v in s.items() if k in Signal.model_fields}))
            except Exception:
                log.warning("dropped malformed signal: %s", s.get("name"))

        history = get_price_history(material, lookback_days=365)
        history_tuples = [(p.date, p.price) for p in history]
        forecast_points_objs, forecast_summary_obj = build_forecast(history_tuples, horizon, signal_objs)
        forecast_summary = forecast_summary_obj.model_dump(mode="json")
        forecast_points_list = [fp.model_dump(mode="json") for fp in forecast_points_objs]
        spot_price_val = history_tuples[-1][1] if history_tuples else None
        spot_date_val = history_tuples[-1][0] if history_tuples else None
        timings["forecast"] = time.perf_counter() - t_det

        t_dec = time.perf_counter()
        mat_profile = get_profile(MaterialKey(material))
        prio_profile = get_priority_profile(PriorityProfileKey(priority))
        action, scores = decide_action(forecast_summary_obj, signal_objs, mat_profile, prio_profile)

        # Warehouse fill: surface as datapoint only — no action override.
        # Low fill = high inventory_pressure (buying more urgent); high fill = low pressure.
        if warehouse_fill is not None:
            try:
                fill = float(warehouse_fill)
                current_months = round((fill / 100.0) * target_coverage_months, 1)
                scores["inventory_pressure"] = round(max(0.0, min(100.0, 100.0 - fill)), 1)
                scores["warehouse_fill_pct"] = fill
                if action in (Action.BUY_NOW, Action.HEDGE):
                    months_to_buy = max(0, round(target_coverage_months - current_months))
            except Exception:
                log.warning("warehouse_fill_pct invalid: %r", warehouse_fill)

        md_res = missing_data_guardrail(all_signals)
        if not md_res["ok"]:
            action = getattr(Action, md_res["downgrade_to"], action)
            scores["confidence"] = 0.0
            
        conf_res = confidence_guardrail(action.value, scores["confidence"])
        if not conf_res["ok"]:
            action = getattr(Action, conf_res["downgrade_to"], action)

        driver_ctx = enrich_driver_context(material, signal_objs)
        
        decision = {
            "material": material,
            "action": action.value,
            "horizon_days": horizon,
            "scores": scores,
            "forecast_summary": forecast_summary,
            "main_drivers": [d.model_dump(mode="json") for d in build_drivers(signal_objs)],
            "explanation": build_explanation(action, forecast_summary_obj, horizon, scores["confidence"]),
            "active_drivers": driver_ctx["active_drivers"],
            "dormant_drivers": driver_ctx["dormant_drivers"],
            "cross_material_dependencies": driver_ctx["cross_material_dependencies"],
            "warehouse_fill_pct": warehouse_fill,
            "current_coverage_months": current_months,
            "target_coverage_months": target_coverage_months,
            "months_to_buy": months_to_buy,
        }
        timings["decision"] = time.perf_counter() - t_dec
        tool_calls.append({"agent": "Orchestrator", "tool": "build_forecast", "args": {"material": material, "n_signals": len(signal_objs)}})
        tool_calls.append({"agent": "Orchestrator", "tool": "decide_action", "args": {"material": material, "priority_profile": priority}})
    except Exception:
        log.exception("Deterministic forecast/decision failed — full fallback")
        decision = _run_recommendation(material, priority, horizon)
        forecast_summary = decision.get("forecast_summary") or {}
        tool_calls.append({"agent": "Orchestrator", "tool": "fallback_full_analysis", "args": {"material": material}})

    # ----- Phase 4: Explanation (serial, optional MCP) -----
    # Slim signal view — drop nested meta to keep prompt small.
    slim_signals = [
        {
            "name": s.get("name"),
            "direction": s.get("direction"),
            "score": s.get("score"),
            "confidence": s.get("confidence"),
        }
        for s in all_signals
    ]
    slim_decision = {
        "material": decision.get("material"),
        "action": decision.get("action"),
        "horizon_days": decision.get("horizon_days"),
        "scores": decision.get("scores"),
        "explanation": decision.get("explanation"),
        "warehouse_fill_pct": decision.get("warehouse_fill_pct"),
        "current_coverage_months": decision.get("current_coverage_months"),
        "months_to_buy": decision.get("months_to_buy"),
    }
    raw_conf = (decision.get("scores") or {}).get("confidence") if isinstance(decision, dict) else None
    try:
        conf_pct = int(round(float(raw_conf) * 100)) if raw_conf is not None and float(raw_conf) <= 1.0 else int(round(float(raw_conf or 0)))
    except Exception:
        conf_pct = 0
    wh_line = f"warehouse_fill_pct={warehouse_fill}\n" if warehouse_fill is not None else ""
    explanation_prompt = (
        f"Compose the user-facing card in ENGLISH ONLY. No placeholders, no other languages.\n"
        f"material={material} priority={priority} horizon_days={horizon} horizon_label={horizon_label} "
        f"analysis_type={analysis_type}\n"
        f"action={slim_decision.get('action')} confidence_pct={conf_pct}\n"
        f"{wh_line}"
        f"DECISION={json.dumps(slim_decision)}\n"
        f"SIGNALS={json.dumps(slim_signals)}\n"
        f"EVIDENCE_URLS={json.dumps(evidence_urls[:8])}\n"
        f"Write the ACTION line as: 'ACTION: {slim_decision.get('action')} for {material} over {horizon}d (confidence {conf_pct}%)'.\n"
        f"If action is BUY_NOW or HEDGE, add a line: 'QUANTITY: buy ~{slim_decision.get('months_to_buy')} months of coverage "
        f"(current stock ≈ {slim_decision.get('current_coverage_months')} months, target {target_coverage_months}).' "
        f"Otherwise omit the QUANTITY line.\n"
        f"Warehouse fill is a datapoint, not a rule: weigh it alongside price/supply/geo signals. "
        f"Mention it in TOP DRIVERS or COUNTER-DRIVERS when it materially shifts the picture (low fill → urgency, high fill → can wait).\n"
    )

    # Skip LLM Explanation entirely — structured response is built by analyze_builder.
    # Provide a deterministic narrative string for back-compat with /agent/chat callers.
    explanation_text = decision.get("explanation") or ""
    qty_line = ""
    if slim_decision.get("action") in ("BUY_NOW", "HEDGE") and slim_decision.get("months_to_buy"):
        qty_line = (
            f"\nQUANTITY: buy ~{slim_decision.get('months_to_buy')} months "
            f"(current stock ≈ {slim_decision.get('current_coverage_months')} months, target {target_coverage_months})."
        )
    answer = (
        f"ACTION: {slim_decision.get('action')} for {material} over {horizon}d "
        f"(confidence {conf_pct}%)."
        f"{qty_line}\n"
        f"{explanation_text}"
    )
    timings["explanation"] = 0.0

    log.info("orchestrator done | timings=%s tool_calls=%d", timings, len(tool_calls))

    return OrchestratorResult(
        answer=answer,
        tool_calls=tool_calls,
        decision=decision,
        signals=all_signals,
        evidence_urls=evidence_urls,
        timings=timings,
        raw={"fundamentals": fund_out, "cala_signal": cala_out, "decision": decision},
        forecast_points=locals().get("forecast_points_list"),
        spot_price=locals().get("spot_price_val"),
        spot_date=locals().get("spot_date_val"),
    )
