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
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    out[col] = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return out


def price_ma_deviation(df: pd.DataFrame, ma_col: str = "sma_20") -> pd.Series:
    """Return the absolute price deviation from the MA (close - MA)."""
    return (df["close"] - df[ma_col]).abs()


def resample_ohlcv(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample a 1-minute OHLCV DataFrame to a higher timeframe.

    Parameters
    ----------
    df : pd.DataFrame
        Must have a DatetimeIndex and columns: open, high, low, close, volume.
    timeframe : str
        Pandas offset alias, e.g. '5min', '15min', '1h'.
    """
    resampled = df.resample(timeframe).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna()
    return resampled


def to_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a standard OHLCV DataFrame to Heikin-Ashi candles.

    Requires columns: open, high, low, close.
    Returns a new DataFrame with ha_open, ha_high, ha_low, ha_close columns.
    """
    out = df.copy()
    ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ha_open = ha_close.copy()
    ha_open.iloc[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2
    out["ha_open"] = ha_open
    out["ha_close"] = ha_close
    out["ha_high"] = pd.concat([df["high"], ha_open, ha_close], axis=1).max(axis=1)
    out["ha_low"] = pd.concat([df["low"], ha_open, ha_close], axis=1).min(axis=1)
    return out


@dataclass
class FibZones:
    cheap_buy_level: float
    expensive_sell_level: float
    midpoint_level: float
    tp_reversal_level: float


def get_fib_zones(opening_range: OpeningRange, reversal_tp_level: float = 0.382) -> FibZones:
    """Calculate Fibonacci zones from the opening range."""
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


def in_fib_zone(price: float, fib_zones: FibZones, direction: TradeDirection) -> bool:
    """Return True if price is within the relevant Fib zone for the given direction."""
    if direction == TradeDirection.LONG:
        return price <= fib_zones.cheap_buy_level
    if direction == TradeDirection.SHORT:
        return price >= fib_zones.expensive_sell_level
    return False


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
    """Return True if the DXY bias confirms the intended trade direction."""
    normalised = symbol.strip().upper()
    apply = any(normalised == p.upper() for p in pairs)
    if not apply:
        return True
    if dxy_bias == "unknown" or dxy_bias == "neutral":
        return False
    if direction == TradeDirection.SHORT:
        return dxy_bias == "bullish"
    return dxy_bias == "bearish"


def classify_trend_alignment(
    df_1m: pd.DataFrame,
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame,
    ma_col: str = "sma_20",
    price_col: str = "close",
    lookback: int = 50,
) -> str:
    """Multi-timeframe trend alignment using 20 MA slope and retracement rules.

    Returns one of: 'Strongly Aligned', 'Reversal Established',
    'Neutral/Caution', or 'unknown'.
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
            move = last_high - price[price.idxmax():].min()
            retracement = (last_high - price.iloc[-1]) / move if move > 0 else 0
        elif trend == "down":
            last_low = price.min()
            move = price[price.idxmin():].max() - last_low
            retracement = (price.iloc[-1] - last_low) / move if move > 0 else 0
        else:
            retracement = None
        return trend, retracement

    trend_1m, _ = get_trend_and_retracement(df_1m, ma_col, price_col, lookback)
    trend_5m, retr_5m = get_trend_and_retracement(df_5m, ma_col, price_col, lookback)
    trend_15m, retr_15m = get_trend_and_retracement(df_15m, ma_col, price_col, lookback)

    if "unknown" in (trend_1m, trend_5m, trend_15m) or None in (retr_5m, retr_15m):
        return "unknown"

    if trend_1m == trend_5m == trend_15m and trend_1m in ("up", "down"):
        if retr_5m > 0.75 or retr_15m > 0.75:
            return "Reversal Established"
        if retr_5m < 0.5 and retr_15m < 0.5:
            return "Strongly Aligned"
        return "Neutral/Caution"
    return "Neutral/Caution"