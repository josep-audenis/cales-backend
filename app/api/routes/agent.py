from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.analyze_builder import build_analyze_response
from app.agent.runtime import run_agent
from app.agent.ui_agent import run_ui_agent
from app.schemas.analyze_response import AnalyzeResponse
from app.schemas.common import MaterialKey, PriorityProfileKey
from app.schemas.ui_agent import UIAgentRequest, UIAgentResponse

router = APIRouter(prefix="/agent", tags=["agent"])


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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
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


@router.post("/ui", response_model=UIAgentResponse)
async def ui(req: UIAgentRequest) -> UIAgentResponse:
    return await run_ui_agent(req)
