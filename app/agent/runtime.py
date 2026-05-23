"""
Agent runtime. Wires OpenAI Agents SDK to a Groq-hosted model via
OpenAI-compatible endpoint.

Environment variables (see app/core/config.py):
  GROQ_API_KEY        Groq API key
  GROQ_BASE_URL       https://api.groq.com/openai/v1
  AGENT_MODEL         e.g. "llama-3.3-70b-versatile"

Falls back gracefully if the SDK is not installed; callers can still invoke
deterministic tools via app.agent.tools.call_raw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agent.prompts import PROCUREMENT_ANALYST_SYSTEM
from app.agent.tools import ALL_TOOLS, call_raw
from app.core.config import settings

try:
    from agents import Agent, Runner  # type: ignore
    from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel  # type: ignore
    from openai import AsyncOpenAI  # type: ignore

    _SDK_AVAILABLE = True
except Exception:  # pragma: no cover
    _SDK_AVAILABLE = False


@dataclass
class AgentRunResult:
    answer: str
    tool_calls: list[dict[str, Any]]
    raw: Any | None = None


def _build_agent() -> Any:
    if not _SDK_AVAILABLE:
        raise RuntimeError(
            "openai-agents not installed. `pip install openai-agents` "
            "or use deterministic fallback via /recommendation."
        )
    client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    model = OpenAIChatCompletionsModel(model=settings.agent_model, openai_client=client)
    return Agent(
        name="ProcurementAnalyst",
        instructions=PROCUREMENT_ANALYST_SYSTEM,
        model=model,
        tools=ALL_TOOLS,
    )


_agent_singleton: Any | None = None


def get_agent() -> Any:
    global _agent_singleton
    if _agent_singleton is None:
        _agent_singleton = _build_agent()
    return _agent_singleton


async def run_agent(message: str, context: dict[str, Any] | None = None) -> AgentRunResult:
    """Run a single agent turn. Returns answer + tool-call audit trail."""
    if not _SDK_AVAILABLE or not settings.groq_api_key:
        # Demo-safety: deterministic fallback
        material = (context or {}).get("material", "barley")
        priority = (context or {}).get("priority_profile", "balanced")
        rec = call_raw(
            "compute_recommendation",
            material=material,
            priority_profile=priority,
            horizon_days=(context or {}).get("horizon_days", 180),
        )
        return AgentRunResult(
            answer=(
                f"[fallback] Action {rec['action']} on {material} "
                f"for {rec['horizon_days']}d. {rec['explanation']}"
            ),
            tool_calls=[{"tool": "compute_recommendation", "args": {"material": material}}],
            raw=rec,
        )

    agent = get_agent()
    result = await Runner.run(agent, input=message, context=context or {})
    tool_calls = []
    for item in getattr(result, "new_items", []) or []:
        if getattr(item, "type", None) == "tool_call":
            tool_calls.append(
                {"tool": getattr(item, "name", None), "args": getattr(item, "arguments", None)}
            )
    return AgentRunResult(answer=str(result.final_output), tool_calls=tool_calls, raw=result)
