---
type: entity
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [material, commodity]
---

# Aluminium

Highest-spend material for [[Damm]] currently ([[smartbuy-brief]]). Used in cans.

## Profile

From [[material-profile]]:
- Hedgeable: **True** (LME aluminium futures).
- Criticality: 0.90.
- Top weights: forecast_trend 0.25, geopolitical_risk 0.20, energy_pressure 0.20, price_momentum 0.20.

## Key drivers

- LME spot + futures.
- Energy prices (smelting = energy-intensive → high energy_pressure weight).
- Geopolitics (sanctions on producers — e.g., Russia historically).
- Bauxite + alumina upstream.
- China export policy.

## External signal sources to wire

- LME (London Metal Exchange) — futures + COT positions.
- Cala.ai geopolitical events.
- Power prices ([[Energy]] cross-link).
- Industry news (Fastmarkets, Expana — already monitored by Damm).

## Related

[[material-profile]], [[Energy]], [[smartbuy-brief]], [[signal-normalization]].
