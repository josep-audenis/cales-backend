---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [signals, schema]
---

# Signal Normalization

Every signal — internal or external — collapsed to single schema. Lets [[decision-engine]] combine heterogeneous inputs.

## Schema

```json
{
  "name": "geopolitical_risk",
  "direction": "bullish | bearish | neutral",
  "score": 0-100,
  "confidence": 0-100,
  "horizon_days": 60,
  "source": "Cala.ai | TimesFM | Internal | ...",
  "evidence": ["text snippet", "..."]
}
```

Fields:
- **direction** — sign of pressure on price.
- **score** — magnitude.
- **confidence** — how much to trust signal.
- **horizon_days** — over what window signal expected to play out.
- **evidence** — human-readable bullets for explainability.

## MVP signals

1. `price_momentum` — internal, recent return + accel.
2. `forecast_trend` — derived from [[TimesFM]] / fallback.
3. `geopolitical_risk` — [[Cala-ai]] events.
4. `supply_chain` — [[Cala-ai]] news.
5. `seasonality` — internal calendar features.

## Later signals

`weather` (esp. [[Barley]]), `macro_energy` (esp. [[PET]], [[Energy]]), `regulation` (esp. PET rPET / EU recycling), `oil_derivatives` (PET), `imports` (PET Asia/Turkey).

## Cala → normalized

Cala payload e.g.:

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

Mapped: severity × 100 → `score`, confidence × 100 → `confidence`, `summary` → `evidence[0]`.

## Related

[[decision-engine]], [[material-profile]], [[Cala-ai]], [[forecast-corridor]].
