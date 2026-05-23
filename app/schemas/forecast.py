from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import ForecastDirection, MaterialKey


class PricePoint(BaseModel):
    date: date
    price: float


class ForecastPoint(BaseModel):
    date: date
    median: float
    lower: float
    upper: float


class ForecastSummary(BaseModel):
    expected_change_pct: float
    range_low_pct: float
    range_high_pct: float
    direction: ForecastDirection
    uncertainty: float = Field(ge=0.0, le=1.0)


class CalaEventMark(BaseModel):
    date: date
    label: str
    direction: str
    source: str = "Cala.ai"


class Forecast(BaseModel):
    material: MaterialKey
    horizon_days: int = Field(ge=1)
    history: list[PricePoint]
    forecast: list[ForecastPoint]
    summary: ForecastSummary
    events: list[CalaEventMark] = Field(default_factory=list)
