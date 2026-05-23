from pydantic import BaseModel, Field

from app.schemas.common import Action, Direction, MaterialKey, PriorityProfileKey


class RecommendationRequest(BaseModel):
    material: MaterialKey
    horizon_days: int = Field(default=180, ge=1, le=365)
    priority_profile: PriorityProfileKey = PriorityProfileKey.BALANCED


class Driver(BaseModel):
    signal: str
    direction: Direction
    impact: float = Field(ge=-100.0, le=100.0)
    source: str
    note: str | None = None


class ForecastBrief(BaseModel):
    expected_change_pct: float
    range_low_pct: float
    range_high_pct: float


class Recommendation(BaseModel):
    material: MaterialKey
    priority_profile: PriorityProfileKey
    action: Action
    horizon_days: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    opportunity_score: float = Field(ge=0.0, le=100.0)
    forecast_summary: ForecastBrief
    main_drivers: list[Driver]
    explanation: str
