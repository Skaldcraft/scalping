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

from data.fetcher import fetch_daily, fetch_intraday_chunked
from engine.opening_range import calculate_atr
from engine.session import SessionGate
from engine.opening_range import calculate_opening_range, is_manipulation_candle
from engine.signals import detect_breakout_signal
from engine.indicators import add_ema, resample_ohlcv

log = logging.getLogger(__name__)


class SelectionDataProvider(Protocol):
    """Interface used by the pre-session selector."""

    def get_atr14(self, symbol: str, as_of_date: date) -> Optional[float]:
        ...

    def get_profit_factor(self, symbol: str, as_of_date: date) -> Optional[float]:
        ...

    def get_spread(self, symbol: str, as_of_date: date) -> Optional[float]:
        ...

    def get_signal_snapshot(self, symbol: str, as_of_date: date) -> dict:
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
        self._signal_cache: dict[tuple[str, date], dict] = {}

        session_cfg = cfg.get("session", {})
        self._session_start = str(session_cfg.get("start_time", "09:30"))
        self._session_end = str(session_cfg.get("end_time", "11:00"))
        self._timezone = str(session_cfg.get("timezone", "America/New_York"))
        self._or_minutes = int(cfg.get("opening_range", {}).get("candle_size_minutes", 15))
        self._manip_threshold = float(cfg.get("strategy", {}).get("manipulation_threshold_pct", 25.0))
        self._dxy_symbol = str(cfg.get("strategy", {}).get("external_bias", {}).get("dxy_symbol", "DX-Y.NYB"))

        mtf_cfg = cfg.get("strategy", {}).get("multi_timeframe", {})
        self._ema_15_fast = int(mtf_cfg.get("ema_15m_fast", 20))
        self._ema_15_slow = int(mtf_cfg.get("ema_15m_slow", 50))

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

    def get_signal_snapshot(self, symbol: str, as_of_date: date) -> dict:
        cache_key = (symbol, as_of_date)
        if cache_key in self._signal_cache:
            return self._signal_cache[cache_key]

        snapshot = {
            "manipulation_status": False,
            "displacement_gap": False,
            "trend_aligned": False,
            "opening_range_valid": False,
            "opening_range_pct_atr": None,
            "spread_atr_ratio": None,
        }

        try:
            atr14 = self.get_atr14(symbol, as_of_date)
            spread = self.get_spread(symbol, as_of_date)

            # Prefer 1m for displacement scan; fallback to 5m if unavailable.
            day_start = as_of_date - timedelta(days=1)
            day_end = as_of_date + timedelta(days=1)

            try:
                intraday_1m = fetch_intraday_chunked(symbol, "1m", day_start, day_end)
            except Exception:
                intraday_1m = fetch_intraday_chunked(symbol, "5m", day_start, day_end)

            gate = SessionGate(self._session_start, self._session_end, self._timezone)
            or_bars = gate.get_opening_range_bars(intraday_1m, str(as_of_date), self._or_minutes)
            post_bars = gate.get_post_opening_bars(intraday_1m, str(as_of_date), self._or_minutes)

            if not or_bars.empty:
                opening_range = calculate_opening_range(or_bars, self._or_minutes)
                if opening_range is not None:
                    snapshot["opening_range_valid"] = True

                    if atr14 and atr14 > 0:
                        pct = (opening_range.candle_range / atr14) * 100.0
                        snapshot["opening_range_pct_atr"] = round(pct, 3)
                        snapshot["manipulation_status"] = is_manipulation_candle(
                            opening_range,
                            atr14,
                            self._manip_threshold,
                        )

                    if spread is not None and atr14 and atr14 > 0:
                        snapshot["spread_atr_ratio"] = round(spread / atr14, 6)

                    if not post_bars.empty:
                        sig = detect_breakout_signal(
                            post_bars,
                            opening_range,
                            pd.Timestamp(self._session_end).time(),
                            require_high_volume_doji=False,
                            allow_displacement_gap_entry=True,
                            entry_priority="gap_first",
                            atr14=atr14 or 0.0,
                        )
                        snapshot["displacement_gap"] = bool(sig and getattr(sig, "displacement_detected", False))

            # Higher-timeframe alignment proxy: 15m and 1h trend agree.
            bars_15 = resample_ohlcv(intraday_1m, "15min")
            bars_1h = resample_ohlcv(intraday_1m, "1h")
            day_15 = bars_15[bars_15.index.date == as_of_date]
            day_1h = bars_1h[bars_1h.index.date == as_of_date]
            if len(day_15) >= self._ema_15_slow and len(day_1h) >= self._ema_15_slow:
                day_15 = add_ema(add_ema(day_15, self._ema_15_fast), self._ema_15_slow)
                day_1h = add_ema(add_ema(day_1h, self._ema_15_fast), self._ema_15_slow)
                last_15 = day_15.iloc[-1]
                last_1h = day_1h.iloc[-1]
                dir_15 = 1 if float(last_15[f"ema_{self._ema_15_fast}"]) > float(last_15[f"ema_{self._ema_15_slow}"]) else -1
                dir_1h = 1 if float(last_1h[f"ema_{self._ema_15_fast}"]) > float(last_1h[f"ema_{self._ema_15_slow}"]) else -1
                snapshot["trend_aligned"] = dir_15 == dir_1h

        except Exception as exc:
            log.debug("[%s] Signal snapshot fallback to defaults: %s", symbol, exc)

        self._signal_cache[cache_key] = snapshot
        return snapshot

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
