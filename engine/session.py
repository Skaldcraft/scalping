"""
engine/session.py
=================
Session gating logic.

The utility operates exclusively during the first 90–120 minutes of the
New York market open (9:30 AM ET).  This module enforces that boundary
and provides helpers for slicing per-day DataFrames to the correct window.
"""

from datetime import datetime, time
from typing import Optional

import pandas as pd


class SessionGate:
    """
    Filters a DataFrame to the active trading window and tracks whether
    new entries are still permitted.

    Parameters
    ----------
    session_start_str  : Market open time string, default '09:30'.
    session_end_str    : Hard-stop time string for new entries (e.g. '11:00').
    tz                 : Timezone string, default 'America/New_York'.
    """

    def __init__(
        self,
        session_start_str: str = "09:30",
        session_end_str: str   = "11:00",
        tz: str                = "America/New_York",
    ):
        self.session_start: time = pd.Timestamp(session_start_str).time()
        self.session_end: time   = pd.Timestamp(session_end_str).time()
        self.tz = tz

    # ------------------------------------------------------------------

    def slice_session(self, df: pd.DataFrame, session_date: str) -> pd.DataFrame:
        """
        Return only the bars for a specific calendar date that fall
        within [session_start, session_end].

        Parameters
        ----------
        df           : Full intraday DataFrame (multi-day).
        session_date : ISO date string, e.g. '2024-01-15'.
        """
        day = pd.Timestamp(session_date).date()
        mask = (
            (df.index.date == day) &
            (df.index.time >= self.session_start) &
            (df.index.time <= self.session_end)
        )
        return df[mask]

    def is_entry_permitted(self, bar_time: datetime) -> bool:
        """
        Return True if the bar's timestamp is within the entry window.
        New entries are blocked at or after session_end.
        """
        t = bar_time.time() if hasattr(bar_time, "time") else bar_time
        return self.session_start <= t < self.session_end

    def get_opening_range_bars(
        self,
        df: pd.DataFrame,
        session_date: str,
        candle_minutes: int,
    ) -> pd.DataFrame:
        """
        Return the bar(s) that constitute the opening range candle.

        For 5-minute bars, candle_minutes=5 returns the single 9:30 bar.
        For 15-minute bars, candle_minutes=15 returns the single 9:30 bar.
        If the interval doesn't align perfectly, the first N minutes of
        bars are returned and the caller merges them.
        """
        session_bars = self.slice_session(df, session_date)
        if session_bars.empty:
            return session_bars

        open_ts = session_bars.index[0]
        cutoff  = open_ts + pd.Timedelta(minutes=candle_minutes)
        return session_bars[session_bars.index < cutoff]

    def get_post_opening_bars(
        self,
        df: pd.DataFrame,
        session_date: str,
        candle_minutes: int,
    ) -> pd.DataFrame:
        """
        Return bars after the opening range candle through session end.
        These are the bars scanned for breakouts, retests, and patterns.
        """
        session_bars = self.slice_session(df, session_date)
        if session_bars.empty:
            return session_bars

        open_ts  = session_bars.index[0]
        cutoff   = open_ts + pd.Timedelta(minutes=candle_minutes)
        return session_bars[session_bars.index >= cutoff]
