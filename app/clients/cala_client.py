"""
Cala.ai client. Set CALA_API_KEY + CALA_BASE_URL in .env for live mode.
Falls back to mock data when USE_CALA_MOCK=true (default).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

from app.core.config import settings


class CalaEvent:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.source: str = raw.get("source", "Cala.ai")
        self.material: str = raw["material"]
        self.event_type: str = raw["event_type"]
        self.summary: str = raw.get("summary", "")
        self.direction: str = raw.get("direction", "neutral")
        self.severity: float = float(raw.get("severity", 0.5))
        self.confidence: float = float(raw.get("confidence", 0.5))
        self.horizon_days: int = int(raw.get("horizon_days", 30))
        self.date: date = date.fromisoformat(raw["date"]) if "date" in raw else date.today()


class CalaPricePoint:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.date: date = date.fromisoformat(raw["date"])
        self.price: float = float(raw["price"])


class CalaClient:
    def __init__(self) -> None:
        self._mock = settings.use_cala_mock
        self._base_url = settings.cala_base_url
        self._api_key = settings.cala_api_key

    def get_prices(self, material: str, lookback_days: int = 365) -> list[CalaPricePoint]:
        if self._mock:
            return _mock_prices(material, lookback_days)
        return self._fetch_prices(material, lookback_days)

    def get_events(self, material: str) -> list[CalaEvent]:
        if self._mock:
            return _mock_events(material)
        return self._fetch_events(material)

    def _fetch_prices(self, material: str, lookback_days: int) -> list[CalaPricePoint]:
        with httpx.Client(base_url=self._base_url, headers={"Authorization": f"Bearer {self._api_key}"}) as client:
            r = client.get(f"/v1/prices/{material}", params={"lookback_days": lookback_days})
            r.raise_for_status()
            return [CalaPricePoint(p) for p in r.json()["data"]]

    def _fetch_events(self, material: str) -> list[CalaEvent]:
        with httpx.Client(base_url=self._base_url, headers={"Authorization": f"Bearer {self._api_key}"}) as client:
            r = client.get(f"/v1/events/{material}")
            r.raise_for_status()
            return [CalaEvent(e) for e in r.json()["events"]]


# ---------------------------------------------------------------------------
# Mock data — realistic enough for demo / offline dev
# ---------------------------------------------------------------------------

_MOCK_PRICE_BASES: dict[str, float] = {
    "aluminium": 2200.0,
    "pet": 1050.0,
    "energy": 42.0,
    "barley": 220.0,
}

_MOCK_PRICE_VOLS: dict[str, float] = {
    "aluminium": 0.015,
    "pet": 0.012,
    "energy": 0.025,
    "barley": 0.018,
}


def _mock_prices(material: str, lookback_days: int) -> list[CalaPricePoint]:
    import math
    import random

    random.seed(42)
    base = _MOCK_PRICE_BASES.get(material, 1000.0)
    vol = _MOCK_PRICE_VOLS.get(material, 0.015)
    today = date.today()
    points: list[CalaPricePoint] = []
    price = base
    for i in range(lookback_days, 0, -1):
        d = today - timedelta(days=i)
        shock = random.gauss(0, vol)
        # light seasonal for barley
        if material == "barley":
            seasonal = 0.002 * math.sin(2 * math.pi * d.timetuple().tm_yday / 365)
            shock += seasonal
        price *= 1 + shock
        points.append(CalaPricePoint({"date": d.isoformat(), "price": round(price, 2)}))
    return points


_MOCK_EVENTS_BY_MATERIAL: dict[str, list[dict[str, Any]]] = {
    "aluminium": [
        {
            "material": "aluminium",
            "event_type": "geopolitical_risk",
            "summary": "New sanctions risk on Russian aluminium exports.",
            "direction": "bullish",
            "severity": 0.72,
            "confidence": 0.68,
            "horizon_days": 60,
            "date": (date.today() - timedelta(days=14)).isoformat(),
        },
        {
            "material": "aluminium",
            "event_type": "supply_chain",
            "summary": "Smelter outages in Europe due to energy costs.",
            "direction": "bullish",
            "severity": 0.55,
            "confidence": 0.75,
            "horizon_days": 45,
            "date": (date.today() - timedelta(days=7)).isoformat(),
        },
    ],
    "pet": [
        {
            "material": "pet",
            "event_type": "supply_chain",
            "summary": "Asian PET imports surge; pricing pressure downward.",
            "direction": "bearish",
            "severity": 0.60,
            "confidence": 0.65,
            "horizon_days": 30,
            "date": (date.today() - timedelta(days=10)).isoformat(),
        },
    ],
    "energy": [
        {
            "material": "energy",
            "event_type": "geopolitical_risk",
            "summary": "TTF spot elevated on cold-snap forecast for Central Europe.",
            "direction": "bullish",
            "severity": 0.80,
            "confidence": 0.78,
            "horizon_days": 30,
            "date": (date.today() - timedelta(days=3)).isoformat(),
        },
    ],
    "barley": [
        {
            "material": "barley",
            "event_type": "supply_chain",
            "summary": "Ukraine harvest forecast revised down 8% due to drought.",
            "direction": "bullish",
            "severity": 0.65,
            "confidence": 0.70,
            "horizon_days": 90,
            "date": (date.today() - timedelta(days=5)).isoformat(),
        },
    ],
}


def _mock_events(material: str) -> list[CalaEvent]:
    raw_events = _MOCK_EVENTS_BY_MATERIAL.get(material, [])
    return [CalaEvent(e) for e in raw_events]
