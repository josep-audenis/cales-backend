# LOG

Append-only journal. Each entry: `## [YYYY-MM-DD] <op> | <subject>`.

Parse last 5 entries: `grep "^## \[" LOG.md | tail -5`.

---

## [2026-05-23] init | Scaffolded LLM Wiki structure

Created `CLAUDE.md` (schema), `INDEX.md`, `LOG.md`, `raw/`, `wiki/{sources,entities,concepts,syntheses}/`. Two PDFs pending ingest: `SmartBuy Compras ES.pdf`, `what is hugging face.pdf`.

## [2026-05-23] ingest | SmartBuy Brief + Planning Architecture v2

Ingested `raw/SmartBuy Compras EN.pdf` + planning-AI conversation. Created 2 sources, 5 entities, 6 concepts, 2 syntheses (17 wiki pages total). Material scope confirmed: all four ([[Aluminium]], [[PET]], [[Energy]], [[Barley]]). Architecture target = 4-layer (data → forecast → signals → decision); decision-card is the deliverable, forecast corridor is evidence. INDEX populated.

## [2026-05-23] pivot | Agent architecture (tool-first)

Pivoted top-level execution model from pure deterministic pipeline → agent + tools. Deterministic layers from [[architecture-v2]] become the tool layer. New synthesis [[agent-architecture]], concepts [[agent-tools]] + [[agent-guardrails]]. Stack: OpenAI Agents SDK + Groq free tier (Gemini/Ollama fallback). 32-tool catalog defined; MVP subset marked. `architecture-v2` + `mvp-build-order` updated with supersede / Phase 0 notes. Scaffolded `app/{agent,services,schemas}/` + `/agent/chat`, `/agent/analyze`, deterministic routes (`/materials`, `/recommendation`, `/scenario`, `/compare`). Added `openai-agents`, `pandas`, `numpy` to requirements.

## [2026-05-23] note | LocalPriceLoader skeleton + Cala-is-not-prices

Realized at runtime: [[Cala-ai]] has no price REST endpoint — it's an MCP knowledge graph. Our mock `CalaClient.get_prices` hit `https://api.cala.ai/v1/prices/barley` → 404 when `USE_CALA_MOCK=false`. Landed `LocalPriceLoader` skeleton at `app/clients/local_price_loader.py` reading `data/prices/<material>.{csv,parquet}`. Not wired yet — see [[local-price-loader]] for the 4-step swap. Workaround for demo: `USE_CALA_MOCK=true` in `.env`.

## [2026-05-23] explore | Cala API entity types + best query patterns

Live exploration of Cala REST (`https://api.cala.ai/v1`) for our 4 materials. Mapped entity types → relationships → predictive value. Key findings: `Product` type owns the producer graph (`MANUFACTURED_BY`/`CREATED_BY`/`OPERATED_BY`) — gold for supply-concentration signals + explainability (every related entity ships `properties.sources` w/ URL). `Commodity` (UPPER) type only has `cftc_commodity_code` + `HAS_UNDERLIER` (futures anchor). `Plant.NATIVE_TO` gives climate exposure. Company graph (`HAS_HEADQUARTERS_IN`, `IS_ULTIMATE_PARENT_OF`, etc.) maps supply chain. `Industry` empty for materials; `numerical_observations` on Companies = UK Companies House mortgage rows, useless. Five-signal extraction pipeline + UUID cache + 12 proven queries documented in new [[cala-signal-extraction]] concept. [[Cala-ai]] entity page rewritten w/ REST endpoints + cheat sheet. Note: `knowledge_query "<material> price history"` does return sourced/lagged price-point rows — fine for enrichment, not OHLC.

## [2026-05-23] pivot | Cala MCP wired + recommender decomposed

Connected Cala MCP (`https://api.cala.ai/mcp/`, `X-API-KEY`) via `MCPServerStreamableHttp`. Dropped our `get_cala_market_signals` mock-wrapper — agent now calls Cala's `knowledge_search` / `knowledge_query` / `entity_search` / `entity_introspection` / `retrieve_entity` directly. Decomposed monolithic `compute_recommendation` into agent-orchestratable steps: `get_price_history_tool`, `compute_price_features`, `compute_momentum_signal`, `compute_seasonality_signal_tool`, `build_forecast_summary`, `score_and_decide`. Kept `fallback_full_analysis` as one-shot demo safety net. Tools that accept Cala-shaped `extra_signals` use `function_tool(strict_mode=False)` because Cala's schema-less JSON breaks OpenAI strict mode (per Cala docs). Updated `[[agent-architecture]]` + `[[Cala-ai]]` w/ MCP wiring details.
