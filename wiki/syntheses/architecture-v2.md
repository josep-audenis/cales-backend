---
type: synthesis
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [architecture, plan, api]
---

# Architecture v2 — Consolidated Plan

Working synthesis of [[smartbuy-brief]] requirements + [[planning-architecture-v2]] design. This is the build target.

## Product positioning

**Procurement Market Intelligence Engine.** Two surfaces:
1. Forecast corridor (evidence) — see [[forecast-corridor]].
2. Decision card (deliverable) — buy / wait / hedge / monitor + horizon + drivers + explanation. See [[recommendation-actions]].

Chart builds trust. Decision is the star.

## Layers

```
1. Data       — Cala.ai prices + geo/news + Damm + weather/macro
2. Forecast   — TimesFM baseline + signal-adjusted asymmetric band
3. Signals    — normalized direction/score/confidence/horizon
4. Decision   — weighted, priority-aware, action + horizon + rationale
```

Layer responsibilities:
- Layer 1: `app/data/`, `app/clients/cala_client.py`.
- Layer 2: `app/forecasting/` — see [[TimesFM]] + fallback.
- Layer 3: `app/signals/` — schema [[signal-normalization]].
- Layer 4: `app/decision/` — logic [[decision-engine]], config [[material-profile]] + [[priority-profile]].

## API surface

```
GET  /materials                                  list with metadata
GET  /materials/{material}/forecast?horizon_days=180
GET  /materials/{material}/signals
POST /recommendation   {material, horizon_days, priority_profile}
POST /scenario         {material, priority_profile, shocks}
```

Recommendation response payload — see [[recommendation-actions]].

## Folder structure

```
app/
  main.py
  api/         routes_materials, routes_forecasts, routes_signals,
               routes_recommendations, routes_scenarios
  clients/     cala_client.py
  data/        ingestion.py, normalization.py, cache.py
  features/    price_features.py, signal_features.py, material_profiles.py
  forecasting/ timesfm_model.py, fallback_model.py, uncertainty.py
  signals/     geopolitical_signal.py, supply_signal.py, seasonality_signal.py,
               macro_signal.py, weather_signal.py, price_momentum_signal.py
  decision/    scoring.py, recommender.py, explanation.py, scenarios.py
  schemas/     material.py, forecast.py, signal.py, recommendation.py
```

## Frontend screens

1. **Market cockpit** — material + horizon + priority selector, recommendation card, forecast chart with Cala event markers.
2. **Drivers** — bullish/bearish bars, contribution waterfall, signal table.
3. **Evidence** — Cala events: source / date / material / direction / reliability.
4. **Scenario lab** — apply shocks (oil +10%, EUR/USD −5%, geo +20%, weather +15%) → recompute → before/after.

## Material scope

All four ([[Aluminium]], [[PET]], [[Energy]], [[Barley]]) per user direction 2026-05-23. Brief lists all as relevant.

## Build order

See [[mvp-build-order]].

## Risks

- TimesFM fragility → fallback ready.
- Cala API unknowns → mock layer in `app/clients/` for offline dev.
- PET unhedgeable → HEDGE collapses to staggered BUY.
- Barley = only material with provided dataset → start there for validation.

## Related

[[smartbuy-brief]], [[planning-architecture-v2]], [[mvp-build-order]], [[decision-engine]], [[forecast-corridor]].
