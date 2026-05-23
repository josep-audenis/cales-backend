---
type: synthesis
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2, smartbuy-brief]
tags: [mvp, roadmap]
---

# MVP Build Order

End-to-end flow first. No model zoo. Brief explicit: "Prioritize a working end-to-end flow over a broad but superficial solution."

## Phase 1 — MVP (full decision loop)

1. **Cala price ingestion** — `clients/cala_client.py`, mock if API not ready.
2. **Historical + 6-month forecast chart** — [[TimesFM]] OR fallback volatility cone ([[forecast-corridor]]).
3. **Cala geopolitical + supply signal ingestion** — events → normalized ([[signal-normalization]]).
4. **Signal normalization layer** — uniform schema.
5. **Recommendation engine** — [[decision-engine]] with [[material-profile]] + [[priority-profile]].
6. **Explanation output** — top drivers + Cala evidence + horizon.
7. **Frontend decision screen** — market cockpit (selector + card + chart).

End state of Phase 1: jury sees end-to-end demo for at least [[Barley]] (only material with provided dataset).

## Phase 2 — differentiation

8. **Scenario simulator** — `/scenario` endpoint + frontend shock UI.
9. **Event markers on chart** — Cala events overlaid on price.
10. **Material-specific profiles** — wire all four materials ([[Aluminium]], [[PET]], [[Energy]], [[Barley]]).
11. **Backtesting / similar historical episodes** — brief lists this as a deliverable.

## Phase 3 — polish (if time)

12. Driver waterfall chart.
13. Signal table with confidence.
14. Multi-material dashboard.
15. Hedge horizon suggestion logic.

## Order rationale

- Start with [[Barley]] (has data) — validates pipeline offline.
- Mock [[Cala-ai]] from day 0 to unblock dev.
- TimesFM fallback before TimesFM itself — fallback is demo-safety net.
- Scenario simulator = single biggest differentiator vs. typical hackathon dashboards.

## Submission checklist mapping

[[smartbuy-brief]] checklist → MVP phase:
- Run instructions → Phase 1
- Material selector → step 7
- Buy/wait/hedge/monitor → step 5
- Driver + source explanation → step 6
- External data → step 3
- Sources/assumptions documented → wiki + README
- Functional demo → end of Phase 1

## Related

[[architecture-v2]], [[smartbuy-brief]], [[decision-engine]].
