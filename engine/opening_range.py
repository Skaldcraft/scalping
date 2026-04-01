"""
engine/opening_range.py
=======================
Calculates the Opening Range (OR) from the first N-minute candle
of the session and derives the Fibonacci 0.5 midpoint used as the
mechanical stop-loss and trade invalidation level.
"""

from typing import Optional
import pandas as pd
from data.models import OpeningRange


def calculate_opening_range(
    bars: pd.DataFrame,
    candle_minutes: int,
) -> Optional[OpeningRange]:
    """
    Derive the Opening Range from one or more bars covering the first
    N minutes of the session.

    If a single bar is passed (interval == candle_minutes) it is used
    directly.  If multiple sub-interval bars are passed (e.g., 1-minute
    bars for a 15-minute opening range), the composite high/low are used.

    Returns None if the bars DataFrame is empty or malformed.
    """
    if bars.empty:
        return None

    high      = float(bars["high"].max())
    low       = float(bars["low"].min())
    midpoint  = round((high + low) / 2, 6)
    candle_range = round(high - low, 6)

    if candle_range <= 0:
        return None

    return OpeningRange(
        high=high,
        low=low,
        midpoint=midpoint,
        candle_range=candle_range,
        candle_size_minutes=candle_minutes,
        open_time=bars.index[0].to_pydatetime(),
        close_time=bars.index[-1].to_pydatetime(),
    )


# ---------------------------------------------------------------------------
# engine/atr_filter.py — inline here to keep related logic together
# ---------------------------------------------------------------------------

"""
ATR Filter
----------
Calculates the 14-day Average True Range and determines whether the
opening candle qualifies as a "manipulation candle" (range ≥ 25% of ATR).

A manipulation candle signals that institutions have engineered a
liquidity event to trap retail traders, and the utility should
anticipate a reversal rather than a continuation.
"""

import logging
import numpy as np

log = logging.getLogger(__name__)


def calculate_atr(daily_df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """
    Compute the Average True Range over `period` daily bars.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)

    Returns None if insufficient data.
    """
    if len(daily_df) < period + 1:
        log.warning(
            "Insufficient daily bars for ATR calculation (%d available, %d required).",
            len(daily_df), period + 1,
        )
        return None

    df = daily_df.copy().tail(period + 1)
    prev_close = df["close"].shift(1)
    tr = pd.DataFrame({
        "hl":  df["high"] - df["low"],
        "hpc": (df["high"] - prev_close).abs(),
        "lpc": (df["low"]  - prev_close).abs(),
    }).max(axis=1)

    return float(tr.iloc[1:].mean())   # skip first NaN row


def is_manipulation_candle(
    opening_range: OpeningRange,
    atr_14: float,
    threshold_pct: float = 25.0,
) -> bool:
    """
    Return True if the opening candle's range is >= threshold_pct% of the
    14-day ATR, classifying it as an institutional manipulation candle.

    The threshold is configurable; 25% is the value specified by ProRealAlgos
    as the 'dead giveaway' level.  Values of 22–23% can also be used but
    carry slightly lower confidence.
    """
    if atr_14 <= 0:
        return False

    threshold = (threshold_pct / 100.0) * atr_14
    result = opening_range.candle_range >= threshold

    log.debug(
        "ATR filter: OR range=%.5f  ATR=%.5f  threshold(%.0f%%)=%.5f  manipulation=%s",
        opening_range.candle_range, atr_14, threshold_pct, threshold, result,
    )
    return result
