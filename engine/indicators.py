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


def add_ema(df: pd.DataFrame, period: int, source: str = "close", name: str = None) -> pd.DataFrame:
    """Add an exponential moving average (EMA) column to a DataFrame."""
    out = df.copy()
    col = name or f"ema_{period}"
    out[col] = out[source].ewm(span=period, adjust=False).mean()
    return out


def add_atr(df: pd.DataFrame, period: int = 14, name: str = None) -> pd.DataFrame:
    """Add an Average True Range (ATR) column to a DataFrame.

    Requires columns: high, low, close.
    Uses Wilder's smoothing (same as TradingView / MT4).
    """
    out = df.copy()
    col = name or f"atr_{period}"
    high = out["high"]
    low = out["low"]
    prev_close = out["close"].shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out[col] = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
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


def get_dxy_bias(
    dxy_1m: pd.DataFrame,
    ts,
    ema_fast: int = 9,
    ema_slow: int = 21,
) -> str:
    """Return DXY trend bias based on EMA crossover."""
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


# --- Multi-Timeframe Trend Alignment using 20 MA Slope and Retracement ---
def classify_trend_alignment(
    df_1m: pd.DataFrame,
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame,
    ma_col: str = "sma_20",
    price_col: str = "close",
    lookback: int = 50
) -> str:
    """
    Multi-timeframe trend alignment using 20 MA slope and retracement rules.
    - All timeframes (1m, 5m, 15m) must have 20 MA sloping in the same direction.
    - 5m and 15m must not have retracement > 50% for 'Strongly Aligned'.
    - If retracement > 75% on 5m or 15m, return 'Reversal Established'.
    """
    def get_trend_and_retracement(df, ma_col, price_col, lookback):
        if len(df) < lookback:
            return "unknown", None
        ma = df[ma_col].iloc[-lookback:]
        if ma.isnull().any():
            return "unknown", None
        slope = ma.iloc[-1] - ma.iloc[0]
        trend = "up" if slope > 0 else ("down" if slope < 0 else "flat")
        price = df[price_col].iloc[-lookback:]
        if trend == "up":
            last_high = price.max()
            last_low = price[price.idxmax():].min()
            move = last_high - last_low
            retracement = (last_high - price.iloc[-1]) / move if move > 0 else 0
        elif trend == "down":
            last_low = price.min()
            last_high = price[price.idxmin():].max()
            move = last_high - last_low
            retracement = (price.iloc[-1] - last_low) / move if move > 0 else 0
        else:
            retracement = None
        return trend, retracement

    trend_1m, _ = get_trend_and_retracement(df_1m, ma_col, price_col, lookback)
    trend_5m, retr_5m = get_trend_and_retracement(df_5m, ma_col, price_col, lookback)
    trend_15m, retr_15m = get_trend_and_retracement(df_15m, ma_col, price_col, lookback)

    if "unknown" in (trend_1m, trend_5m, trend_15m) or None in (retr_5m, retr_15m):
        return "unknown"

    # All timeframes must agree on trend direction (not flat)
    if trend_1m == trend_5m == trend_15m and trend_1m in ("up", "down"):
        # Check for reversal first (75% rule)
        if retr_5m > 0.75 or retr_15m > 0.75:
            return "Reversal Established"
        # Check for strong alignment (50% rule)
        if retr_5m < 0.5 and retr_15m < 0.5:
            return "Strongly Aligned"
        # Caution zone
        return "Neutral/Caution"
    return "Neutral/Caution"