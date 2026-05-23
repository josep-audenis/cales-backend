# INDEX

Catalog of wiki pages. Updated on every ingest.

## Sources

- [SmartBuy Brief](wiki/sources/smartbuy-brief.md) — Damm × Engineering HUB hackathon participants brief (PDF).
- [Planning Architecture v2](wiki/sources/planning-architecture-v2.md) — planning-AI conversation proposing full backend + frontend design.

## Entities

- [Damm](wiki/entities/Damm.md) — buyer, hackathon host, beverage co.
- [Cala.ai](wiki/entities/Cala-ai.md) — primary market intel provider (prices + geo/news).
- [TimesFM](wiki/entities/TimesFM.md) — primary forecast model (with fallback).
- [Aluminium](wiki/entities/Aluminium.md) — highest-spend material; hedgeable via LME.
- [PET](wiki/entities/PET.md) — vPET + rPET; oil/PTA/MEG driven; not hedgeable.
- [Energy](wiki/entities/Energy.md) — gas + power; criticality 1.00; TTF/OMIP.
- [Barley](wiki/entities/Barley.md) — only material with provided dataset; weather-driven.

## Concepts

- [Recommendation Actions](wiki/concepts/recommendation-actions.md) — buy/wait/hedge/monitor semantics + payload.
- [Signal Normalization](wiki/concepts/signal-normalization.md) — uniform schema for all signals.
- [Forecast Corridor](wiki/concepts/forecast-corridor.md) — median + asymmetric uncertainty band, signal-adjusted.
- [Material Profile](wiki/concepts/material-profile.md) — per-material signal weights + hedgeability + criticality.
- [Priority Profile](wiki/concepts/priority-profile.md) — user strategy modes (cost / risk_averse / supply).
- [Decision Engine](wiki/concepts/decision-engine.md) — scoring → action mapping + explanation.
- [Agent Tools](wiki/concepts/agent-tools.md) — full tool catalog w/ signatures + I/O contracts.
- [Agent Guardrails](wiki/concepts/agent-guardrails.md) — quant/source/recommendation/confidence/fallback rules.
- [Local Price Loader](wiki/concepts/local-price-loader.md) — local CSV/parquet loader; replaces broken Cala price path.
- [Cala Signal Extraction](wiki/concepts/cala-signal-extraction.md) — 5-signal pipeline mining Cala graph: producers / disruption / weather / policy / explanation. UUID cache + proven queries.

## Syntheses

- [Agent Architecture](wiki/syntheses/agent-architecture.md) — **current top-level**: tool-first agent (OpenAI Agents SDK + Groq).
- [Architecture v2](wiki/syntheses/architecture-v2.md) — layers/API/folders (now the tool layer under the agent).
- [MVP Build Order](wiki/syntheses/mvp-build-order.md) — phased roadmap: end-to-end flow first.
