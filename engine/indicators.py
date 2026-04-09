"""
engine/indicators.py
====================
Reusable indicator and filtering helpers for real-time signal qualification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from data.models import OpeningRange, TradeDirection


@dataclass
class FibZones:
    cheap_buy_level: float
    expensive_sell_level: float
    midpoint_level: float
    tp_reversal_level: float


def resample_ohlcv(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = (
        df.resample(interval)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["open", "high", "low", "close"])
    )
    return out


def to_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    ha = pd.DataFrame(index=df.index)
    ha["close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0

    ha_open = [float((df.iloc[0]["open"] + df.iloc[0]["close"]) / 2.0)]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i - 1] + float(ha.iloc[i - 1]["close"])) / 2.0)

    ha["open"] = ha_open
    ha["high"] = pd.concat([ha["open"], ha["close"], df["high"]], axis=1).max(axis=1)
    ha["low"] = pd.concat([ha["open"], ha["close"], df["low"]], axis=1).min(axis=1)
    ha["volume"] = df["volume"]
    return ha


def add_ema(df: pd.DataFrame, period: int, source: str = "close", name: Optional[str] = None) -> pd.DataFrame:
    out = df.copy()
    col = name or f"ema_{period}"
    out[col] = out[source].ewm(span=period, adjust=False).mean()
    return out


def add_atr(df: pd.DataFrame, period: int, name: str = "atr") -> pd.DataFrame:
    out = df.copy()
    prev_close = out["close"].shift(1)
    tr = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out[name] = tr.rolling(period, min_periods=period).mean()
    return out


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


def in_fib_zone(entry_price: float, direction: TradeDirection, zones: FibZones) -> bool:
    if direction == TradeDirection.LONG:
        return entry_price <= zones.cheap_buy_level
    return entry_price >= zones.expensive_sell_level


def has_no_opposite_wick(bar: pd.Series, direction: TradeDirection, tol: float = 1e-9) -> bool:
    body_low = min(float(bar["open"]), float(bar["close"]))
    body_high = max(float(bar["open"]), float(bar["close"]))
    if direction == TradeDirection.LONG:
        return abs(body_low - float(bar["low"])) <= tol
    return abs(float(bar["high"]) - body_high) <= tol


def classify_trend_alignment(
    ts,
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    bars_15m: pd.DataFrame,
    ema_1m_period: int = 100,
    ema_5m_fast: int = 20,
    ema_5m_slow: int = 50,
    ema_15m_fast: int = 20,
    ema_15m_slow: int = 50,
) -> str:
    one = bars_1m.loc[:ts]
    five = bars_5m.loc[:ts]
    fifteen = bars_15m.loc[:ts]

    if len(one) < ema_1m_period or len(five) < ema_5m_slow or len(fifteen) < ema_15m_slow:
        return "unknown"

    one = add_ema(one, ema_1m_period)
    five = add_ema(add_ema(five, ema_5m_fast), ema_5m_slow)
    fifteen = add_ema(add_ema(fifteen, ema_15m_fast), ema_15m_slow)

    one_last = one.iloc[-1]
    five_last = five.iloc[-1]
    fifteen_last = fifteen.iloc[-1]

    bullish = (
        float(one_last["close"]) > float(one_last[f"ema_{ema_1m_period}"])
        and float(five_last[f"ema_{ema_5m_fast}"]) > float(five_last[f"ema_{ema_5m_slow}"])
        and float(fifteen_last[f"ema_{ema_15m_fast}"]) > float(fifteen_last[f"ema_{ema_15m_slow}"])
    )
    bearish = (
        float(one_last["close"]) < float(one_last[f"ema_{ema_1m_period}"])
        and float(five_last[f"ema_{ema_5m_fast}"]) < float(five_last[f"ema_{ema_5m_slow}"])
        and float(fifteen_last[f"ema_{ema_15m_fast}"]) < float(fifteen_last[f"ema_{ema_15m_slow}"])
    )

    if bullish:
        return "bullish"
    if bearish:
        return "bearish"
    return "mixed"


def dxy_bias_at(ts, dxy_1m: pd.DataFrame, ema_fast: int = 20, ema_slow: int = 50) -> str:
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
