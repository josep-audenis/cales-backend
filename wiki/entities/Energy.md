---
type: entity
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [material, commodity, energy]
---

# Energy

Power + gas. Highest criticality material (1.00) per [[material-profile]] — production stops without it.

## Profile

- Hedgeable: **True** (TTF gas futures, power forwards via OMIP).
- Criticality: 1.00.
- Top weights: geopolitical_risk 0.25, forecast_trend 0.20, weather 0.15, storage 0.15, price_momentum 0.15, seasonality 0.10.

## Key drivers

- **TTF** — Dutch Title Transfer Facility, EU gas benchmark.
- **OMIP** — Iberian power exchange.
- Geopolitics (gas supply, sanctions, pipelines).
- Weather (heating/cooling demand).
- Storage levels (EU gas storage %).
- Seasonality (winter premium).

## Reference sources already monitored by Damm

OMIP + TTF + ICIS per [[smartbuy-brief]]. SmartBuy must add: gas storage %, weather forecasts, LNG cargo flows, geopolitical events via [[Cala-ai]].

## Related

[[material-profile]], [[Aluminium]] (energy-intensive smelting), [[smartbuy-brief]].
