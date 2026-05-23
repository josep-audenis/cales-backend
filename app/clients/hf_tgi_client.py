"""
HF Space TGI client adapter.

TGI's OpenAI-compatible /v1/chat/completions endpoint has two spec violations:

1. tool_call.function.arguments returned as a JSON object instead of a JSON-encoded
   string — breaks strict pydantic validation in openai-agents SDK.

2. finish_reason=stop even when tool_calls are present — should be "tool_calls".
   This causes the openai-agents SDK to loop forever: it calls the tool, gets the
   result, sends it back, model emits the same tool_call with finish_reason=stop
   again, SDK calls the tool again, ad infinitum.

3. Assistant messages with tool_calls have content=null (correct per spec), but our
   request hook was flattening that to "" which may confuse TGI's context handling.

This module patches all three issues via httpx event hooks.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from openai import AsyncOpenAI

log = logging.getLogger("app.clients.hf_tgi")


def _flatten_content(content: Any) -> str:
    """Coerce any OpenAI content value -> plain string for TGI."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block.get("content"), str):
                    parts.append(block["content"])
                else:
                    parts.append(json.dumps(block))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        return json.dumps(content)
    return str(content)


async def _flatten_request_content(request: httpx.Request) -> None:
    """Rewrite messages[*].content from non-string to plain string for TGI.

    Skips assistant messages that have tool_calls — those legitimately have
    content=null per the OpenAI spec and TGI expects them that way.
    """
    if "chat/completions" not in str(request.url):
        return
    body = request.content
    if not body:
        return
    try:
        data = json.loads(body)
    except Exception:
        return
    messages = data.get("messages")
    if not isinstance(messages, list):
        return

    # --- DETAILED TURN LOGGING ---
    turn = len([m for m in messages if isinstance(m, dict) and m.get("role") == "assistant"])
    log.info("hf_tgi >>>REQUEST turn=%d total_messages=%d", turn, len(messages))
    for idx, m in enumerate(messages):
        if not isinstance(m, dict):
            continue
        role = m.get("role", "?")
        tool_calls = m.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                fn = (tc.get("function") or {})
                log.info("  msg[%d] role=%s TOOL_CALL name=%s args=%s", idx, role, fn.get("name"), str(fn.get("arguments", ""))[:200])
        elif role == "tool":
            log.info("  msg[%d] role=tool tool_call_id=%s content=%s", idx, m.get("tool_call_id"), str(m.get("content", ""))[:200])
        else:
            log.info("  msg[%d] role=%s content=%s", idx, role, str(m.get("content", ""))[:120])
    # --- END TURN LOGGING ---

    changed = False
    for idx, m in enumerate(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") == "assistant" and m.get("tool_calls"):
            m["content"] = ""
            changed = True
            log.info("hf_tgi: set messages[%d].content to empty string (assistant+tool_calls)", idx)
            continue
        c = m.get("content")
        if not isinstance(c, str):
            new_c = _flatten_content(c)
            m["content"] = new_c
            changed = True
            log.info("hf_tgi: flattened messages[%d].content (role=%s, type=%s -> str len=%d)", idx, m.get("role"), type(c).__name__, len(new_c))


    # --- LOOP PREVENTION: STRIP TOOLS ONCE PLAN IS COMPLETED ---
    executed_tools: set[str] = set()
    call_id_to_name: dict[str, str] = {}
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                tc_id = tc.get("id")
                tc_name = (tc.get("function") or {}).get("name")
                if tc_id and tc_name:
                    call_id_to_name[tc_id] = tc_name
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("role") == "tool":
            tcid = m.get("tool_call_id")
            if tcid in call_id_to_name:
                executed_tools.add(call_id_to_name[tcid])

    strip_tools = False
    if "compute_seasonality_signal_tool" in executed_tools:
        strip_tools = True
        log.info("hf_tgi: stripping tools because compute_seasonality_signal_tool has been executed")
    if "cala_weather_signal" in executed_tools:
        strip_tools = True
        log.info("hf_tgi: stripping tools because cala_weather_signal has been executed")
    if "cala_disruption_scan" in executed_tools:
        is_barley = False
        for m in messages:
            content_str = str(m.get("content") or "")
            if "barley" in content_str.lower():
                is_barley = True
                break
        if not is_barley:
            strip_tools = True
            log.info("hf_tgi: stripping tools because cala_disruption_scan has been executed (non-barley)")

    if strip_tools:
        if "tools" in data:
            del data["tools"]
            changed = True
        if "tool_choice" in data:
            del data["tool_choice"]
            changed = True

    if changed:
        new_body = json.dumps(data).encode("utf-8")
        request._content = new_body  # type: ignore[attr-defined]
        request.stream = httpx.ByteStream(new_body)  # type: ignore[attr-defined]
        request.headers["content-length"] = str(len(new_body))
        request.headers.pop("transfer-encoding", None)
        log.info("hf_tgi: rewrote body, new content-length=%d", len(new_body))
    else:
        log.debug("hf_tgi: no content flatten needed (%d messages)", len(messages))


async def _coerce_tool_args_to_string(response: httpx.Response) -> None:
    """Fix two TGI response bugs:
    1. tool_call.function.arguments returned as dict instead of JSON string.
    2. finish_reason=stop when tool_calls present — must be "tool_calls" so the
       SDK knows to call the tool and wait for a final text response.
    """
    if "chat/completions" not in str(response.request.url):
        return
    ctype = response.headers.get("content-type", "")
    log.info("hf_tgi <<<RESPONSE status=%d content-type=%s", response.status_code, ctype)
    if "application/json" not in ctype:
        log.info("hf_tgi <<<RESPONSE skipping hook (not JSON — streaming SSE?)")
        return
    try:
        await response.aread()
    except Exception:
        return
    try:
        data = json.loads(response.content)
    except Exception:
        return

    changed = False
    for choice in data.get("choices") or []:
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls")

        # Fix 1: coerce arguments to string and assign unique tool call ID.
        for tc in tool_calls or []:
            import uuid
            old_id = tc.get("id")
            new_id = f"call_{uuid.uuid4().hex[:8]}"
            tc["id"] = new_id
            fn = tc.get("function") or {}
            args: Any = fn.get("arguments")
            if not isinstance(args, str):
                fn["arguments"] = json.dumps(args) if args is not None else "{}"
            changed = True
            log.info("hf_tgi: assigned unique tool call ID %s (was %s)", new_id, old_id)

        # Fix 2: TGI returns finish_reason=stop even when tool_calls present.
        # The SDK uses finish_reason to decide whether to call tools or emit final
        # output. With "stop" + tool_calls it gets confused and loops. Force "tool_calls".
        if tool_calls and choice.get("finish_reason") != "tool_calls":
            log.info("hf_tgi: fixing finish_reason stop→tool_calls (TGI bug)")
            choice["finish_reason"] = "tool_calls"
            changed = True

    # --- DETAILED RESPONSE LOGGING ---
    for choice in data.get("choices") or []:
        msg = choice.get("message") or {}
        finish = choice.get("finish_reason")
        role = msg.get("role", "?")
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                fn = (tc.get("function") or {})
                log.info("hf_tgi <<<RESPONSE finish=%s TOOL_CALL name=%s args=%s", finish, fn.get("name"), str(fn.get("arguments", ""))[:200])
        else:
            log.info("hf_tgi <<<RESPONSE finish=%s role=%s content=%s", finish, role, str(msg.get("content", ""))[:300])
    # --- END RESPONSE LOGGING ---

    if changed:
        new_body = json.dumps(data).encode("utf-8")
        response._content = new_body  # type: ignore[attr-defined]
        if "content-length" in response.headers:
            response.headers["content-length"] = str(len(new_body))


def make_tgi_async_openai(*, api_key: str, base_url: str, timeout: float = 120.0) -> AsyncOpenAI:
    http_client = httpx.AsyncClient(
        event_hooks={
            "request": [_flatten_request_content],
            "response": [_coerce_tool_args_to_string],
        },
        timeout=timeout,
    )
    return AsyncOpenAI(api_key=api_key or "dummy", base_url=base_url, http_client=http_client)
