---
type: entity
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief, planning-architecture-v2]
tags: [vendor, data-source]
---

# Cala.ai

Primary market intelligence provider for SmartBuy. Role per [[smartbuy-brief]]: structured raw material price data + may help identify/structure external sources.

## What Cala provides

- Structured commodity prices (frequency TBD — daily/weekly/monthly).
- Geopolitical events.
- Market news.
- Supply chain risk signals.
- Regulatory signals.
- Sector-specific insights.
- Possibly import/export and futures-related context.

## Integration role

Backend treats Cala as primary feed. Cala raw payload normalized into internal signal schema ([[signal-normalization]]) and consumed by [[decision-engine]].

## Example Cala payload

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

## Client location

Planned: `app/clients/cala_client.py` (see [[architecture-v2]]).

## Open questions

- Auth mechanism, rate limits, endpoint surface.
- Push (webhook) vs pull (polling)?
- Event freshness latency.
- Coverage per material (aluminium / PET / energy / barley).

## Related

[[smartbuy-brief]], [[signal-normalization]], [[architecture-v2]], [[Damm]].
