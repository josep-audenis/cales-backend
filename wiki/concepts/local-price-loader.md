---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: []
tags: [data, prices, todo]
---

# Local Price Loader

Reads price history from local CSV/parquet under `data/prices/<material>.{csv,parquet}`. Replaces the broken `CalaClient.get_prices` path — [[Cala-ai]] has no price endpoint.

## Status

**Skeleton landed**, not wired. Lives at `app/clients/local_price_loader.py`.

## Wiring TODO

1. Extract / drop price files into `data/prices/` (one per material). Schema: `date,price`.
   - Candidate source: `ordi_data.zip` at repo root.
2. In `app/data/ingestion.py`, swap:
   ```python
   _client = CalaClient()
   ...
   raw = _client.get_prices(material, lookback_days)
   ```
   →
   ```python
   _prices = LocalPriceLoader()
   ...
   raw = _prices.get_prices(material, lookback_days)
   ```
3. Delete `_fetch_prices` + `_mock_prices` from `CalaClient` (price-REST is dead).
4. `CalaClient` becomes news/events-only (or fully delete once everything goes through MCP).

## Why not Cala for prices

Cala MCP tools = `knowledge_search`, `knowledge_query`, `entity_search`, `entity_introspection`, `retrieve_entity`. Knowledge graph, not a market-data API. Demo hit `https://api.cala.ai/v1/prices/barley` → 404 (endpoint never existed; was a placeholder in our mock client).

## Related

[[Cala-ai]], [[agent-architecture]], [[agent-tools]].
