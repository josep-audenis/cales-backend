"""Structured response schema for POST /agent/analyze."""

from __future__ import annotations

from datetime import date as _date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import MaterialKey


PressureDirection = Literal[
    "upward_price_pressure",
    "downward_price_pressure",
    "moderate_upward_price_pressure",
    "moderate_downward_price_pressure",
    "strong_upward_price_pressure",
    "strong_downward_price_pressure",
    "neutral",
]
BuyerImpact = Literal["positive", "negative", "neutral"]
Impact = Literal["high", "medium", "low"]
Reliability = Literal["high", "medium", "low"]
StepType = Literal["evidence", "signal", "market_mechanism", "decision"]
GraphLineKey = Literal["base", "upside", "downside"]


class SpotPrice(BaseModel):
    value: float
    unit: str
    as_of: _date
    source_id: str


class ContextUsed(BaseModel):
    current_date: bool = True
    spot_price: bool = True
    warehouse_fill_pct: bool = True
    related_news: bool = True
    source_reliability: bool = True
    market_drivers: bool = True


class MarketContext(BaseModel):
    current_date: _date
    spot_price: SpotPrice | None = None
    warehouse_fill_pct: float | None = None
    context_used: ContextUsed


class Recommendation(BaseModel):
    action: str
    recommended_horizon_days: int
    confidence: float = Field(ge=0.0, le=1.0)
    risk_score: float
    opportunity_score: float
    summary: str
    decision_rationale: str
    months_to_buy: int | None = None
    current_coverage_months: float | None = None
    target_coverage_months: float | None = None


class ForecastBlock(BaseModel):
    direction: Literal["upward", "downward", "flat"]
    expected_change_pct: float
    range_low_pct: float
    range_high_pct: float
    interpretation: str


class ReasoningStep(BaseModel):
    step: int
    type: StepType
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    driver_ids: list[str] = Field(default_factory=list)


class Driver(BaseModel):
    id: str
    label: str
    direction: PressureDirection
    buyer_impact: BuyerImpact
    impact: Impact
    impact_score: float
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)


class GraphPoint(BaseModel):
    date: _date
    value: float


class Explainability(BaseModel):
    plain_language: str
    click_title: str
    click_evidence_ids: list[str] = Field(default_factory=list)


class PricePath(BaseModel):
    id: Literal["base_case", "worst_case", "relief_case"]
    label: str
    graph_line_key: GraphLineKey
    buyer_impact: BuyerImpact
    direction: PressureDirection
    summary: str
    expected_change_pct: float
    range_low_pct: float
    range_high_pct: float
    driver_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    graph_points: list[GraphPoint]
    explainability: Explainability


class Evidence(BaseModel):
    id: str
    source: str
    title: str
    date: _date | None = None
    reliability: Reliability
    url: str
    signal_extracted: str
    used_for: list[str] = Field(default_factory=list)


class ChangeCondition(BaseModel):
    condition: str
    likely_shift: str
    reason: str
    evidence_to_watch: list[str] = Field(default_factory=list)


class WatchItem(BaseModel):
    item: str
    why: str
    evidence_source_ids: list[str] = Field(default_factory=list)


class DataQuality(BaseModel):
    price_data_available: bool
    warehouse_data_available: bool
    external_news_available: bool
    source_urls_available: bool


class AuditTrail(BaseModel):
    tools_called: list[str] = Field(default_factory=list)
    data_quality: DataQuality


class AnalyzeResponse(BaseModel):
    schema_version: str = "1.0"
    analysis_type: Literal["base_case", "stress_test", "what_if"] = "base_case"
    material: MaterialKey
    generated_at: datetime
    horizon_days: int
    horizon_label: str
    recommendation: Recommendation
    market_context: MarketContext
    forecast: ForecastBlock
    reasoning_chain: list[ReasoningStep]
    drivers: list[Driver]
    price_paths: list[PricePath]
    evidence: list[Evidence]
    what_would_change_the_recommendation: list[ChangeCondition]
    what_to_monitor: list[WatchItem]
    limitations: list[str]
    audit_trail: AuditTrail
