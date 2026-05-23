---
type: synthesis
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [architecture, agent, multi-agent, orchestration, cala]
---

# Multi-Agent Orchestration

Supersedes single-agent shell in [[agent-architecture]]. Same deterministic tool layer underneath — execution shell is now a 5-agent crew under a code-level Orchestrator.

## Topology (star)

```
Orchestrator  (code, not LLM — drives flow + parses JSON)
 ├─ FundamentalsAgent    → price-derived signals (local tools)
 ├─ CalaSignalAgent      → producer / disruption / weather (wrapped Cala REST)
 ├─ ForecastAgent        → corridor (consumes upstream signals)
 ├─ DecisionAgent        → action + scores (consumes forecast + signals)
 └─ ExplanationAgent     → user-facing narrative + citations (+ Cala MCP knowledge_search)
```

No peer-to-peer agent chat. JSON handoffs only. Orchestrator owns sequencing.

## Flow

```
phase 1 (parallel via asyncio.gather):
  Fundamentals → {signals[], features}
  CalaSignal   → {signals[], evidence_urls[]}

phase 2 (serial):
  Forecast(material, horizon, all_signals) → {forecast_summary}
  Decision(material, priority, horizon, all_signals) → {decision}
  Explanation(decision, signals, urls, forecast) → narrative card
```

Fundamentals + CalaSignal are independent → parallel. Forecast consumes signals, Decision consumes forecast + signals, Explanation consumes everything → serial.

## Why 5 agents (hackathon-sized)

| Benefit | Mechanism |
|---|---|
| Lower latency | `asyncio.gather` on Fundamentals + CalaSignal cuts phase 1 ≈50% |
| Token isolation | Raw Cala 5-30KB payloads stay inside CalaSignalAgent; Orchestrator sees only compressed `Signal[]` |
| Sharper outputs | Each subagent prompt is narrow → less tool confusion than one 32-tool mega-prompt |
| Explainability composes | Each signal ships `evidence[]` URLs → Explanation cites them without re-fetching |
| Independent failure | Cala fails → Fundamentals still ships; Decision degrades gracefully |
| Pitch story | 5 visible agent badges = demo theater |

Cost: 5 LLM calls per request vs 1. Mitigated by Groq free tier + Phase 1 parallelism. Hard fallback to deterministic `_run_recommendation` if Decision returns empty.

## Tool routing (one subset per subagent)

| Subagent | Tools |
|---|---|
| Fundamentals | `get_price_history_tool`, `compute_price_features`, `compute_momentum_signal`, `compute_seasonality_signal_tool` |
| CalaSignal | `cala_producer_graph`, `cala_disruption_scan`, `cala_weather_signal` |
| Forecast | `build_forecast_summary` |
| Decision | `score_and_decide`, `fallback_full_analysis` |
| Explanation | Cala MCP `knowledge_search` only (no local tools) |

See [[cala-signal-extraction]] for the 3 wrapped Cala tools + UUID cache.

## I/O contracts (JSON-only)

Each subagent's prompt forces JSON output. Orchestrator parses, ignores raw text on parse failure (logs warning). No LLM-mediated handoffs — orchestrator is code.

```
FundamentalsAgent  → {"signals": [...], "features": {...}}
CalaSignalAgent    → {"signals": [...], "evidence_urls": [...]}
ForecastAgent      → {"forecast_summary": {...}}
DecisionAgent      → {"decision": {...}}
ExplanationAgent   → plain text (4-section card, ≤180 words)
```

## File layout

- `app/agent/orchestrator.py` — Orchestrator + 5 subagent factories + `run_orchestrator()`
- `app/agent/cala_tools.py` — 3 wrapped Cala REST tools + UUID cache
- `app/agent/prompts.py` — 5 subagent system prompts + legacy single-agent prompt
- `app/agent/tools.py` — tool subsets (`FUNDAMENTALS_TOOLS`, `FORECAST_TOOLS`, `DECISION_TOOLS`, `EXPLANATION_TOOLS`) + back-compat `ALL_TOOLS`
- `app/agent/runtime.py` — delegates to `run_orchestrator`; legacy single-agent path behind `ctx["legacy_single_agent"]`

## Degradation ladder

```
1. Multi-agent orchestrator (default)
2. ctx["legacy_single_agent"] = true       → original single-agent shell
3. GROQ_API_KEY missing or SDK unavailable → deterministic _run_recommendation
```

## Open items

- Compare-materials flow: orchestrator should fan out N material runs in parallel (not yet wired).
- Streaming: stream subagent results to UI as they land for visible "crew working" effect.
- Caching: Phase 1 outputs cacheable per `(material, day)` — saves redundant calls in compare/what-if.
- Retry per subagent on JSON-parse failure (currently single attempt).

## Related

[[agent-architecture]], [[Cala-ai]], [[cala-signal-extraction]], [[agent-tools]], [[agent-guardrails]], [[decision-engine]], [[signal-normalization]].
