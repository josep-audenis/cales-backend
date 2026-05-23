"""Adapter: AnalyzeResponse -> WebsiteReportResponse envelope."""

from __future__ import annotations

from app.schemas.analyze_response import AnalyzeResponse
from app.schemas.website_report import (
    ExecutivePdf,
    ReportJson,
    WebsiteEvidence,
    WebsiteExplainability,
    WebsiteMarketContext,
    WebsitePricePath,
    WebsiteReportResponse,
)


def make_request_id(material: str, generated_at, horizon_days: int) -> str:
    return f"{material}-{generated_at.date().isoformat()}-{horizon_days}d"


def to_website_report(
    resp: AnalyzeResponse,
    request_id: str,
    pdf_file_name: str,
    pdf_url: str,
    pdf_size_bytes: int,
) -> WebsiteReportResponse:
    report_json = ReportJson(
        schema_version=resp.schema_version,
        analysis_type=resp.analysis_type,
        material=resp.material,
        generated_at=resp.generated_at,
        horizon_days=resp.horizon_days,
        horizon_label=resp.horizon_label,
        recommendation=resp.recommendation,
        market_context=WebsiteMarketContext(
            current_date=resp.market_context.current_date,
            spot_price=resp.market_context.spot_price,
            warehouse_fill_pct=resp.market_context.warehouse_fill_pct,
        ),
        forecast=resp.forecast,
        price_paths=[
            WebsitePricePath(
                id=p.id,
                label=p.label,
                graph_line_key=p.graph_line_key,
                buyer_impact=p.buyer_impact,
                summary=p.summary,
                expected_change_pct=p.expected_change_pct,
                driver_ids=p.driver_ids,
                evidence_ids=p.evidence_ids,
                graph_points=p.graph_points,
                explainability=WebsiteExplainability(
                    click_title=p.explainability.click_title,
                    plain_language=p.explainability.plain_language,
                    click_evidence_ids=p.explainability.click_evidence_ids,
                ),
            )
            for p in resp.price_paths
        ],
        drivers=resp.drivers,
        evidence=[
            WebsiteEvidence(
                id=e.id,
                source=e.source,
                title=e.title,
                date=e.date,
                reliability=e.reliability,
                url=e.url,
                signal_extracted=e.signal_extracted,
            )
            for e in resp.evidence
        ],
        what_to_monitor=resp.what_to_monitor,
    )

    return WebsiteReportResponse(
        request_id=request_id,
        status="completed",
        material=resp.material,
        generated_at=resp.generated_at,
        report_json=report_json,
        executive_pdf=ExecutivePdf(
            status="ready",
            file_name=pdf_file_name,
            mime_type="application/pdf",
            url=pdf_url,
            size_bytes=pdf_size_bytes,
        ),
    )
