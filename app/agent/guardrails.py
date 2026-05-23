"""
Output guardrails for the procurement analyst agent.

These run after the agent produces its answer. If a guardrail trips, the
caller should either reject the answer or downgrade the recommendation to
MONITOR. See wiki/concepts/agent-guardrails.md.
"""

from __future__ import annotations

import re
from typing import Any

ALLOWED_ACTIONS = {"BUY_NOW", "WAIT", "HEDGE", "MONITOR"}

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text or ""))


def quantitative_guardrail(answer: str, tool_outputs: list[Any]) -> dict[str, Any]:
    """Every number in `answer` must appear somewhere in a tool result."""
    allowed: set[str] = set()
    for out in tool_outputs:
        allowed |= numbers_in(str(out))
    used = numbers_in(answer)
    invented = sorted(used - allowed)
    return {"ok": not invented, "invented_numbers": invented}


def recommendation_guardrail(action: str | None) -> dict[str, Any]:
    if action is None:
        return {"ok": True}
    return {"ok": action in ALLOWED_ACTIONS, "action": action, "allowed": sorted(ALLOWED_ACTIONS)}


def confidence_guardrail(action: str, confidence: float) -> dict[str, Any]:
    """If confidence < 0.45, block BUY_NOW / full HEDGE."""
    if confidence < 0.45 and action in {"BUY_NOW", "HEDGE"}:
        return {"ok": False, "downgrade_to": "MONITOR", "reason": "low_confidence"}
    return {"ok": True}


def missing_data_guardrail(tool_outputs: list[Any]) -> dict[str, Any]:
    if not tool_outputs:
        return {"ok": False, "downgrade_to": "MONITOR", "reason": "no_tool_calls"}
    return {"ok": True}
