from fastapi import APIRouter

from app.data.ingestion import get_cala_signals, get_price_history
from app.schemas.common import MaterialKey
from app.schemas.signal import Signal, SignalBundle
from app.signals.price_momentum_signal import get_price_momentum_signal
from app.signals.seasonality_signal import get_seasonality_signal

router = APIRouter(prefix="/materials", tags=["signals"])


@router.get("/{material}/signals", response_model=SignalBundle)
def get_signals(material: MaterialKey) -> SignalBundle:
    history = get_price_history(material.value, lookback_days=365)
    prices = [p.price for p in history]

    signals: list[Signal] = []
    signals += get_cala_signals(material.value)
    signals.append(get_price_momentum_signal(prices))
    signals.append(get_seasonality_signal(material.value))

    return SignalBundle(material=material, signals=signals)
