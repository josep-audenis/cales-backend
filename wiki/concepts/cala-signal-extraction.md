---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [cala, signals, predictions, explainability]
---

# Cala Signal Extraction

How to mine Cala's knowledge graph for prediction signals + explainability evidence. Output feeds [[signal-normalization]] and [[decision-engine]].

Derived from live API exploration on 2026-05-23 — see [[Cala-ai]] for tool reference.

## Entity-type cheat sheet

| Cala type | Example | Outgoing rels | Incoming rels | Use for |
|---|---|---|---|---|
| `Product` | `Aluminium`, `crude oil`, `PTA`, `barley` | `MANUFACTURED_BY`, `CREATED_BY`, `DESIGNED_BY`, `OPERATED_BY` | — | Producer graph → supply concentration |
| `Commodity` (UPPER) | `NATURAL GAS`, `CRUDE OIL`, `WHEAT` | — | `HAS_UNDERLIER` | CFTC code + futures anchor |
| `Plant` | `Barley` | `NATIVE_TO` | — | Climate/geo exposure |
| `Organization` / `Company` | `Norsk Hydro ASA`, `Glencore PLC`, `LME` | `HAS_PRESENCE_IN`, `HAS_HEADQUARTERS_IN`, `IS_ULTIMATE_PARENT_OF`, `IS_DIRECT_PARENT_OF`, `IS_REGISTERED_IN` | `WORKS_AT`, `MANUFACTURED_BY`, `OPERATED_BY` | Corp/supply graph w/ sourced URLs |
| `GPE` / `Country` | — | (geographic) | — | Geopolitical anchor for producers |

Avoid:
- `Industry` — returns empty for material names.
- `numerical_observations` on Companies — UK Companies House mortgage rows. Not predictive.
- `Commodity.properties` — only `name`, `cftc_commodity_code`. Not a price endpoint.

## Tool ranking (predictions + explainability)

1. **`retrieve_entity` with relationships** — top for explainability. Each related entity arrives with `properties.sources = [{name, document(URL), date}]`. Drop straight into recommendation drivers.
2. **`knowledge_query`** — structured rows. Works when scoped tight (year + region + commodity). Returns typed dicts → forecast-feature ready.
3. **`knowledge_search`** — narrative + `explainability[].references` → resolve via `context[].id` → `context[].origins[].document.url`. Best for end-user explanation.
4. **`entity_introspection`** — schema probe. Run once per UUID, cache.

## Five-signal extraction pipeline per material

```
1. Producer concentration   (supply-risk)
   knowledge_query "<Material>.MANUFACTURED_BY.return(name, country)"
   knowledge_query "<material> manufacturers"           # broader fallback
   → top-3 country share > 60% → bullish supply concentration
   → cross-join HAS_HEADQUARTERS_IN.country w/ geopolitical risk

2. Disruption / chokepoint   (event)
   knowledge_query "<material> supply disruption <year>"
   knowledge_query "<chokepoint> disruption affected commodities"
   → match material in result set → severity from price_change field

3. Weather / yield   (barley, wheat, agri)
   knowledge_query "weather events affecting <crop> harvest <region> <year>"
   → drought/frost/flood/disease → bearish yield → bullish price

4. Policy / regulation
   knowledge_query "<body> <decision-type> <year> affecting <material>"
     (OPEC+, EU CBAM, China tariff, sanctions)

5. Explanation layer (always last)
   knowledge_search "<scoped question — material + region + year>"
   → cite via context[].origins[].document.url
```

## Material → UUID cache

Cache to skip `entity_search` round-trips. Verify periodically.

| MaterialKey | Cala type | UUID |
|---|---|---|
| `aluminium` | Product | `2c446fc9-2426-4f08-89bb-8e0fe9c279d5` |
| `barley` (product) | Product | `b7d8cc09-893d-43fc-8afe-38dce97cb676` |
| `barley` (plant) | Plant | `4cbebdb2-3b48-4bb2-8ab9-ea09f77c7d4d` |
| `crude_oil` (Product) | Product | `da942998-b01b-49fe-a136-2da116c6326e` |
| `crude_oil` (Commodity) | Commodity | `421b2156-4640-57b2-ad41-d3e63908429a` |
| `natural_gas` | Commodity | `17e8b7c6-1db2-5ee2-bb04-16550cebe8d9` |
| `PTA` (PET feedstock) | Product | `b874688d-4489-48e3-ba68-3def390bd8ec` |
| `ethylene_glycol` (PET feedstock) | Product | `62f156ba-2f25-4d25-ae9b-08c0c989fd71` |
| `wheat` | Commodity | `94306a7d-bd22-56e8-b2dd-48c994de76fa` |
| LME (exchange) | Company | `f5cc6e80-65da-4e53-81bc-65fd1b7c2bca` |
| Norsk Hydro ASA | Company | `bb4159c1-3690-47b4-a75e-89cbe07bf692` |
| Glencore PLC | Company | `dfc61b6d-b9e4-4713-87a3-bafdf5022b32` |

## Pitfalls

- Broad open questions → `"too complex"` error. Always scope: year + region + commodity.
- PET as named entity is sparse. Use PTA + MEG + crude-oil Products + `knowledge_search "PET resin price drivers"` for the chain.
- `knowledge_query` price-history rows are sourced/lagged — good for enrichment + UI snippets, NOT OHLC. Real series still come from [[local-price-loader]].
- `entity_search` on a brand (Glencore, Norsk Hydro) returns subsidiaries first — pick the `Organization`/parent `Company` with richest description.

## Proven working queries (2026-05-23)

```
knowledge_query "Aluminium.MANUFACTURED_BY.return(name, country)"        # 3 producers w/ country
knowledge_query "aluminium manufacturers"                                # 16 rows, HQ + size + desc
knowledge_query "companies.industry=aluminium production.location=Europe.limit=5.return(name, employee_count)"
knowledge_query "aluminium price history LME"                            # period/price/unit rows
knowledge_query "futures contracts on aluminium"                         # contract_name, exchange, cftc_code
knowledge_query "weather events affecting barley harvest Europe 2025"    # event, region, impact, year
knowledge_query "Strait of Hormuz disruption affected commodities"       # commodity, price_change, supply_impact
knowledge_query "OPEC+ production decisions 2026 affecting crude oil"

knowledge_search "Latest aluminium price moves and drivers"              # narrative + 11 sourced docs
knowledge_search "PET resin price drivers"                               # PTA/MEG/naphtha chain, 13 sources
knowledge_search "Barley harvest 2025 EU yield forecast"                 # COCERAL/Copa-Cogeca numbers
knowledge_search "Crude oil OPEC production decision"                    # OPEC+ July 2026 outlook, 9 sources
```

## Wiring into the agent

Surface these as **first-class agent moves** (replace generic `knowledge_search` calls):

- `cala_producer_graph(material) -> list[{name, country, source}]` (wraps `retrieve_entity` + `MANUFACTURED_BY`)
- `cala_disruption_scan(material, year) -> list[event]` (knowledge_query on chokepoints)
- `cala_weather_signal(crop, region, year) -> list[event]` (agri only)
- `cala_policy_signal(material, year) -> list[event]`
- `cala_price_snapshot(material) -> list[{period, price, unit, source}]` (enrichment, not OHLC)
- `cala_explanation(scoped_question) -> {narrative, citations[]}` (knowledge_search + resolve citations)

Each tool emits a `Signal` per [[signal-normalization]] with `source="cala"` + `evidence_urls`.

## Related

[[Cala-ai]], [[signal-normalization]], [[agent-tools]], [[agent-architecture]], [[decision-engine]], [[local-price-loader]].
