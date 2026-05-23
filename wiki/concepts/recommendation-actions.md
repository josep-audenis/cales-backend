---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [decision, action]
---

# Recommendation Actions

Four discrete outputs from [[decision-engine]]. Defined by [[smartbuy-brief]].

## Actions

| Action | Meaning | Typical trigger |
|--------|---------|-----------------|
| **BUY NOW** | Lock supply at current price | Forecast up + high confidence + moderate/high upside risk |
| **WAIT** | Defer purchase, expect better price | Forecast flat/down + low supply risk + high opportunity score |
| **HEDGE** | Partial cover via futures/forwards | Forecast up OR external risk high + uncertainty high + material critical/hedgeable |
| **MONITOR** | No action, keep watching | Weak/contradictory/low-confidence signals |

## Action payload

Each recommendation must carry:
- `action` (one of above)
- `horizon_days` (for HEDGE — coverage window suggestion)
- `confidence` (0-100)
- `risk_score` (0-100)
- `opportunity_score` (0-100)
- `forecast_summary` (expected % change + range)
- `main_drivers` (top signals with impact direction + source)
- `explanation` (business-readable rationale)

## Hedgeability matters

Not every material can be hedged. See [[material-profile]] `hedgeable` field. PET = not hedgeable directly. Barley = partial. Aluminium + energy = yes (LME, TTF futures).

If material not hedgeable, HEDGE collapses to BUY NOW or staggered purchase.

## Related

[[decision-engine]], [[material-profile]], [[priority-profile]], [[smartbuy-brief]].
