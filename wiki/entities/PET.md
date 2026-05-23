---
type: entity
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [material, commodity, plastic]
---

# PET

Polyethylene terephthalate. Bottle resin. Two variants in scope:
- **vPET** — virgin.
- **rPET** — recycled.

## Profile

From [[material-profile]]:
- Hedgeable: **False** (no liquid futures market).
- Criticality: 0.80.
- Top weights: oil_derivatives 0.25, forecast_trend 0.20, regulation 0.15, imports 0.15, price_momentum 0.15.

## Key drivers ([[smartbuy-brief]])

- **PTA** (purified terephthalic acid) — feedstock.
- **MEG** (monoethylene glycol) — feedstock.
- **Oil** — upstream of PTA/MEG.
- **ICIS LOR** — price reference series.
- **Imports** from Asia + Turkey.
- **EU recycling regulation** — pushes rPET demand, mandated %.

## Hedge note

Not directly hedgeable. HEDGE action ([[recommendation-actions]]) collapses to BUY NOW or staggered procurement for PET.

## Signals to wire

- Brent / WTI crude.
- PTA + MEG spot.
- ICIS LOR.
- EU regulation tracker (Cala.ai news).
- Asia/Turkey import volumes + freight.

## Related

[[material-profile]], [[smartbuy-brief]], [[signal-normalization]].
