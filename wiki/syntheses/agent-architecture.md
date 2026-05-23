---
type: synthesis
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2, smartbuy-brief]
tags: [architecture, agent, plan, llm]
---

# Agent Architecture — Tool-First Procurement Analyst

Pivot from pure deterministic pipeline ([[architecture-v2]]) to **agent + tools**. Deterministic engine stays — it becomes the tool layer. LLM only plans and narrates; never invents numbers.

Supersedes execution model in [[architecture-v2]]; underlying layers (Data / Forecast / Signals / Decision) unchanged.

> **Superseded execution shell (2026-05-23):** single Procurement Analyst agent has been replaced by a 5-agent crew under an Orchestrator. See [[multi-agent-orchestration]] for the new flow. This page remains accurate for the tool layer + guardrails; the LLM-driving section below describes the legacy single-agent shell.

## Core principle

```
LLM agent  = planner + narrator
Python tools = calculations + data + recommendations
Frontend = cockpit + chat
```

LLM must not think quantitatively. Every number comes from a tool call. See [[agent-guardrails]].

## Stack

- **Framework:** OpenAI Agents SDK (provider-agnostic; gives agents, tools, handoffs, guardrails, structured outputs, tracing).
- **External knowledge:** Cala MCP (`https://api.cala.ai/mcp/`, `X-API-KEY`). Tools attached natively: `knowledge_search`, `knowledge_query`, `entity_search`, `entity_introspection`, `retrieve_entity`. Uses `strict_mode=False` on our own tools that pass through Cala-shaped signals.
- **LLM primary:** Groq free tier (`llama-3.1-8b-instant` default, OpenAI-compatible).
- **LLM fallback:** Gemini Flash → Ollama local.
- **Demo fallback:** `fallback_full_analysis` deterministic pipeline button — works without any LLM.

## Agent topology

**MVP:** single `ProcurementAnalystAgent` with all tools.

**Stretch:** specialist split — `MarketDataAgent`, `QuantRiskAgent`, `DecisionAgent`, `NarrativeAgent` via SDK handoffs.

## System prompt (binding)

```
You are a procurement intelligence analyst.

You must not invent prices, probabilities, scores or sources.
For any quantitative claim, call the relevant tool first.
You may explain, compare and summarize, but all numbers must come from tools.
If data is missing, say what is missing and recommend monitoring.

Recommendations limited to: BUY_NOW, WAIT, HEDGE, MONITOR.

Always include:
- action
- horizon
- confidence
- main drivers
- counter-drivers
- evidence sources
- what to monitor next
```

## Tool layer

Full catalog in [[agent-tools]]. Categories:

```
A. Data ingestion       (get_available_materials, get_price_history,
                         get_cala_market_signals, get_source_registry)
B. Price features       (compute_price_features, momentum, seasonality)
C. Volatility/regime    (compute_volatility_regime, classify_market_regime,
                         detect_anomalies)
D. Quant analogues      (find_historical_analogues, build_forward_return_distribution)
E. Cala normalization   (normalize_cala_signals, compute_external_risk_scores)
F. Risk cone            (build_base_risk_cone, adjust_risk_cone_with_cala,
                         generate_chart_payload)
G. Decision             (compute_risk_opportunity_scores, compute_recommendation,
                         compute_coverage_suggestion, compare_materials)
H. Scenario             (run_scenario, stress_test_material)
I. Explanation          (generate_explanation, generate_procurement_memo,
                         get_audit_trail)
J. Agent control        (validate_material, validate_priority_profile,
                         list_capabilities, fallback_full_analysis)
```

## Orchestration patterns

Recommendation → `validate_material` → `get_price_history` → `compute_volatility_regime` → `classify_market_regime` → `find_historical_analogues` → `build_forward_return_distribution` → `get_cala_market_signals` → `compute_external_risk_scores` → `adjust_risk_cone_with_cala` → `compute_risk_opportunity_scores` → `compute_recommendation` → `generate_explanation`.

Why → `get_audit_trail` + `generate_explanation`.
Scenario → `run_scenario` + `generate_explanation`.
Compare → `compare_materials`.
Chart → `generate_chart_payload`.

## API surface

Deterministic (kept):
```
GET  /materials
GET  /materials/{m}/history
GET  /materials/{m}/volatility
GET  /materials/{m}/regime
GET  /materials/{m}/signals
GET  /materials/{m}/risk-cone?horizon_days=180
POST /recommendation
POST /scenario
POST /compare
GET  /recommendations/{id}/audit
```

Agent (new):
```
POST /agent/chat       {message, context:{priority_profile, horizon_days}}
POST /agent/analyze    {material, priority_profile, horizon_days}
```

Response: `{answer, tool_calls, recommendation, chart_payload}`.

## Folder structure (delta from [[architecture-v2]])

```
app/
  agent/
    runtime.py       SDK agent setup + Groq client wiring
    tools.py         @function_tool registrations -> services
    guardrails.py    output validators
    prompts.py       system prompts
  services/
    pricing.py       price history + features
    volatility.py    regime + anomaly
    analogues.py     historical analogues + forward distribution
    cala.py          Cala client + mock + normalization
    recommender.py   scoring + decision + explanation
    scenarios.py     scenario + stress test
  schemas/
    signal.py material.py recommendation.py risk_cone.py audit.py
  api/routes/
    materials.py recommendation.py scenario.py agent.py
data/sample/         barley_prices.csv, sample_cala_barley.json
```

## Reliability

- Cache everything (SQLite + JSON): Cala responses, price history, features, recommendations, chart payloads.
- Pre-canned sample Cala JSONs for offline demo.
- `fallback_full_analysis` runs deterministic chain without LLM — demo-safety net.

## Build order (revised)

See [[mvp-build-order]] revision: deterministic tools first, agent wraps after.

## Related

[[agent-tools]], [[agent-guardrails]], [[architecture-v2]], [[mvp-build-order]], [[decision-engine]], [[Cala-ai]].
