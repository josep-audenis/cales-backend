---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [agent, guardrails, safety]
---

# Agent Guardrails

Rules enforced on agent output for [[agent-architecture]]. Implemented in `app/agent/guardrails.py` as OpenAI Agents SDK output validators where possible; otherwise post-hoc checks before returning.

## Quantitative guardrail

Agent **must not** mention a number unless it came from a tool result in the current run. Validator scans response for numeric tokens not present in any tool output → flag and ask agent to retry.

## Source guardrail

Agent cannot cite a source not present in `evidence[]` of returned signals or in [[Cala-ai]] registry. Hallucinated source names (e.g., "Bloomberg") → strip + warn.

## Recommendation guardrail

Action must be one of `BUY_NOW | WAIT | HEDGE | MONITOR`. See [[recommendation-actions]]. Anything else → reject.

## Missing-data guardrail

If a critical tool fails or returns empty signals:
- force `action = MONITOR`
- state limitation explicitly
- list what data is needed

## Confidence guardrail

If `confidence < 0.45`:
- never recommend `BUY_NOW` or full-coverage `HEDGE`
- downgrade to `MONITOR` or partial coverage

## Tool-failure guardrail

If [[Cala-ai]] fails:
- use `build_base_risk_cone` only (skip Cala adjustment)
- flag `external_intelligence_unavailable: true`
- lower confidence by 0.15

## Demo guardrail

Always have mock Cala JSON in `data/sample/`. Code path must work offline.

## Implementation notes

- SDK `output_guardrail` decorator wraps the analyst agent.
- Numeric-token check uses a regex sweep over tool result JSON serialized values.
- Audit trail (`get_audit_trail`) records every tool invocation — guardrail violations append a `guardrail_triggered` event.

## Related

[[agent-architecture]], [[agent-tools]], [[recommendation-actions]], [[Cala-ai]].
