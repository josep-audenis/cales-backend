from enum import Enum


class MaterialKey(str, Enum):
    ALUMINIUM = "aluminium"
    PET = "pet"
    ENERGY = "energy"
    BARLEY = "barley"


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ForecastDirection(str, Enum):
    UPWARD = "upward"
    DOWNWARD = "downward"
    FLAT = "flat"


class Action(str, Enum):
    BUY_NOW = "BUY_NOW"
    WAIT = "WAIT"
    HEDGE = "HEDGE"
    MONITOR = "MONITOR"


class Hedgeable(str, Enum):
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"


class PriorityProfileKey(str, Enum):
    COST_SAVING = "cost_saving"
    BALANCED = "balanced"
    RISK_AVERSE = "risk_averse"
    SUPPLY_SECURITY = "supply_security"
    SUSTAINABILITY = "sustainability"
