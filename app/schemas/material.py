from pydantic import BaseModel, Field

from app.schemas.common import Hedgeable, MaterialKey


class MaterialWeights(BaseModel):
    forecast_trend: float = 0.0
    price_momentum: float = 0.0
    geopolitical_risk: float = 0.0
    supply_chain: float = 0.0
    seasonality: float = 0.0
    weather: float = 0.0
    energy_pressure: float = 0.0
    oil_derivatives: float = 0.0
    regulation: float = 0.0
    imports: float = 0.0
    storage: float = 0.0
    macro_energy: float = 0.0


class Material(BaseModel):
    key: MaterialKey
    name: str
    unit: str = Field(description="Pricing unit, e.g. USD/t, EUR/MWh")
    hedgeable: Hedgeable
    criticality: float = Field(ge=0.0, le=1.0)
    weights: MaterialWeights


class MaterialList(BaseModel):
    items: list[Material]
