"""ATR (Average True Range) volatility calculation using yfinance."""
from dataclasses import dataclass

import pandas as pd
import yfinance as yf


@dataclass
class VolatilityReading:
    current_range: float
    atr_14: float
    ratio: float            # current_range / atr_14
    interpretation: str     # 'elevated' | 'normal' | 'compressed'


def calculate_atr(ticker: str, period_days: int = 30) -> VolatilityReading | None:
    """
    Pull ~30 calendar days (~21 trading days) so we always have 14 prior bars
    plus the current day for the comparison.
    """
    try:
        data = yf.Ticker(ticker).history(period=f"{period_days}d", interval="1d")
    except Exception:
        return None

    if data is None or len(data) < 15:
        return None

    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    prev_close = close.shift(1)

    # True Range = max(H-L, |H - prev_close|, |L - prev_close|)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    # 14-day ATR (simple rolling mean), excluding today so it's a baseline
    atr_14 = tr.rolling(window=14).mean().iloc[-2]
    current_range = high.iloc[-1] - low.iloc[-1]

    if pd.isna(atr_14) or atr_14 == 0:
        return None

    ratio = float(current_range) / float(atr_14)
    if ratio > 1.5:
        interpretation = "elevated"
    elif ratio < 0.6:
        interpretation = "compressed"
    else:
        interpretation = "normal"

    return VolatilityReading(
        current_range=round(float(current_range), 2),
        atr_14=round(float(atr_14), 2),
        ratio=round(ratio, 2),
        interpretation=interpretation,
    )
