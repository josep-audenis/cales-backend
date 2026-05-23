from pydantic import BaseModel, Field

from app.schemas.common import MaterialKey, PriorityProfileKey
from app.schemas.recommendation import Recommendation


class Shock(BaseModel):
    name: str = Field(description="e.g. oil, eur_usd, geopolitical, weather")
    delta_pct: float = Field(description="Relative shock, e.g. +0.10 = +10%")


class ScenarioRequest(BaseModel):
    material: MaterialKey
    priority_profile: PriorityProfileKey = PriorityProfileKey.BALANCED
    horizon_days: int = Field(default=180, ge=1, le=365)
    shocks: list[Shock]


class ScenarioResponse(BaseModel):
    material: MaterialKey
    before: Recommendation
    after: Recommendation
    delta_expected_change_pct: float
    delta_confidence: float
