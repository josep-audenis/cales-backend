from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.agent.analyze_builder import build_analyze_response
from app.agent.runtime import run_agent
from app.agent.ui_agent import run_ui_agent
from app.agent.website_report_adapter import make_request_id, to_website_report
from app.core.config import settings
from app.reports import render_executive_pdf
from app.schemas.analyze_response import AnalyzeResponse
from app.schemas.common import MaterialKey, PriorityProfileKey
from app.schemas.ui_agent import UIAgentRequest, UIAgentResponse
from app.schemas.website_report import WebsiteReportResponse

# Process-local cache of generated PDFs keyed by request_id.
_PDF_CACHE: dict[str, tuple[bytes, str]] = {}

router = APIRouter(prefix="/agent", tags=["agent"])
reports_router = APIRouter(prefix="/reports", tags=["reports"])


class ChatContext(BaseModel):
    material: MaterialKey | None = None
    priority_profile: PriorityProfileKey = PriorityProfileKey.BALANCED
    horizon_days: int = Field(default=180, ge=1, le=365)


class ChatRequest(BaseModel):
    message: str
    context: ChatContext = Field(default_factory=ChatContext)


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[dict[str, Any]]


class AnalyzeContext(BaseModel):
    current_date: bool = True
    spot_price: bool = True
    warehouse_fill_pct: float | None = Field(default=None, ge=0, le=100)
    related_news: bool = True
    source_reliability: bool = True


class AnalyzeRequest(BaseModel):
    material: MaterialKey
    horizon_days: int = Field(default=180, ge=1, le=365)
    horizon_label: str | None = None
    priority_profile: PriorityProfileKey = PriorityProfileKey.BALANCED
    requested_at: datetime | None = None
    context: AnalyzeContext = Field(default_factory=AnalyzeContext)
    include_market_drivers: bool = True
    analysis_type: Literal["base_case", "stress_test", "what_if"] = "base_case"


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    ctx = req.context.model_dump(mode="json")
    result = await run_agent(req.message, ctx)
    return ChatResponse(answer=result.answer, tool_calls=result.tool_calls)


async def _run_analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    horizon_str = req.horizon_label or f"{req.horizon_days}d"
    wh = req.context.warehouse_fill_pct
    wh_str = f" Current warehouse fill: {wh}%." if wh is not None else ""
    msg = (
        f"Produce a {req.analysis_type} procurement recommendation for "
        f"{req.material.value} over {horizon_str} ({req.horizon_days} days) "
        f"under the {req.priority_profile.value} profile.{wh_str} "
        "Include action, top drivers with sources, counter-drivers, and what to monitor. "
        "Write the entire response in English."
    )
    ctx = req.model_dump(mode="json")
    result = await run_agent(msg, ctx)
    return build_analyze_response(
        material=req.material.value,
        horizon_days=req.horizon_days,
        horizon_label=horizon_str,
        analysis_type=req.analysis_type,
        requested_at=req.requested_at,
        context_flags=req.context.model_dump(mode="json"),
        include_market_drivers=req.include_market_drivers,
        decision=result.decision,
        signals=result.signals,
        evidence_urls=result.evidence_urls,
        forecast_points=result.forecast_points,
        spot_price=result.spot_price,
        spot_date=result.spot_date,
        tool_calls=result.tool_calls,
        answer_text=result.answer,
    )


@router.post("/analyze", response_model=WebsiteReportResponse)
async def analyze(req: AnalyzeRequest) -> WebsiteReportResponse:
    resp = await _run_analyze(req)
    request_id = make_request_id(req.material.value, resp.generated_at, req.horizon_days)
    pdf_bytes = render_executive_pdf(resp)
    file_name = f"{req.material.value}-executive-report-{resp.generated_at.strftime('%Y-%m-%d')}.pdf"
    _PDF_CACHE[request_id] = (pdf_bytes, file_name)
    base = settings.public_base_url.rstrip("/")
    pdf_url = f"{base}/reports/{request_id}/executive.pdf" if base else f"/reports/{request_id}/executive.pdf"
    return to_website_report(
        resp=resp,
        request_id=request_id,
        pdf_file_name=file_name,
        pdf_url=pdf_url,
        pdf_size_bytes=len(pdf_bytes),
    )


@reports_router.get("/{request_id}/executive.pdf")
async def get_executive_pdf(request_id: str, inline: bool = True) -> Response:
    cached = _PDF_CACHE.get(request_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="report not found")
    pdf_bytes, file_name = cached
    disp = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="{file_name}"'},
    )


@router.post("/analyze/raw", response_model=AnalyzeResponse)
async def analyze_raw(req: AnalyzeRequest) -> AnalyzeResponse:
    return await _run_analyze(req)


@router.post("/analyze/report")
async def analyze_report(req: AnalyzeRequest, inline: bool = False) -> Response:
    resp = await _run_analyze(req)
    pdf = render_executive_pdf(resp)
    filename = f"damm-report-{req.material.value}-{resp.generated_at.strftime('%Y%m%d-%H%M')}.pdf"
    disp = "inline" if inline else "attachment"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="{filename}"'},
    )


@router.post("/ui", response_model=UIAgentResponse)
async def ui(req: UIAgentRequest) -> UIAgentResponse:
    return await run_ui_agent(req)
