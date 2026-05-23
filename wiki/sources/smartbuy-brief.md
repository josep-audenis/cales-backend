---
type: source
created: 2026-05-23
updated: 2026-05-23
sources: [smartbuy-brief]
tags: [hackathon, brief, damm, procurement]
---

# SmartBuy Hackathon Brief

Source: `raw/SmartBuy Compras EN.pdf` — Damm × Engineering HUB Hackathon participants briefing.

## Core challenge

Build tool that helps Purchasing decide **buy / wait / hedge / monitor** for key raw materials ([[Aluminium]], [[PET]], [[Energy]], [[Barley]]), combining internal data, structured price data from [[Cala-ai]] and external sources not currently considered.

## Business context

- Purchasing decisions affect cost, margin, availability, supply continuity.
- [[Aluminium]] = highest-spend category currently. All four matter.
- [[Damm]] already monitors Fastmarkets, Expana, OMIP, TTF, ICIS + market forecasts + experience.
- Ambition: detect signals **before they become obvious**. Mimic what large funds/market players use to move earlier.

## Objectives

1. Detect advanced signals anticipating up/down movements.
2. Recommend buy/wait/hedge/monitor (see [[recommendation-actions]]).
3. Indicate hedge horizon where relevant.
4. Combine price + news + regulation + geopolitics + imports + futures + speculative positions.
5. Explainable recommendations backed by evidence.

## Data provided

- Barley dataset, previous 6 months.
- Structured raw material price data from [[Cala-ai]].
- Current reference sources: Fastmarkets, Expana, OMIP, TTF, ICIS (when available/referenced).
- For [[PET]]: vPET and rPET, drivers PTA / MEG / oil / ICIS LOR / Asia-Turkey imports / EU recycling regulation.

## External enrichment expected

Teams expected to search/use: macroeconomics, geopolitics, regulation, imports/exports, freight costs, weather, futures, COT reports, industry news, alternative data. Every external source must be documented: origin, date, frequency, expected reliability, influence on recommendation.

## Deliverables

- Recommendation system (buy/wait/hedge/monitor).
- Risk or opportunity score per material.
- Driver explanation (what pushes price up/down).
- Comparison with similar historical episodes where possible.
- Dashboard/interface: select material → see recommendation + evidence + horizon.
- Code repo + real working demo (not slide-only mockup).

## Rules

- Damm data confidential, hackathon-only use this weekend.
- External sources must be documented.
- GenAI, LLMs, AutoML, APIs, no-code, notebooks, Streamlit, Power BI all allowed.
- Demo must be functional end-to-end.

## Judging criteria

- **Actionability**: supports real business decision.
- **Technical robustness**: analysis, models, optimization logic, evidence.
- **Data usage**: cleaning, integration, external enrichment.
- **Explainability**: justifiable to business user.
- **Working demo**: jury sees end-to-end flow with real/representative data.

One prize per challenge + one overall.

## Key quotes

> "Does the solution need to predict the exact price? Not necessarily. It is more useful to predict trend, risk, opportunity and an explainable recommendation."

> "Can it recommend volume? It would be interesting, but not mandatory. The focus is on timing, hedging, risk and explanation."

> "Build something real, executable and explainable. Prioritize a working end-to-end flow over a broad but superficial solution."

## Submission checklist

- [ ] Repo with clear run instructions
- [ ] Demo allows material selection/analysis
- [ ] Solution recommends buy/wait/hedge/monitor
- [ ] Recommendation includes driver + source explanation
- [ ] External data incorporated beyond provided datasets
- [ ] Sources, assumptions, limitations documented
- [ ] Demo functional (not descriptive-only)

## Open questions

- What exact format/schema does [[Cala-ai]] structured price data ship in?
- Frequency of Cala.ai geo/news intel — push or pull?
- Granularity of barley dataset (daily/weekly, price-only or features)?
- Are futures/COT data accessible programmatically or scraped?

## Related

[[planning-architecture-v2]], [[architecture-v2]], [[mvp-build-order]], [[recommendation-actions]].
