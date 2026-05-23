---
type: concept
created: 2026-05-23
updated: 2026-05-23
sources: [planning-architecture-v2]
tags: [agent, tools, contracts]
---

# Agent Tools — Catalog

Full tool registry for [[agent-architecture]]. Signatures + I/O shapes. MVP subset marked **★**.

## A. Data ingestion

### `get_available_materials() -> dict` ★
```json
{"materials": ["barley", "aluminium", "PET", "energy"]}
```

### `get_price_history(material, frequency="weekly") -> dict` ★
```json
{"material":"barley","frequency":"weekly","current_price":210.5,
 "history":[{"date":"2024-01-01","price":205.0}]}
```

### `get_cala_market_signals(material, horizon_days=180) -> dict` ★
```json
{"signals":[{"type":"weather_risk","direction":"bullish",
  "direction_score":0.72,"volatility_impact":0.81,
  "confidence":0.69,"evidence":"...","source":"Cala.ai"}]}
```

### `get_source_registry(material) -> dict`
Required for jury (sources/freshness/reliability/usage).

## B. Price features

### `compute_price_features(material) -> dict`
`return_{1m,3m,6m}`, `moving_average_{1m,3m}`, `trend_slope`, `drawdown_from_1y_high`, `distance_from_1y_low`, `price_percentile_3y`.

### `compute_momentum_signal(material) -> dict`
Normalized `{signal, direction, score, confidence, evidence}`. See [[signal-normalization]].

### `compute_seasonality_signal(material, horizon_days) -> dict`
Barley/energy relevant.

## C. Volatility / regime

### `compute_volatility_regime(material) -> dict` ★
```json
{"volatility_regime":"ELEVATED_VOLATILITY",
 "volatility_percentile":0.73,"volatility_trend":"rising",
 "vol_1m":0.041,"vol_3m":0.063,"vol_6m":0.055,
 "interpretation":"..."}
```

### `classify_market_regime(material) -> dict` ★
Regimes: `LOW_VOL_SIDEWAYS | NORMAL_SIDEWAYS | UPTREND | DOWNTREND | SHOCK_RISK | POST_SHOCK_NORMALIZATION | CHEAP_ACCUMULATION | EXPENSIVE_STRETCHED`.

### `detect_anomalies(material) -> dict`
zscore-flagged spikes.

## D. Quant analogues

### `find_historical_analogues(material, k=25) -> dict` ★
```json
{"similar_periods":[{"date":"2016-04-01","similarity":0.91,
  "regime":"NORMAL_SIDEWAYS","fwd_6m_return":0.08}]}
```

### `build_forward_return_distribution(material, horizon_days=180) -> dict` ★
`median_return`, `p10_return`, `p90_return`, `prob_up_{5,10}pct`, `prob_down_{5,10}pct`.

### `train_event_probability_model(material) -> dict`
Stretch. Classifiers for up/down/vol-spike events.

### `predict_event_probabilities(material, horizon_days) -> dict`
Stretch. Uses trained model.

## E. Cala normalization

### `normalize_cala_signals(raw, material) -> dict` ★
Maps raw Cala → internal [[signal-normalization]] shape.

### `compute_external_risk_scores(material) -> dict` ★
```json
{"bullish_external_score":72,"bearish_external_score":21,
 "volatility_external_score":81,"supply_risk_score":68,
 "main_external_drivers":["weather_risk","geopolitical_risk"]}
```

## F. Risk cone

### `build_base_risk_cone(material, horizon_days=180) -> dict` ★
p10/median/p90 from analogues + current volatility. See [[forecast-corridor]].

### `adjust_risk_cone_with_cala(material, horizon_days=180) -> dict` ★
Bullish Cala → upper widens. Bearish → lower widens. War/supply/weather → whole widens. Confidence-weighted.

### `generate_chart_payload(material, horizon_days) -> dict` ★
`history + base_cone + adjusted_cone + event_markers + current_date_marker`.

## G. Decision

### `compute_risk_opportunity_scores(material, priority_profile) -> dict` ★
`upside_risk`, `downside_opportunity`, `supply_risk`, `uncertainty`, `confidence`.

### `compute_recommendation(material, priority_profile="balanced", horizon_days=180) -> dict` ★
```json
{"action":"HEDGE","recommended_horizon_days":90,"confidence":0.68,
 "risk_score":78,"opportunity_score":39,"summary":"..."}
```
Actions: see [[recommendation-actions]].

### `compute_coverage_suggestion(material, action, risk_score) -> dict`
Phrase as suggested coverage, not financial advice.

### `compare_materials(materials, horizon_days) -> dict`
Ranked list `{material, risk_score, action}`.

## H. Scenario

### `run_scenario(material, shocks, priority_profile="balanced") -> dict`
Shocks: `geopolitical_risk_delta`, `weather_risk_delta`, `oil_price_delta_pct`, `eur_usd_delta_pct`, `volatility_multiplier`.
Returns base vs scenario action + changed drivers.

### `stress_test_material(material) -> dict`
Pre-defined: War / Drought / Energy shock / Demand slowdown / EUR weakness / Supply disruption.

## I. Explanation

### `generate_explanation(recommendation_payload) -> dict` ★
`short_explanation`, `drivers`, `counter_drivers`, `what_to_monitor`.

### `generate_procurement_memo(material, recommendation_id) -> dict`
Exec summary + regime + distribution + recommendation + evidence + monitoring.

### `get_audit_trail(recommendation_id) -> dict` ★
`tools_called`, `data_sources`, `timestamp`. Critical for trust + jury.

## J. Agent control

### `validate_material(material) -> dict` ★
Prevents hallucinated materials.

### `validate_priority_profile(profile) -> dict`
Allowed: `cost_saving | balanced | risk_averse | supply_security | sustainability`. See [[priority-profile]].

### `list_capabilities() -> dict`
Self-description for "what can you do?".

### `fallback_full_analysis(material, priority_profile) -> dict` ★
Runs full deterministic chain without agent. Demo safety net.

## Pydantic contracts

Defined under `app/schemas/`. Key models:

```python
class MarketSignal(BaseModel):
    name: str
    direction: Literal["bullish","bearish","neutral"]
    direction_score: float
    volatility_impact: float
    confidence: float
    source: str
    evidence: list[str]

class Recommendation(BaseModel):
    material: str
    action: Literal["BUY_NOW","WAIT","HEDGE","MONITOR"]
    horizon_days: int
    confidence: float
    risk_score: float
    opportunity_score: float
    top_drivers: list[str]
    counter_drivers: list[str]
```

## Related

[[agent-architecture]], [[agent-guardrails]], [[signal-normalization]], [[recommendation-actions]], [[decision-engine]].
