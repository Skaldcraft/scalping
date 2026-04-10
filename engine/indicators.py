

def add_sma(df: pd.DataFrame, period: int, source: str = "close", name: str = None) -> pd.DataFrame:
    """Add a simple moving average (SMA) column to a DataFrame."""
    out = df.copy()
    col = name or f"sma_{period}"
    out[col] = out[source].rolling(window=period, min_periods=period).mean()
    return out

def price_ma_deviation(df: pd.DataFrame, ma_col: str = "sma_20") -> pd.Series:
    """Return the absolute price deviation from the MA (close - MA)."""
    return (df["close"] - df[ma_col]).abs()
from __future__ import annotations

from dataclasses import dataclass
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from data.models import OpeningRange, TradeDirection

def add_sma(df: pd.DataFrame, period: int, source: str = "close", name: str = None) -> pd.DataFrame:
    """Add a simple moving average (SMA) column to a DataFrame."""
    out = df.copy()
    col = name or f"sma_{period}"
    out[col] = out[source].rolling(window=period, min_periods=period).mean()
    return out

                        tp_reversal_level=round(tp_reversal, 6),
    """Return the absolute price deviation from the MA (close - MA)."""
    return (df["close"] - df[ma_col]).abs()

@dataclass
class FibZones:
    cheap_buy_level: float
    expensive_sell_level: float
    midpoint_level: float
    tp_reversal_level: float

                    )
    rng = opening_range.high - opening_range.low
    cheap = opening_range.low + (0.618 * rng)
    expensive = opening_range.low + (0.382 * rng)
    midpoint = opening_range.midpoint
    tp_reversal = opening_range.low + (reversal_tp_level * rng)
    return FibZones(
        cheap_buy_level=round(cheap, 6),
        expensive_sell_level=round(expensive, 6),
        midpoint_level=round(midpoint, 6),
        tp_reversal_level=round(tp_reversal, 6),
    )
    if dxy_1m.empty:
        return "unknown"

    dxy = dxy_1m.loc[:ts]
    if len(dxy) < ema_slow:
        return "unknown"

    dxy = add_ema(add_ema(dxy, ema_fast), ema_slow)
    last = dxy.iloc[-1]
    fast = float(last[f"ema_{ema_fast}"])
    slow = float(last[f"ema_{ema_slow}"])

    if fast > slow:
        return "bullish"
    if fast < slow:
        return "bearish"
    return "neutral"


from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from data.models import OpeningRange, TradeDirection

def add_sma(df: pd.DataFrame, period: int, source: str = "close", name: str = None) -> pd.DataFrame:
    """Add a simple moving average (SMA) column to a DataFrame."""
    out = df.copy()
    col = name or f"sma_{period}"
    out[col] = out[source].rolling(window=period, min_periods=period).mean()
    return out

def price_ma_deviation(df: pd.DataFrame, ma_col: str = "sma_20") -> pd.Series:
    """Return the absolute price deviation from the MA (close - MA)."""
    return (df["close"] - df[ma_col]).abs()

@dataclass
class FibZones:
    cheap_buy_level: float
    expensive_sell_level: float
    midpoint_level: float
    tp_reversal_level: float

def get_fib_zones(opening_range: OpeningRange, reversal_tp_level: float = 0.382) -> FibZones:
    rng = opening_range.high - opening_range.low
    cheap = opening_range.low + (0.618 * rng)
    expensive = opening_range.low + (0.382 * rng)
    midpoint = opening_range.midpoint
    tp_reversal = opening_range.low + (reversal_tp_level * rng)
    return FibZones(
        cheap_buy_level=round(cheap, 6),
        expensive_sell_level=round(expensive, 6),
        midpoint_level=round(midpoint, 6),
        tp_reversal_level=round(tp_reversal, 6),
    )

def dxy_confirms_direction(symbol: str, direction: TradeDirection, dxy_bias: str, pairs: list[str]) -> bool:
    normalised = symbol.strip().upper()
    apply = any(normalised == p.upper() for p in pairs)
    if not apply:
        return True

    if dxy_bias == "unknown" or dxy_bias == "neutral":
        return False

    if direction == TradeDirection.SHORT:
        return dxy_bias == "bullish"
    return dxy_bias == "bearish"
