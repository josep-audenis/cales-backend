---
type: source
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [planning, architecture, design]
---

# Planning Conversation — Architecture v2

Source: planning-AI conversation, ingested 2026-05-23. Proposes SmartBuy backend + frontend design built on [[smartbuy-brief]].

## Core thesis

> "The forecast is not the final product. The final product is the decision. The forecast corridor is one of the evidences used to justify the decision."

Two outputs:
1. **Forecast view** — historical + 6-month probabilistic corridor.
2. **Decision view** — buy/wait/hedge/monitor + drivers + evidence + horizon.

Chart builds trust. [[decision-engine]] is the star.

## Pitch framing

"Procurement Market Intelligence Engine" — Citadel-like positioning: separate signals from decisions, normalize every signal, combine dynamically, quantify uncertainty, show evidence, simulate shocks.

## 4-layer architecture

```
Layer 1 — Data:     Cala.ai prices + geo/news, Damm data, weather/macro
Layer 2 — Forecast: TimesFM baseline 6-month, lower/upper band
Layer 3 — Signals:  Cala events + internal features → normalized scores
Layer 4 — Decision: weighted, priority-aware, outputs action + horizon + explanation
```

See [[forecast-corridor]], [[signal-normalization]], [[decision-engine]].

## Folder structure proposed

```
app/
  main.py
  api/        routes_materials.py, routes_forecasts.py, routes_signals.py,
              routes_recommendations.py, routes_scenarios.py
  clients/    cala_client.py
  data/       ingestion.py, normalization.py, cache.py
  features/   price_features.py, signal_features.py, material_profiles.py
  forecasting/ timesfm_model.py, fallback_model.py, uncertainty.py
  signals/    geopolitical_signal.py, supply_signal.py, seasonality_signal.py,
              macro_signal.py, weather_signal.py, price_momentum_signal.py
  decision/   scoring.py, recommender.py, explanation.py, scenarios.py
  schemas/    material.py, forecast.py, signal.py, recommendation.py
```

## Cala.ai role

[[Cala-ai]] = primary market intelligence provider. Prices + geopolitical events + market news + supply chain risk + regulatory signals + sector insights + import/export/futures context. Backend normalizes Cala output into internal signal schema ([[signal-normalization]]).

## Forecast engine

Primary: TimesFM ([[TimesFM]]). Inputs historical prices, freq daily/weekly/monthly, horizon 6 months. Outputs median + lower + upper + confidence + direction + expected pct change + uncertainty.

Fallback: moving avg + volatility cone, exp smoothing, Prophet, or LightGBM with lag features. Demo-reliable fallback:

```python
median_forecast = last_price * cumulative_trend
upper = median_forecast * (1 + rolling_volatility * sqrt(horizon))
lower = median_forecast * (1 - rolling_volatility * sqrt(horizon))
```

**Key upgrade**: forecast adjusted by signals, not just historical extrapolation. See [[forecast-corridor]] for asymmetric-band logic.

## Signal engine

Every signal same interface — see [[signal-normalization]]. MVP signals:
1. Price momentum
2. TimesFM forecast trend
3. Cala.ai geopolitical
4. Cala.ai supply/news
5. Seasonality

Later: weather, macro/energy, regulation.

## Material + priority profiles

Per-material signal weights ([[material-profile]]) + user strategy modes ([[priority-profile]]). Same market, different recommendation depending on priority. Demo moment.

## Decision logic

Score → action mapping. See [[decision-engine]].

## API surface

```
GET  /materials
GET  /materials/{material}/forecast?horizon_days=180
GET  /materials/{material}/signals
POST /recommendation     {material, horizon_days, priority_profile}
POST /scenario           {material, priority_profile, shocks}
```

## Frontend screens

1. Market cockpit — selector + recommendation card + forecast chart
2. Drivers — bullish/bearish, contribution waterfall, signal table
3. Evidence — Cala.ai events table
4. Scenario lab — shocks + recompute

Event markers on chart key for differentiation.

## MVP build order

See [[mvp-build-order]].

## Contradictions with brief

- Brief: "not necessarily predict exact price". Planning: heavy TimesFM. Resolution: forecast = evidence, not deliverable.
- Brief lists 4 materials equally. Planning MVP originally dropped energy; user override 2026-05-23 = cover all four.

## Related

[[smartbuy-brief]], [[architecture-v2]], [[mvp-build-order]], [[Cala-ai]], [[TimesFM]], [[decision-engine]].
