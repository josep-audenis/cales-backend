"""Envelope schema for website-facing report response."""

from __future__ import annotations

from datetime import date as _date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analyze_response import (
    AffectedPlace,
    BuyerImpact,
    Driver,
    ForecastBlock,
    GraphLineKey,
    GraphPoint,
    Recommendation,
    SpotPrice,
    WatchItem,
)
from app.schemas.common import MaterialKey


class WebsiteMarketContext(BaseModel):
    current_date: _date
    spot_price: SpotPrice | None = None
    warehouse_fill_pct: float | None = None


class WebsiteExplainability(BaseModel):
    click_title: str
    plain_language: str
    click_evidence_ids: list[str] = Field(default_factory=list)


class WebsitePricePath(BaseModel):
    id: Literal["base_case", "worst_case", "relief_case"]
    label: str
    graph_line_key: GraphLineKey
    buyer_impact: BuyerImpact
    summary: str
    expected_change_pct: float
    driver_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    graph_points: list[GraphPoint]
    explainability: WebsiteExplainability


class WebsiteEvidence(BaseModel):
    id: str
    source: str
    title: str
    date: _date | None = None
    reliability: Literal["high", "medium", "low"]
    url: str = ""
    signal_extracted: str


class ReportJson(BaseModel):
    schema_version: str = "1.0"
    output_type: Literal["website_report"] = "website_report"
    analysis_type: Literal["base_case", "stress_test", "what_if"]
    material: MaterialKey
    generated_at: datetime
    horizon_days: int
    horizon_label: str
    recommendation: Recommendation
    market_context: WebsiteMarketContext
    forecast: ForecastBlock
    price_paths: list[WebsitePricePath]
    drivers: list[Driver]
    evidence: list[WebsiteEvidence]
    what_to_monitor: list[WatchItem]
    affected_places: list[AffectedPlace] = Field(default_factory=list)


class ExecutivePdf(BaseModel):
    status: Literal["ready", "pending", "error"] = "ready"
    file_name: str
    mime_type: str = "application/pdf"
    url: str
    size_bytes: int


class WebsiteReportResponse(BaseModel):
    request_id: str
    status: Literal["completed", "pending", "error"] = "completed"
    material: MaterialKey
    generated_at: datetime
    report_json: ReportJson
    executive_pdf: ExecutivePdf
