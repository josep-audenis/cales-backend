from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import Direction, MaterialKey


class Signal(BaseModel):
    name: str
    direction: Direction
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=100.0)
    horizon_days: int = Field(ge=1)
    source: str
    evidence: list[str] = Field(default_factory=list)
    observed_at: datetime | None = None


class SignalBundle(BaseModel):
    material: MaterialKey
    signals: list[Signal]
