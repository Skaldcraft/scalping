"""
selector/provider.py
====================
Data provider abstraction for pre-session instrument selection.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, Optional

import pandas as pd

from data.fetcher import fetch_daily
from engine.opening_range import calculate_atr

log = logging.getLogger(__name__)


class SelectionDataProvider(Protocol):
    """Interface used by the pre-session selector."""

    def get_atr14(self, symbol: str, as_of_date: date) -> Optional[float]:
        ...

    def get_profit_factor(self, symbol: str, as_of_date: date) -> Optional[float]:
        ...

    def get_spread(self, symbol: str, as_of_date: date) -> Optional[float]:
        ...


class DefaultSelectionProvider:
    """
    Default provider backed by existing project data sources.

    - ATR: Yahoo daily bars via fetch_daily
    - Profit factor: historical trade logs in results/*/trade_log.csv (2R by default)
    - Spread: optional manual overrides from config pre_session.spread_overrides
    """

    def __init__(
        self,
        cfg: dict,
        results_dir: str | Path = "results",
        atr_period: int = 14,
        pf_pnl_column: str = "pnl_2r",
        min_trades_for_pf: int = 10,
        pf_lookback_trades: Optional[int] = None,
    ):
        self.cfg = cfg
        self.results_dir = Path(results_dir)
        self.atr_period = atr_period
        self.pf_pnl_column = pf_pnl_column
        self.min_trades_for_pf = min_trades_for_pf
        self.pf_lookback_trades = pf_lookback_trades
        self._trade_cache: Optional[pd.DataFrame] = None

    def get_atr14(self, symbol: str, as_of_date: date) -> Optional[float]:
        start = as_of_date - timedelta(days=60)
        end = as_of_date + timedelta(days=1)

        try:
            daily_df = fetch_daily(symbol, start, end)
        except Exception as exc:
            log.warning("[%s] ATR fetch failed: %s", symbol, exc)
            return None

        hist_daily = daily_df[daily_df.index.date < as_of_date]
        return calculate_atr(hist_daily, self.atr_period)

    def get_profit_factor(self, symbol: str, as_of_date: date) -> Optional[float]:
        trades = self._load_trade_history(symbol, as_of_date)
        if trades.empty or len(trades) < self.min_trades_for_pf:
            return None

        pnl = pd.to_numeric(trades[self.pf_pnl_column], errors="coerce").dropna()
        if pnl.empty:
            return None

        gross_profit = float(pnl[pnl > 0].sum())
        gross_loss = abs(float(pnl[pnl < 0].sum()))
        if gross_loss <= 0:
            return None

        return round(gross_profit / gross_loss, 6)

    def get_spread(self, symbol: str, as_of_date: date) -> Optional[float]:
        del as_of_date
        spread_map = self.cfg.get("pre_session", {}).get("spread_overrides", {})
        raw = spread_map.get(symbol)
        if raw is None:
            return None

        try:
            return float(raw)
        except (TypeError, ValueError):
            log.warning("[%s] Invalid spread override '%s'", symbol, raw)
            return None

    def _load_trade_history(self, symbol: str, as_of_date: date) -> pd.DataFrame:
        df = self._load_all_trades()
        if df.empty:
            return df

        if "instrument" not in df.columns or "session_date" not in df.columns:
            return pd.DataFrame()

        filtered = df[df["instrument"] == symbol].copy()
        filtered["session_date"] = pd.to_datetime(filtered["session_date"], errors="coerce")
        cutoff = pd.Timestamp(as_of_date)
        filtered = filtered[filtered["session_date"] < cutoff]

        filtered = filtered.sort_values("session_date")
        if self.pf_lookback_trades is not None and self.pf_lookback_trades > 0:
            filtered = filtered.tail(self.pf_lookback_trades)

        if self.pf_pnl_column not in filtered.columns:
            return pd.DataFrame()

        return filtered

    def _load_all_trades(self) -> pd.DataFrame:
        if self._trade_cache is not None:
            return self._trade_cache

        if not self.results_dir.exists():
            self._trade_cache = pd.DataFrame()
            return self._trade_cache

        frames = []
        for trade_file in self.results_dir.glob("*/trade_log.csv"):
            try:
                df = pd.read_csv(trade_file)
                if not df.empty:
                    frames.append(df)
            except Exception as exc:
                log.debug("Skipping unreadable trade log %s: %s", trade_file, exc)

        self._trade_cache = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return self._trade_cache
