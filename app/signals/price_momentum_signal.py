"""Price momentum signal — derived from recent price history."""

from __future__ import annotations

from app.schemas.common import Direction
from app.schemas.signal import Signal


def get_price_momentum_signal(prices: list[float], short_window: int = 20, long_window: int = 60) -> Signal:
    """
    prices: list of prices sorted ascending (oldest first).
    Returns momentum signal.
    """
    if len(prices) < long_window:
        return Signal(
            name="price_momentum",
            direction=Direction.NEUTRAL,
            score=50.0,
            confidence=30.0,
            horizon_days=30,
            source="Internal",
            evidence=["Insufficient history for momentum calculation."],
        )

    short_avg = sum(prices[-short_window:]) / short_window
    long_avg = sum(prices[-long_window:]) / long_window
    momentum = (short_avg - long_avg) / long_avg

    direction = Direction.BULLISH if momentum > 0.005 else (Direction.BEARISH if momentum < -0.005 else Direction.NEUTRAL)
    score = round(min(abs(momentum) * 1000, 100.0), 1)  # 10% move = 100 score

    # Recent acceleration: last 5 vs previous 5
    accel = 0.0
    if len(prices) >= 10:
        recent5 = sum(prices[-5:]) / 5
        prev5 = sum(prices[-10:-5]) / 5
        accel = (recent5 - prev5) / prev5

    confidence = round(min(50 + abs(accel) * 1000, 90.0), 1)

    return Signal(
        name="price_momentum",
        direction=direction,
        score=score,
        confidence=confidence,
        horizon_days=30,
        source="Internal",
        evidence=[
            f"Short MA {short_avg:.2f} vs long MA {long_avg:.2f} ({momentum:+.2%}).",
            f"5-day acceleration: {accel:+.2%}.",
        ],
    )
