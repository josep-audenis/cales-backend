---
type: entity
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [vendor, data-source, mcp]
mcp_url: https://api.cala.ai/mcp/
mcp_auth_header: X-API-KEY
mcp_tools: [knowledge_search, knowledge_query, entity_search, entity_introspection, retrieve_entity]
mcp_docs: https://docs.cala.ai/integrations/mcp
rest_base: https://api.cala.ai/v1
rest_auth_header: X-API-KEY
rest_endpoints: [POST /knowledge/search, POST /knowledge/query, GET /entities, POST /entities/{id}, GET /entities/{id}/introspection]
prices_via_cala: snapshots_only
---

> **Important (2026-05-23):** Cala has **no live OHLC price endpoint**. `knowledge_query "<material> price history"` does return *sourced, lagged* price-point rows (period / price / unit) — fine for enrichment + UI snippets, not for time-series. Real series still come from [[local-price-loader]] (see `app/clients/local_price_loader.py`). The legacy price-REST path in `app/clients/cala_client.py` will be removed once the loader is wired.

# Cala.ai

Primary market intelligence provider for SmartBuy. Role per [[smartbuy-brief]]: structured raw material price data + may help identify/structure external sources.

## What Cala provides

- Structured commodity prices (frequency TBD — daily/weekly/monthly).
- Geopolitical events.
- Market news.
- Supply chain risk signals.
- Regulatory signals.
- Sector-specific insights.
- Possibly import/export and futures-related context.

## Integration role

Backend treats Cala as primary feed. Cala raw payload normalized into internal signal schema ([[signal-normalization]]) and consumed by [[decision-engine]].

## Example Cala payload

```json
{
  "source": "Cala.ai",
  "material": "aluminium",
  "event_type": "geopolitical_risk",
  "summary": "Supply disruption risk increased due to sanctions...",
  "direction": "bullish",
  "severity": 0.78,
  "confidence": 0.71,
  "horizon_days": 60
}
```

## Client location

Planned: `app/clients/cala_client.py` (see [[architecture-v2]]).

## Entity type cheat sheet (2026-05-23 exploration)

| Cala type | Material match | Rich rels | Best for |
|---|---|---|---|
| `Product` | Aluminium, crude oil, PTA, barley | `MANUFACTURED_BY`, `CREATED_BY`, `OPERATED_BY` | Producer graph |
| `Commodity` (UPPER) | NATURAL GAS, CRUDE OIL, WHEAT | `HAS_UNDERLIER` (futures) | CFTC code anchor |
| `Plant` | Barley | `NATIVE_TO` | Climate exposure |
| `Organization` / `Company` | Norsk Hydro, Glencore, LME | `HAS_PRESENCE_IN`, `HAS_HEADQUARTERS_IN`, `IS_ULTIMATE_PARENT_OF`, `IS_DIRECT_PARENT_OF`, `IS_REGISTERED_IN` | Corp/supply graph |

Avoid: `Industry` (empty for material names), `numerical_observations` on Companies (UK Companies House mortgage rows — not predictive), `Commodity.properties` (only name + cftc code).

## Signal extraction recipe

See [[cala-signal-extraction]] for the full 5-signal pipeline, UUID cache, and proven query patterns.

## Tool ranking for our use case

1. `retrieve_entity` w/ relationships — best explainability (every related entity ships with `properties.sources = [{name, document(URL), date}]`).
2. `knowledge_query` — typed rows when scoped tight (year + region + commodity).
3. `knowledge_search` — narrative + claim→source citation chain (`explainability` → `context.origins.document.url`).
4. `entity_introspection` — one-time schema probe per UUID, cache.

Broad open questions ("aluminium supply disruption risks 2026") → `"too complex"` error. Always scope.

## Open questions

- Auth mechanism, rate limits, endpoint surface (REST works w/ `X-API-KEY`; rate limits unmeasured).
- Push (webhook) vs pull (polling)? Currently pull-only.
- Event freshness latency — sources dated same-day in our test (2026-05-23).
- PET coverage thin as a named entity — use feedstock chain (PTA + MEG + crude oil + naphtha) instead.

## Related

[[smartbuy-brief]], [[signal-normalization]], [[architecture-v2]], [[Damm]], [[cala-signal-extraction]], [[local-price-loader]], [[agent-tools]].
