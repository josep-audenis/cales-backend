"""
Agent runtime. OpenAI Agents SDK + Groq model + Cala MCP.

Per-request MCP connection — caching across requests breaks the SDK's anyio
task scopes (the cached generator is entered in one task and exited in another,
raising "Attempted to exit cancel scope in a different task").
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.agent.prompts import PROCUREMENT_ANALYST_SYSTEM
from app.agent.tools import ALL_TOOLS, _run_recommendation
from app.core.config import settings

log = logging.getLogger("app.agent")

try:
    from agents import Agent, Runner, set_tracing_disabled  # type: ignore
    from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter  # type: ignore
    from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel  # type: ignore
    from openai import AsyncOpenAI  # type: ignore

    set_tracing_disabled(True)  # using Groq, no OpenAI trace export
    _SDK_AVAILABLE = True
except Exception as e:  # pragma: no cover
    log.warning("openai-agents SDK unavailable: %s", e)
    _SDK_AVAILABLE = False


@dataclass
class AgentRunResult:
    answer: str
    tool_calls: list[dict[str, Any]]
    raw: Any | None = None
    decision: dict[str, Any] | None = None
    signals: list[dict[str, Any]] | None = None
    evidence_urls: list[str] | None = None
    forecast_points: list[dict[str, Any]] | None = None
    spot_price: float | None = None
    spot_date: Any | None = None


def _make_model() -> Any:
    if settings.llm_provider == "hf":
        # HF Space TGI: OpenAI-compatible, served at <base>/v1/chat/completions.
        # Uses a wrapper that fixes TGI's non-spec tool-call arguments (dict -> JSON string).
        from app.clients.hf_tgi_client import make_tgi_async_openai

        client = make_tgi_async_openai(api_key=settings.hf_token, base_url=settings.hf_space_base_url)
        return OpenAIChatCompletionsModel(model=settings.hf_model, openai_client=client)
    client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return OpenAIChatCompletionsModel(model=settings.agent_model, openai_client=client)


def _make_agent(mcp_servers: list[Any]) -> Any:
    return Agent(
        name="ProcurementAnalyst",
        instructions=PROCUREMENT_ANALYST_SYSTEM,
        model=_make_model(),
        tools=ALL_TOOLS,
        mcp_servers=mcp_servers,
    )


def _extract_tool_calls(result: Any) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for item in getattr(result, "new_items", []) or []:
        cls_name = type(item).__name__
        if cls_name == "ToolCallItem":
            raw = getattr(item, "raw_item", None)
            tool_calls.append(
                {
                    "tool": getattr(raw, "name", None),
                    "args": getattr(raw, "arguments", None),
                }
            )
        elif cls_name == "ToolCallOutputItem":
            if tool_calls:
                tool_calls[-1]["output"] = getattr(item, "output", None)
    return tool_calls


async def run_agent(message: str, context: dict[str, Any] | None = None) -> AgentRunResult:
    """Run one agent turn. Delegates to the multi-agent orchestrator by default."""
    ctx = context or {}
    log.info("run_agent start | msg=%r ctx=%s", message[:120], ctx)

    have_llm_key = (
        bool(settings.hf_token) if settings.llm_provider == "hf" else bool(settings.groq_api_key)
    )
    if not _SDK_AVAILABLE or not have_llm_key:
        material = ctx.get("material", "barley")
        priority = ctx.get("priority_profile", "balanced")
        log.warning(
            "SDK unavailable or LLM key empty (provider=%s) — deterministic fallback for %s",
            settings.llm_provider,
            material,
        )
        rec = _run_recommendation(
            material=material,
            priority_profile=priority,
            horizon_days=ctx.get("horizon_days", 180),
        )
        return AgentRunResult(
            answer=f"[fallback] Action {rec['action']} on {material} for {rec['horizon_days']}d. {rec['explanation']}",
            tool_calls=[{"tool": "compute_recommendation", "args": {"material": material}}],
            raw=rec,
        )

    # Default path: multi-agent orchestrator.
    use_legacy = bool(ctx.get("legacy_single_agent"))
    if not use_legacy:
        try:
            from app.agent.orchestrator import run_orchestrator

            orch = await run_orchestrator(message, ctx)
            return AgentRunResult(
                answer=orch.answer,
                tool_calls=orch.tool_calls,
                raw={
                    "decision": orch.decision,
                    "signals": orch.signals,
                    "evidence_urls": orch.evidence_urls,
                    "timings": orch.timings,
                    "subagent_outputs": orch.raw,
                },
                decision=orch.decision,
                signals=orch.signals,
                evidence_urls=orch.evidence_urls,
                forecast_points=orch.forecast_points,
                spot_price=orch.spot_price,
                spot_date=orch.spot_date,
            )
        except Exception:
            log.exception("Orchestrator failed — falling back to single-agent path")

    t0 = time.perf_counter()
    mcp_servers: list[Any] = []

    # Connect Cala MCP per-request (caching breaks anyio task affinity)
    if settings.cala_mcp_api_key:
        log.info("connecting Cala MCP at %s", settings.cala_mcp_url)
        cala = MCPServerStreamableHttp(
            params={
                "url": settings.cala_mcp_url,
                "headers": {"X-API-KEY": settings.cala_mcp_api_key},
                "timeout": 120.0,
                "sse_read_timeout": 300.0,
            },
            name="cala",
            cache_tools_list=True,
            client_session_timeout_seconds=120,
            tool_filter=create_static_tool_filter(allowed_tool_names=["knowledge_search"]),
        )
        try:
            async with cala as connected:
                mcp_servers.append(connected)
                log.info("Cala MCP connected in %.2fs", time.perf_counter() - t0)
                return await _run_with(message, ctx, mcp_servers)
        except Exception:
            log.exception("Cala MCP failed; running agent without it")
            return await _run_with(message, ctx, [])
    else:
        log.warning("CALA_MCP_API_KEY empty — agent runs without Cala MCP")
        return await _run_with(message, ctx, [])


async def _run_with(message: str, ctx: dict[str, Any], mcp_servers: list[Any]) -> AgentRunResult:
    agent = _make_agent(mcp_servers)
    active_model = settings.hf_model if settings.llm_provider == "hf" else settings.agent_model
    log.info(
        "Runner.run start | provider=%s model=%s tools=%d mcp_servers=%d",
        settings.llm_provider,
        active_model,
        len(ALL_TOOLS),
        len(mcp_servers),
    )
    t0 = time.perf_counter()
    try:
        result = await Runner.run(agent, input=message, context=ctx)
    except Exception:
        log.exception("Runner.run failed")
        raise
    dt = time.perf_counter() - t0
    tool_calls = _extract_tool_calls(result)
    log.info("Runner.run done in %.2fs | tool_calls=%d", dt, len(tool_calls))
    for tc in tool_calls:
        log.debug("  tool: %s args=%s", tc.get("tool"), str(tc.get("args"))[:200])
    return AgentRunResult(answer=str(result.final_output), tool_calls=tool_calls, raw=result)
