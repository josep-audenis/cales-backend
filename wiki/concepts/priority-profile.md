---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [strategy, user-config]
---

# Priority Profile

User strategy selector. Adjusts how [[decision-engine]] weighs upside risk vs downside opportunity vs supply risk vs uncertainty. Does NOT change forecast — changes interpretation.

## Modes

```
aggressive_cost_saving
balanced
risk_averse
supply_security
sustainability
```

## Schema

```python
PRIORITY_PROFILES = {
    "cost_saving": {
        "upside_risk_weight": 0.8,
        "downside_opportunity_weight": 1.3,
        "supply_risk_weight": 0.7,
        "uncertainty_penalty": 0.6
    },
    "risk_averse": {
        "upside_risk_weight": 1.3,
        "downside_opportunity_weight": 0.8,
        "supply_risk_weight": 1.4,
        "uncertainty_penalty": 1.2
    },
    "supply_security": {
        "upside_risk_weight": 1.1,
        "downside_opportunity_weight": 0.7,
        "supply_risk_weight": 1.6,
        "uncertainty_penalty": 1.1
    }
}
```

## Demo value

Same aluminium market:
- `cost_saving` → MONITOR or partial BUY
- `risk_averse` → HEDGE 60 days

Shows decision is not one-size-fits-all. Strong narrative moment.

## Related

[[decision-engine]], [[material-profile]], [[recommendation-actions]].
