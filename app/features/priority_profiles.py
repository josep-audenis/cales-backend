"""Priority profile configs — tune decision engine scoring weights per user strategy."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.common import PriorityProfileKey


@dataclass(frozen=True)
class PriorityProfile:
    upside_risk_weight: float
    downside_opportunity_weight: float
    supply_risk_weight: float
    uncertainty_penalty: float


PRIORITY_PROFILES: dict[PriorityProfileKey, PriorityProfile] = {
    PriorityProfileKey.COST_SAVING: PriorityProfile(
        upside_risk_weight=0.8,
        downside_opportunity_weight=1.3,
        supply_risk_weight=0.7,
        uncertainty_penalty=0.6,
    ),
    PriorityProfileKey.BALANCED: PriorityProfile(
        upside_risk_weight=1.0,
        downside_opportunity_weight=1.0,
        supply_risk_weight=1.0,
        uncertainty_penalty=1.0,
    ),
    PriorityProfileKey.RISK_AVERSE: PriorityProfile(
        upside_risk_weight=1.3,
        downside_opportunity_weight=0.8,
        supply_risk_weight=1.4,
        uncertainty_penalty=1.2,
    ),
    PriorityProfileKey.SUPPLY_SECURITY: PriorityProfile(
        upside_risk_weight=1.1,
        downside_opportunity_weight=0.7,
        supply_risk_weight=1.6,
        uncertainty_penalty=1.1,
    ),
    PriorityProfileKey.SUSTAINABILITY: PriorityProfile(
        upside_risk_weight=1.0,
        downside_opportunity_weight=0.9,
        supply_risk_weight=1.2,
        uncertainty_penalty=1.0,
    ),
}


def get_priority_profile(key: PriorityProfileKey) -> PriorityProfile:
    return PRIORITY_PROFILES[key]
