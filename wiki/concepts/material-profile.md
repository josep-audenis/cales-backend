---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [material, weights, config]
---

# Material Profile

Per-material configuration: signal weights + hedgeability + criticality. Lets same signal affect materials differently.

## Schema

```python
MATERIAL_PROFILES = {
    "aluminium": {
        "weights": {
            "forecast_trend": 0.25, "price_momentum": 0.20,
            "geopolitical_risk": 0.20, "energy_pressure": 0.20,
            "seasonality": 0.05, "supply_chain": 0.10
        },
        "hedgeable": True, "criticality": 0.90
    },
    "pet": {
        "weights": {
            "forecast_trend": 0.20, "price_momentum": 0.15,
            "oil_derivatives": 0.25, "regulation": 0.15,
            "imports": 0.15, "geopolitical_risk": 0.10
        },
        "hedgeable": False, "criticality": 0.80
    },
    "energy": {
        "weights": {
            "forecast_trend": 0.20, "price_momentum": 0.15,
            "geopolitical_risk": 0.25, "weather": 0.15,
            "storage": 0.15, "seasonality": 0.10
        },
        "hedgeable": True, "criticality": 1.00
    },
    "barley": {
        "weights": {
            "forecast_trend": 0.20, "price_momentum": 0.15,
            "weather": 0.25, "seasonality": 0.20,
            "geopolitical_risk": 0.10, "supply_chain": 0.10
        },
        "hedgeable": "partial", "criticality": 0.85
    }
}
```

## Fields

- **weights** — per-signal weight, sum ≈ 1.0. Determines signal influence in [[decision-engine]] scoring.
- **hedgeable** — `True | False | "partial"`. Gates HEDGE action ([[recommendation-actions]]).
- **criticality** — supply-continuity importance. Scales supply-risk penalty.

## Why per-material

Geopolitical risk hits [[Energy]] (criticality 1.00, weight 0.25) more than [[Barley]] (weight 0.10). Weather hits [[Barley]] (0.25) far more than [[Aluminium]] (not present). Oil hits [[PET]] (0.25 via oil_derivatives) but not directly aluminium.

## Related

[[Aluminium]], [[PET]], [[Energy]], [[Barley]], [[priority-profile]], [[decision-engine]], [[signal-normalization]].
