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
if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
    log.addHandler(handler)
log.setLevel(logging.INFO)

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


def _make_model() -> Any:
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
    """Run one agent turn. Returns answer + tool-call audit trail."""
    ctx = context or {}
    log.info("run_agent start | msg=%r ctx=%s", message[:120], ctx)

    if not _SDK_AVAILABLE or not settings.groq_api_key:
        material = ctx.get("material", "barley")
        priority = ctx.get("priority_profile", "balanced")
        log.warning("SDK unavailable or GROQ_API_KEY empty — deterministic fallback for %s", material)
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
    log.info("Runner.run start | model=%s tools=%d mcp_servers=%d", settings.agent_model, len(ALL_TOOLS), len(mcp_servers))
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
        log.info("  tool: %s args=%s", tc.get("tool"), str(tc.get("args"))[:200])
    return AgentRunResult(answer=str(result.final_output), tool_calls=tool_calls, raw=result)
