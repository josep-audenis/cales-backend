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
