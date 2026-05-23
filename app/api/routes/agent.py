import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.runtime import run_agent
from app.schemas.common import MaterialKey, PriorityProfileKey

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
    priority_profile: PriorityProfileKey = PriorityProfileKey.BALANCED
    horizon_days: int = Field(default=180, ge=1, le=365)
    horizon_label: str | None = None
    requested_at: datetime | None = None
    context: AnalyzeContext = Field(default_factory=AnalyzeContext)
    include_market_drivers: bool = True
    analysis_type: Literal["base_case"] = "base_case"


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    ctx = req.context.model_dump(mode="json")
    result = await run_agent(req.message, ctx)
    return ChatResponse(answer=result.answer, tool_calls=result.tool_calls)


@router.post("/analyze", response_model=ChatResponse)
async def analyze(req: AnalyzeRequest) -> ChatResponse:
    payload = req.model_dump(mode="json")
    msg = (
        "Generate one base-case procurement recommendation from this JSON input.\n"
        f"{json.dumps(payload, indent=2)}\n"
        "Return action, drivers, counter-drivers, evidence and what to monitor."
    )
    result = await run_agent(msg, payload)
    return ChatResponse(answer=result.answer, tool_calls=result.tool_calls)
