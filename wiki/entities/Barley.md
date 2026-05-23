---
type: entity
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [material, commodity, agricultural]
---

# Barley

Brewing grain. Only material with a dataset provided directly by [[Damm]] ([[smartbuy-brief]]: 6-month history).

## Profile

- Hedgeable: **partial** (Euronext malting barley + wheat-as-proxy).
- Criticality: 0.85.
- Top weights: weather 0.25, seasonality 0.20, forecast_trend 0.20, price_momentum 0.15, geopolitical_risk 0.10, supply_chain 0.10.

## Key drivers

- **Weather** — top weight; rainfall, drought, frost in growing regions.
- **Seasonality** — harvest cycle (N hemisphere mid-summer).
- Geopolitics — Ukraine + Russia exports.
- Wheat prices (substitute).
- Freight costs.

## Data note

Only material with provided dataset → MVP-friendly for offline development. Use it to validate [[forecast-corridor]] + [[decision-engine]] before wiring full [[Cala-ai]] feed.

## Signals to wire

- Weather APIs (open-meteo, NOAA) for key growing regions.
- Euronext malting barley futures.
- Wheat futures (substitute).
- Cala.ai supply/news (export bans, harvest reports).

## Related

[[material-profile]], [[smartbuy-brief]], [[mvp-build-order]].
