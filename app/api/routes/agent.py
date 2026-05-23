from typing import Any

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


class AnalyzeRequest(BaseModel):
    material: MaterialKey
    priority_profile: PriorityProfileKey = PriorityProfileKey.BALANCED
    horizon_days: int = Field(default=180, ge=1, le=365)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    ctx = req.context.model_dump(mode="json")
    result = await run_agent(req.message, ctx)
    return ChatResponse(answer=result.answer, tool_calls=result.tool_calls)


@router.post("/analyze", response_model=ChatResponse)
async def analyze(req: AnalyzeRequest) -> ChatResponse:
    msg = (
        f"Give me a procurement recommendation for {req.material.value} "
        f"over {req.horizon_days} days under the {req.priority_profile.value} profile. "
        "Include action, drivers, counter-drivers, evidence and what to monitor."
    )
    result = await run_agent(msg, req.model_dump(mode="json"))
    return ChatResponse(answer=result.answer, tool_calls=result.tool_calls)
