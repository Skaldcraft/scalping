"""
data/validator.py
=================
Lightweight data quality checks applied before any backtesting session.
Issues are returned as a list of human-readable warnings rather than
raising exceptions, allowing the user to decide whether to proceed.
"""

import logging
from typing import List, Tuple

import pandas as pd

log = logging.getLogger(__name__)


def validate(df: pd.DataFrame, symbol: str, interval_minutes: int) -> List[str]:
    """
    Run quality checks on an intraday OHLCV DataFrame.

    Returns a (possibly empty) list of warning strings.
    An empty list means the data passed all checks.
    """
    warnings: List[str] = []

    if df.empty:
        warnings.append(f"[{symbol}] DataFrame is empty.")
        return warnings

    # --- OHLC sanity ---
    bad_ohlc = df[(df["high"] < df["low"]) | (df["open"] <= 0) | (df["close"] <= 0)]
    if not bad_ohlc.empty:
        warnings.append(
            f"[{symbol}] {len(bad_ohlc)} bars with high < low or non-positive prices."
        )

    # --- Gap detection ---
    expected_gap = pd.Timedelta(minutes=interval_minutes)
    diffs = df.index.to_series().diff().dropna()
    # Gaps larger than 2× the expected interval (excludes overnight / weekends)
    large_gaps = diffs[diffs > expected_gap * 2]
    # Filter out gaps that span weekends (> 2 days)
    intraday_gaps = large_gaps[large_gaps < pd.Timedelta(days=2)]
    if not intraday_gaps.empty:
        warnings.append(
            f"[{symbol}] {len(intraday_gaps)} intraday gaps larger than "
            f"{interval_minutes * 2} minutes detected."
        )

    # --- Date range ---
    date_range_days = (df.index[-1] - df.index[0]).days
    if date_range_days < 20:
        warnings.append(
            f"[{symbol}] Only {date_range_days} days of data. "
            "A minimum of 30 trading days is recommended for meaningful results."
        )

    # --- Volume ---
    zero_vol = (df["volume"] == 0).sum()
    if zero_vol > len(df) * 0.5:
        warnings.append(
            f"[{symbol}] More than 50% of bars have zero volume. "
            "Volume-based filters (VWAP, OBV) will be unreliable."
        )

    if not warnings:
        log.debug("[%s] Data validation passed (%d bars).", symbol, len(df))

    return warnings


def filter_market_hours(
    df: pd.DataFrame,
    session_start: str = "09:30",
    session_end: str = "11:30",
    tz: str = "America/New_York",
) -> pd.DataFrame:
    """
    Retain only bars within the trading session window.
    Accepts time strings in 'HH:MM' format (ET by default).
    """
    if df.index.tzinfo is None:
        df = df.copy()
        df.index = df.index.tz_localize(tz)

    mask = (
        (df.index.time >= pd.Timestamp(session_start).time()) &
        (df.index.time <= pd.Timestamp(session_end).time())
    )
    return df[mask]


def get_session_dates(df: pd.DataFrame) -> List[str]:
    """Return a sorted list of unique trading dates present in the DataFrame."""
    return sorted(df.index.normalize().unique().strftime("%Y-%m-%d").tolist())
