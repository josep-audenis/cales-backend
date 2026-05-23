---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2, smartbuy-brief]
tags: [decision, scoring]
---

# Decision Engine

Combines [[forecast-corridor]] + normalized signals ([[signal-normalization]]) + [[material-profile]] + [[priority-profile]] → action from [[recommendation-actions]].

## Scores computed

| Score | Source |
|-------|--------|
| `forecast_pressure` | direction + magnitude of forecast |
| `external_risk` | weighted geo + supply + macro signals |
| `supply_risk` | supply_chain + criticality |
| `opportunity` | downside path + low-supply-risk combo |
| `uncertainty` | forecast band width + signal-confidence spread |
| `confidence` | inverse uncertainty + signal agreement |

## Scoring

```python
def recommend(material, forecast, signals, priority_profile):
    forecast_pressure = compute_forecast_pressure(forecast)
    external_risk     = compute_external_risk(signals)
    supply_risk       = compute_supply_risk(signals)
    opportunity       = compute_downside_opportunity(forecast, signals)
    uncertainty       = compute_uncertainty(forecast, signals)
    confidence        = compute_confidence(forecast, signals)

    adjusted_upside_risk = (
        0.35 * forecast_pressure +
        0.30 * external_risk +
        0.25 * supply_risk +
        0.10 * uncertainty
    )
    adjusted_upside_risk *= priority_profile["upside_risk_weight"]
    supply_risk          *= priority_profile["supply_risk_weight"]
    opportunity          *= priority_profile["downside_opportunity_weight"]

    if adjusted_upside_risk > 75 and uncertainty > 50:
        action = "HEDGE"
    elif adjusted_upside_risk > 70 and confidence > 60:
        action = "BUY_NOW"
    elif opportunity > 65 and supply_risk < 50:
        action = "WAIT"
    else:
        action = "MONITOR"

    return action
```

## Hedge horizon

When action = HEDGE, suggest horizon = weighted avg of contributing signal `horizon_days`, clamped 30-90.

## Explanation engine

Inputs: action + top-N signals by contribution. Output: business-readable rationale citing drivers + sources ([[Cala-ai]] events, [[TimesFM]] forecast, internal momentum). Required by [[smartbuy-brief]] judging criterion "explainability".

## Module decomposition

```
ForecastModel       → median, lower, upper
CalaSignalModel     → normalized directional signals
SeasonalityModel    → seasonal pressure signal
DecisionModel       → action + scores
ExplanationModel    → readable rationale
```

## Related

[[recommendation-actions]], [[forecast-corridor]], [[signal-normalization]], [[material-profile]], [[priority-profile]], [[architecture-v2]].
