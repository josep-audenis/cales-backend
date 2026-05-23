---
type: entity
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [model, forecast]
---

# TimesFM

Time-series foundation model (Google). Primary forecast engine candidate for SmartBuy [[forecast-corridor]].

## Inputs

- Historical material price series.
- Frequency: daily / weekly / monthly (depends on [[Cala-ai]]).
- Horizon: 6 months (180 days).

## Outputs

- Median forecast.
- Lower / upper bound.
- Confidence interval.
- Trend direction.
- Forecasted pct change.
- Forecast uncertainty.

## Risk: hackathon fragility

If TimesFM hard to configure or returns only point forecasts, fallback to volatility cone — see [[forecast-corridor]] fallback block. Hackathons punish fragile deps; fallback non-negotiable.

## Fallback options ranked

1. Moving average + volatility cone (simplest, demo-safe).
2. Exponential smoothing.
3. Prophet.
4. LightGBM / XGBoost with lag features.

## Open questions

- Available checkpoint size / inference latency on free tier?
- License?
- Probabilistic output natively or need wrapper?

## Related

[[forecast-corridor]], [[signal-normalization]], [[planning-architecture-v2]].
