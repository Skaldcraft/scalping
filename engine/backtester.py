"""
engine/backtester.py
====================
Main backtesting loop.

The backtester iterates over every trading session in the requested date
range, for every instrument in the watchlist.  For each session it:

  1. Slices the intraday data to the 9:30–11:00 ET window.
  2. Calculates the opening range from the first N-minute candle.
  3. Computes the 14-day ATR and determines the strategy mode.
  4. Runs the appropriate signal detector.
  5. If a signal is found, resolves the trade bar-by-bar.
  6. Applies circuit-breaker checks after every trade.
  7. Records a SessionSummary regardless of whether a trade was taken.

Outputs a BacktestResult containing all trades and session summaries
for downstream consumption by the journal and dashboard modules.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd

from data.models import (
    OpeningRange, SessionSummary, SignalContext, StrategyMode,
    TradeDirection, TradeResult
)
from data.fetcher import fetch_daily, fetch_intraday_chunked, load_csv
from data.validator import get_session_dates, validate
from engine.session import SessionGate
from engine.opening_range import calculate_opening_range, calculate_atr, is_manipulation_candle
from engine.signals import (
    detect_breakout_signal,
    detect_manipulation_signal,
    detect_mean_reversion_signal,
)
from engine.trade import resolve_trade
from risk.circuit_breaker import CircuitBreaker
from risk.position_sizer import get_current_equity

log = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    instrument_results: Dict[str, List[TradeResult]] = field(default_factory=dict)
    session_summaries:  Dict[str, List[SessionSummary]] = field(default_factory=dict)
    validation_warnings: List[str] = field(default_factory=list)


class Backtester:
    """
    Orchestrates a full backtest run across multiple instruments and
    date ranges according to the parameters in settings.yaml.
    """

    def __init__(self, config: dict):
        self.cfg = config
        self.gate = SessionGate(
            session_start_str=config["session"]["start_time"],
            session_end_str=config["session"]["end_time"],
            tz=config["session"]["timezone"],
        )
        self.or_minutes     = config["opening_range"]["candle_size_minutes"]
        self.atr_period     = config["strategy"]["atr_period"]
        self.manip_threshold = config["strategy"]["manipulation_threshold_pct"]
        self.reward_ratios  = config["strategy"]["reward_ratios"]
        self.risk_pct       = config["account"]["risk_per_trade_pct"]
        self.commission     = config["commissions"]["per_trade_flat"]
        self.starting_capital = config["account"]["starting_capital"]
        self.session_end_time = pd.Timestamp(config["session"]["end_time"]).time()

    # ------------------------------------------------------------------

    def run(self, start_date: date, end_date: date) -> BacktestResult:
        result = BacktestResult()
        instruments = self._build_instrument_list()

        for symbol, source_info in instruments.items():
            log.info("=" * 60)
            log.info("Instrument: %s", symbol)
            log.info("=" * 60)
            try:
                trades, summaries, warnings = self._run_instrument(
                    symbol, source_info, start_date, end_date
                )
                result.instrument_results[symbol] = trades
                result.session_summaries[symbol]  = summaries
                result.validation_warnings.extend(warnings)
            except Exception as exc:
                log.error("[%s] Failed: %s", symbol, exc, exc_info=True)
                result.validation_warnings.append(f"[{symbol}] Error: {exc}")

        return result

    # ------------------------------------------------------------------

    def _build_instrument_list(self) -> dict:
        instruments = {}
        for sym in self.cfg["instruments"].get("equities", []):
            instruments[sym] = {"type": "equity"}
        for sym, path in self.cfg["instruments"].get("forex_csv_files", {}).items():
            instruments[sym] = {"type": "forex", "path": path}
        return instruments

    def _run_instrument(
        self,
        symbol: str,
        source_info: dict,
        start_date: date,
        end_date: date,
    ):
        # ------------------------------------------------------------------
        # 1. Load data
        # ------------------------------------------------------------------
        interval_min = self.or_minutes if self.or_minutes >= 5 else 5
        interval_str = f"{interval_min}m"

        # Add ATR lookback buffer (14 trading days ≈ 20 calendar days)
        atr_buffer = timedelta(days=30)
        data_start  = start_date - atr_buffer

        if source_info["type"] == "equity":
            intraday_df = fetch_intraday_chunked(
                symbol, interval_str, data_start, end_date
            )
            daily_df = fetch_daily(symbol, data_start, end_date)
        else:
            intraday_df = load_csv(source_info["path"], symbol)
            daily_df = self._resample_to_daily(intraday_df)

        intraday_df = intraday_df[
            (intraday_df.index.date >= start_date)
            & (intraday_df.index.date < end_date)
        ]

        # ------------------------------------------------------------------
        # 2. Validate
        # ------------------------------------------------------------------
        warnings = validate(intraday_df, symbol, interval_min)
        for w in warnings:
            log.warning(w)

        # ------------------------------------------------------------------
        # 3. Iterate sessions
        # ------------------------------------------------------------------
        session_dates = get_session_dates(intraday_df)
        log.info("[%s] %d trading sessions to process.", symbol, len(session_dates))

        trades: List[TradeResult]    = []
        summaries: List[SessionSummary] = []

        # Account equity tracks across sessions for risk sizing
        account_equity = self.starting_capital

        # Circuit breaker resets each session
        cb = CircuitBreaker(
            starting_equity=self.starting_capital,
            daily_loss_limit_pct=self.cfg["account"]["daily_loss_limit_pct"],
            profit_factor_floor=self.cfg["risk"]["profit_factor_floor"],
            min_trades_pf=self.cfg["risk"]["min_trades_before_pf_check"],
        )

        for session_date in session_dates:
            session_trades, session_summary = self._run_session(
                symbol=symbol,
                session_date=session_date,
                intraday_df=intraday_df,
                daily_df=daily_df,
                account_equity=account_equity,
                circuit_breaker=cb,
            )

            if session_trades:
                trades.extend(session_trades)
                # Update equity from net P&L (use 2R as primary)
                for t in session_trades:
                    if t.pnl_2r is not None:
                        account_equity += t.pnl_2r
                    cb.record_trade(t)

            summaries.append(session_summary)
            cb.reset_daily(account_equity)

        return trades, summaries, warnings

    # ------------------------------------------------------------------

    def _run_session(
        self,
        symbol: str,
        session_date: str,
        intraday_df: pd.DataFrame,
        daily_df: pd.DataFrame,
        account_equity: float,
        circuit_breaker: "CircuitBreaker",
    ):
        log.debug("Session: %s %s", symbol, session_date)

        rejection_reasons: List[str] = []

        # ------------------------------------------------------------------
        # Circuit breaker check
        # ------------------------------------------------------------------
        if circuit_breaker.is_halted():
            rejection_reasons.append("circuit_breaker_active")
            return [], SessionSummary(
                session_date=session_date,
                instrument=symbol,
                or_high=0, or_low=0, or_midpoint=0, atr_14=0,
                manipulation_flagged=False,
                mode_activated=StrategyMode.NO_TRADE.value,
                breakout_signal_fired=False, retest_confirmed=False,
                pattern_confirmed=False, trade_executed=False,
                rejection_reasons=rejection_reasons,
            )

        # ------------------------------------------------------------------
        # Opening range bars
        # ------------------------------------------------------------------
        or_bars = self.gate.get_opening_range_bars(
            intraday_df, session_date, self.or_minutes
        )
        if or_bars.empty:
            rejection_reasons.append("no_opening_range_bars")
            return [], self._no_trade_summary(symbol, session_date, rejection_reasons)

        opening_range = calculate_opening_range(or_bars, self.or_minutes)
        if opening_range is None:
            rejection_reasons.append("opening_range_invalid")
            return [], self._no_trade_summary(symbol, session_date, rejection_reasons)

        # ------------------------------------------------------------------
        # ATR
        # ------------------------------------------------------------------
        session_ts  = pd.Timestamp(session_date)
        hist_daily  = daily_df[daily_df.index.date < session_ts.date()]
        atr_14      = calculate_atr(hist_daily, self.atr_period)

        if atr_14 is None:
            rejection_reasons.append("insufficient_atr_data")
            return [], self._no_trade_summary(symbol, session_date, rejection_reasons, opening_range)

        atr_threshold      = atr_14 * (self.manip_threshold / 100.0)
        manipulation_flagged = is_manipulation_candle(
            opening_range, atr_14, self.manip_threshold
        )

        # Determine initial manipulation direction from OR bars
        first_bar = or_bars.iloc[0]
        if or_bars.iloc[-1]["close"] > first_bar["open"]:
            initial_spike_direction = TradeDirection.LONG
        else:
            initial_spike_direction = TradeDirection.SHORT

        # ------------------------------------------------------------------
        # Post-opening bars
        # ------------------------------------------------------------------
        post_bars = self.gate.get_post_opening_bars(
            intraday_df, session_date, self.or_minutes
        )
        if post_bars.empty:
            rejection_reasons.append("no_post_opening_bars")
            return [], self._no_trade_summary(
                symbol, session_date, rejection_reasons, opening_range, atr_14, manipulation_flagged
            )

        # ------------------------------------------------------------------
        # Signal detection
        # ------------------------------------------------------------------
        signal: Optional[SignalContext] = None
        mode_activated = StrategyMode.NO_TRADE

        if manipulation_flagged:
            mode_activated = StrategyMode.MANIPULATION
            signal = detect_manipulation_signal(
                post_bars, opening_range, initial_spike_direction, self.session_end_time
            )
            if signal is None:
                rejection_reasons.append("no_manipulation_pattern_found")

        else:
            mode_activated = StrategyMode.BREAKOUT
            signal = detect_breakout_signal(
                post_bars, opening_range, self.session_end_time
            )

            if signal is None:
                # Attempt mean reversion fallback
                mode_activated = StrategyMode.MEAN_REVERSION
                signal = detect_mean_reversion_signal(
                    post_bars, opening_range, initial_spike_direction, self.session_end_time
                )
                if signal is None:
                    rejection_reasons.append("no_signal_found")

        # ------------------------------------------------------------------
        # No signal
        # ------------------------------------------------------------------
        if signal is None:
            return [], SessionSummary(
                session_date=session_date,
                instrument=symbol,
                or_high=opening_range.high,
                or_low=opening_range.low,
                or_midpoint=opening_range.midpoint,
                atr_14=atr_14,
                manipulation_flagged=manipulation_flagged,
                mode_activated=mode_activated.value,
                breakout_signal_fired=False,
                retest_confirmed=False,
                pattern_confirmed=False,
                trade_executed=False,
                rejection_reasons=rejection_reasons,
            )

        # ------------------------------------------------------------------
        # Enrich signal with instrument and ATR data
        # ------------------------------------------------------------------
        signal.instrument    = symbol
        signal.atr_14        = atr_14
        signal.atr_threshold = atr_threshold

        # ------------------------------------------------------------------
        # Resolve trade
        # ------------------------------------------------------------------
        signal_idx = post_bars.index.get_loc(
            post_bars.index[post_bars.index >= signal.signal_time][0]
        ) if signal.signal_time else 0

        remaining_bars = post_bars.iloc[signal_idx:]

        trade = resolve_trade(
            signal=signal,
            remaining_bars=remaining_bars,
            account_equity=account_equity,
            risk_pct=self.risk_pct,
            commission=self.commission,
            instrument=symbol,
            session_end_time=self.session_end_time,
        )

        summary = SessionSummary(
            session_date=session_date,
            instrument=symbol,
            or_high=opening_range.high,
            or_low=opening_range.low,
            or_midpoint=opening_range.midpoint,
            atr_14=atr_14,
            manipulation_flagged=manipulation_flagged,
            mode_activated=mode_activated.value,
            breakout_signal_fired=signal.mode in (StrategyMode.BREAKOUT, StrategyMode.MEAN_REVERSION),
            retest_confirmed=signal.retest_detected,
            pattern_confirmed=bool(signal.pattern_detected),
            trade_executed=True,
            trade_id=trade.trade_id,
            rejection_reasons=[],
        )

        return [trade], summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _no_trade_summary(
        self,
        symbol, session_date, rejection_reasons,
        opening_range=None, atr_14=0.0, manipulation_flagged=False,
    ) -> SessionSummary:
        return SessionSummary(
            session_date=session_date,
            instrument=symbol,
            or_high=opening_range.high if opening_range else 0,
            or_low=opening_range.low   if opening_range else 0,
            or_midpoint=opening_range.midpoint if opening_range else 0,
            atr_14=atr_14,
            manipulation_flagged=manipulation_flagged,
            mode_activated=StrategyMode.NO_TRADE.value,
            breakout_signal_fired=False,
            retest_confirmed=False,
            pattern_confirmed=False,
            trade_executed=False,
            rejection_reasons=rejection_reasons,
        )

    def _resample_to_daily(self, intraday_df: pd.DataFrame) -> pd.DataFrame:
        """Resample intraday bars to daily OHLCV for ATR calculation."""
        daily = intraday_df.resample("1D").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        ).dropna()
        return daily
