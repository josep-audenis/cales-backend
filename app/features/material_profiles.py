"""Static material profiles — weights, hedgeability, criticality."""

from __future__ import annotations

from app.schemas.common import Hedgeable, MaterialKey
from app.schemas.material import Material, MaterialWeights

MATERIAL_PROFILES: dict[MaterialKey, Material] = {
    MaterialKey.ALUMINIUM: Material(
        key=MaterialKey.ALUMINIUM,
        name="Aluminium",
        unit="USD/t",
        hedgeable=Hedgeable.YES,
        criticality=0.90,
        weights=MaterialWeights(
            forecast_trend=0.25,
            price_momentum=0.20,
            geopolitical_risk=0.20,
            energy_pressure=0.20,
            seasonality=0.05,
            supply_chain=0.10,
        ),
    ),
    MaterialKey.PET: Material(
        key=MaterialKey.PET,
        name="PET",
        unit="USD/t",
        hedgeable=Hedgeable.NO,
        criticality=0.80,
        weights=MaterialWeights(
            forecast_trend=0.20,
            price_momentum=0.15,
            oil_derivatives=0.25,
            regulation=0.15,
            imports=0.15,
            geopolitical_risk=0.10,
        ),
    ),
    MaterialKey.ENERGY: Material(
        key=MaterialKey.ENERGY,
        name="Energy",
        unit="EUR/MWh",
        hedgeable=Hedgeable.YES,
        criticality=1.00,
        weights=MaterialWeights(
            forecast_trend=0.20,
            price_momentum=0.15,
            geopolitical_risk=0.25,
            weather=0.15,
            storage=0.15,
            seasonality=0.10,
        ),
    ),
    MaterialKey.BARLEY: Material(
        key=MaterialKey.BARLEY,
        name="Barley",
        unit="EUR/t",
        hedgeable=Hedgeable.PARTIAL,
        criticality=0.85,
        weights=MaterialWeights(
            forecast_trend=0.20,
            price_momentum=0.15,
            weather=0.25,
            seasonality=0.20,
            geopolitical_risk=0.10,
            supply_chain=0.10,
        ),
    ),
}


def get_profile(material: MaterialKey) -> Material:
    return MATERIAL_PROFILES[material]
