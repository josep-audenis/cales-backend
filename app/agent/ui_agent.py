"""UI-control agent. Given page state + visible controls, return explanation + cursor actions."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.schemas.ui_agent import UIAction, UIAgentRequest, UIAgentResponse

log = logging.getLogger("app.agent.ui")

SYSTEM_PROMPT = """You are the Cales UI cursor agent. You drive a frontend cursor on a procurement workspace.

You receive:
- prompt: a natural-language instruction from the user.
- page_id, route, material: where on the app the user is.
- screen_state: current React state for the page.
- visible_controls: every control the cursor may target. Each has target_id, label, type, selected, disabled, metadata.

You must return STRICT JSON with this shape:
{
  "explanation": "<plain-language explanation of the screen or planned changes>",
  "actions": [
    {"type": "click|toggle_on|toggle_off|select", "target_id": "<id>", "reason": "<why>", "value": <optional>}
  ],
  "requires_confirmation": <bool>
}

Hard rules:
- Every action.target_id MUST appear in visible_controls. Never invent ids.
- Do not target controls with disabled=true.
- For toggle_on, the control must currently be selected=false. For toggle_off, selected=true. Skip otherwise.
- Keep actions minimal and ordered. Prefer 1-4 actions unless the user clearly asks for more.
- "explanation" must be useful to a procurement analyst: describe the screen or what your actions will change and why.
- Set requires_confirmation=true when actions mutate selection or trigger generate/submit-style buttons.
- Output JSON only. No prose outside the JSON object.

generate_report button rule:
- When the user's intent is to generate, create, run, or produce a report (any phrasing), you MUST include a final action {"type": "click", "target_id": "generate_report", "reason": "<why>"} — but ONLY if "generate_report" appears in visible_controls and is not disabled.
- Always place the generate_report click last, after any toggle actions."""


def _build_user_message(req: UIAgentRequest) -> str:
    payload = {
        "prompt": req.prompt,
        "page_id": req.page_id,
        "route": req.route,
        "material": req.material,
        "screen_state": req.screen_state,
        "visible_controls": [c.model_dump(exclude_none=True) for c in req.visible_controls],
    }
    return json.dumps(payload, ensure_ascii=False)


def _make_client_and_model() -> tuple[Any, str]:
    from openai import AsyncOpenAI  # type: ignore

    if settings.llm_provider == "hf":
        from app.clients.hf_tgi_client import make_tgi_async_openai

        client = make_tgi_async_openai(api_key=settings.hf_token, base_url=settings.hf_space_base_url)
        return client, settings.hf_model
    client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return client, settings.agent_model


def _fallback_response(req: UIAgentRequest, reason: str = "LLM unavailable") -> UIAgentResponse:
    return UIAgentResponse(
        explanation=(
            f"Screen '{req.page_id}' with {len(req.visible_controls)} controls. "
            f"{reason} — returning no actions."
        ),
        actions=[],
        requires_confirmation=False,
    )


def _sanitize(resp: UIAgentResponse, req: UIAgentRequest) -> UIAgentResponse:
    valid_ids = {c.target_id: c for c in req.visible_controls}
    cleaned: list[UIAction] = []
    for a in resp.actions:
        ctl = valid_ids.get(a.target_id)
        if ctl is None or ctl.disabled:
            log.warning("dropping action with invalid/disabled target_id=%s", a.target_id)
            continue
        if a.type == "toggle_on" and ctl.selected is True:
            continue
        if a.type == "toggle_off" and ctl.selected is False:
            continue
        cleaned.append(a)
    prompt = req.prompt.lower()
    generate_ctl = valid_ids.get("generate_report")
    _generation_triggers = ("generate", "create report", "run report", "produce report", "run the report", "run analysis", "go", "run it", "do it", "submit")
    wants_generation = any(t in prompt for t in _generation_triggers)
    already_clicks_generate = any(a.type == "click" and a.target_id == "generate_report" for a in cleaned)
    if wants_generation and generate_ctl is not None and not generate_ctl.disabled and not already_clicks_generate:
        cleaned.append(
            UIAction(
                type="click",
                target_id="generate_report",
                reason="Generate the report after applying the requested input changes.",
            )
        )
    return UIAgentResponse(
        explanation=resp.explanation,
        actions=cleaned,
        requires_confirmation=resp.requires_confirmation or bool(cleaned),
    )


async def run_ui_agent(req: UIAgentRequest) -> UIAgentResponse:
    have_key = bool(settings.hf_token) if settings.llm_provider == "hf" else bool(settings.groq_api_key)
    if not have_key:
        log.warning("UI agent: no LLM key for provider=%s — fallback", settings.llm_provider)
        return _fallback_response(req, reason=f"no LLM key for provider={settings.llm_provider}")

    client, model = _make_client_and_model()
    try:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(req)},
            ],
            "temperature": 0.2,
        }
        # Groq supports json_object; TGI/HF often does not.
        if settings.llm_provider == "groq":
            kwargs["response_format"] = {"type": "json_object"}
        completion = await client.chat.completions.create(**kwargs)
    except Exception as e:
        log.exception("UI agent LLM call failed")
        return _fallback_response(req, reason=f"LLM call failed: {type(e).__name__}: {e}")

    content = (completion.choices[0].message.content or "{}").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
        content = content.strip()
    # Extract first {...} block if extra prose snuck in.
    if not content.startswith("{"):
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start : end + 1]
    try:
        data = json.loads(content)
        resp = UIAgentResponse.model_validate(data)
    except Exception as e:
        log.exception("UI agent returned invalid JSON: %s", content[:400])
        return _fallback_response(req, reason=f"invalid JSON from LLM: {type(e).__name__}")

    return _sanitize(resp, req)
