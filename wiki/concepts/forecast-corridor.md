---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [forecast, uncertainty]
---

# Forecast Corridor

Median price path + asymmetric uncertainty band over 6-month horizon. Visual evidence behind [[recommendation-actions]] — not the deliverable itself ([[smartbuy-brief]] explicit: exact price prediction not required).

## Components

```
Line 1: historical actual price       (past 6-24 months)
Line 2: predicted median price        (next 6 months)
Band:   lower / upper bound           (uncertainty interval)
Marks:  Cala.ai event annotations     (geo, supply, regulation)
```

## Baseline forecast

Primary: [[TimesFM]] → median + lower + upper.

Fallback (volatility cone):

```python
def build_forecast_band(point_forecast, historical_returns, horizon_step):
    vol = historical_returns.std()
    uncertainty = vol * np.sqrt(horizon_step)
    lower = point_forecast * (1 - 1.96 * uncertainty)
    upper = point_forecast * (1 + 1.96 * uncertainty)
    return lower, upper
```

## Signal-adjusted forecast

Adjust baseline by aggregated external pressure from [[signal-normalization]]:

```python
adjusted_median = baseline_median * (1 + signal_adjustment)
risk_multiplier = 1 + external_risk_score / 100
adjusted_upper  = adjusted_median * (1 + base_uncertainty * risk_multiplier)
adjusted_lower  = adjusted_median * (1 - base_uncertainty * risk_multiplier)
```

`signal_adjustment` = weighted sum of geopolitical + supply + macro + seasonality (weights per [[material-profile]]).

## Asymmetric band

If net external pressure bullish, expand upper > lower (and vice versa):

```python
if net_external_pressure > 0:
    upper = median * (1 + uncertainty * 1.4)
    lower = median * (1 - uncertainty * 0.8)
else:
    upper = median * (1 + uncertainty * 0.8)
    lower = median * (1 - uncertainty * 1.4)
```

Captures skew: tail risk lives on side signals point to.

## Output schema

```json
{
  "material": "aluminium",
  "horizon_days": 180,
  "history": [{"date": "2026-01-01", "price": 100.2}],
  "forecast": [{"date": "2026-06-01", "median": 105.3, "lower": 96.2, "upper": 114.7}],
  "summary": {
    "expected_change_pct": 5.3,
    "range_low_pct": -3.8,
    "range_high_pct": 14.7,
    "direction": "upward",
    "uncertainty": 0.62
  }
}
```

## Related

[[TimesFM]], [[signal-normalization]], [[decision-engine]], [[material-profile]].
