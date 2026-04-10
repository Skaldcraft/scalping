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
from engine.indicators import (
    add_atr,
    classify_trend_alignment,
    dxy_bias_at,
    dxy_confirms_direction,
    get_fib_zones,
    in_fib_zone,
    resample_ohlcv,
    to_heikin_ashi,
)
from engine.signals import (
    detect_breakout_signal,
    detect_manipulation_signal,
    detect_mean_reversion_signal,
    detect_mean_reversion_20ma_signal,
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
        self.execution_minutes = int(config.get("strategy", {}).get("execution_timeframe_minutes", 1))
        self.atr_period     = config["strategy"]["atr_period"]
        self.manip_threshold = config["strategy"]["manipulation_threshold_pct"]
        self.reward_ratios  = config["strategy"]["reward_ratios"]
        # Safety lock is intentionally hard-coded as top-level priority.
        self.risk_pct       = 1.0
        self.commission     = config["commissions"]["per_trade_flat"]
        self.starting_capital = config["account"]["starting_capital"]
        self.session_end_time = pd.Timestamp(config["session"]["end_time"]).time()
        trend_mode = config.get("strategy", {}).get("trend_mode", {})
        self.allow_displacement_gap_entry = bool(
            trend_mode.get("allow_displacement_gap_entry", False)
        )
        self.entry_priority = str(trend_mode.get("entry_priority", "retest_first"))
        self.displacement_min_atr_pct = float(
            trend_mode.get("displacement_min_atr_pct", 0.0)
        )
        self.displacement_min_body_pct = float(
            trend_mode.get("displacement_min_body_pct", 0.0)
        )
        self.use_heikin_ashi = bool(config.get("strategy", {}).get("use_heikin_ashi", False))
        self.require_trend_alignment = bool(config.get("strategy", {}).get("require_trend_alignment", True))
        self.use_fib_zone_filter = bool(config.get("strategy", {}).get("fibonacci_zone_filter", True))

        mtf_cfg = config.get("strategy", {}).get("multi_timeframe", {})
        self.mtf_enabled = bool(mtf_cfg.get("enabled", True))
        self.ema_1m_period = int(mtf_cfg.get("ema_1m_period", 100))
        self.ema_5m_fast = int(mtf_cfg.get("ema_5m_fast", 20))
        self.ema_5m_slow = int(mtf_cfg.get("ema_5m_slow", 50))
        self.ema_15m_fast = int(mtf_cfg.get("ema_15m_fast", 20))
        self.ema_15m_slow = int(mtf_cfg.get("ema_15m_slow", 50))
        self.require_ha_no_opposite_wick = bool(
            mtf_cfg.get("require_ha_no_opposite_wick", True)
        )

        ext_cfg = config.get("strategy", {}).get("external_bias", {})
        self.dxy_filter_enabled = bool(ext_cfg.get("dxy_filter_enabled", True))
        self.dxy_symbol = str(ext_cfg.get("dxy_symbol", "DX-Y.NYB"))
        self.dxy_apply_pairs = list(ext_cfg.get("apply_to_pairs", ["EURUSD", "EURUSD=X", "GBPUSD", "GBPUSD=X"]))
        self.dxy_ema_fast = int(ext_cfg.get("ema_fast", 20))
        self.dxy_ema_slow = int(ext_cfg.get("ema_slow", 50))

        dyn_stop = config.get("strategy", {}).get("dynamic_stop", {})
        self.dynamic_stop_enabled = bool(dyn_stop.get("enabled", True))
        self.dynamic_stop_atr_period = int(dyn_stop.get("atr_period_1m", 14))
        self.dynamic_stop_atr_mult = float(dyn_stop.get("atr_multiplier", 1.75))

        rev_cfg = config.get("strategy", {})
        self.reversal_touch_and_turn_tp = bool(rev_cfg.get("reversal_touch_and_turn_tp", True))
        self.reversal_tp_level = float(rev_cfg.get("reversal_tp_level", 0.382))

        partial_cfg = config.get("strategy", {}).get("partial_profit", {})
        self.partial_enabled = bool(partial_cfg.get("enabled", True))
        self.partial_first_scale_ratio = float(partial_cfg.get("first_scale_ratio", 1.0))
        self.partial_first_scale_pct = float(partial_cfg.get("first_scale_pct", 50.0))
        self.partial_move_sl_to_be = bool(partial_cfg.get("move_stop_to_breakeven", True))

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

    def _infer_displacement_filter_rejections(
        self,
        bars: pd.DataFrame,
        opening_range: OpeningRange,
        atr_14: float,
    ) -> List[str]:
        """Infer why displacement candidates were filtered out when no breakout signal was produced."""
        reasons: List[str] = []
        if bars.empty:
            return reasons

        or_high = opening_range.high
        or_low = opening_range.low
        breakout_direction: Optional[TradeDirection] = None
        prev_bar = None
        size_fail = False
        body_fail = False

        def _body_pct(bar: pd.Series) -> float:
            tr = float(bar["high"] - bar["low"])
            if tr <= 0:
                return 0.0
            return abs(float(bar["close"] - bar["open"])) / tr

        for ts, bar in bars.iterrows():
            if ts.time() >= self.session_end_time:
                break

            if breakout_direction is None:
                if min(float(bar["open"]), float(bar["close"])) > or_high:
                    breakout_direction = TradeDirection.LONG
                    prev_bar = bar
                    continue
                if max(float(bar["open"]), float(bar["close"])) < or_low:
                    breakout_direction = TradeDirection.SHORT
                    prev_bar = bar
                    continue

            if breakout_direction is not None and prev_bar is not None:
                is_gap = (
                    float(bar["low"]) > float(prev_bar["high"])
                    if breakout_direction == TradeDirection.LONG
                    else float(bar["high"]) < float(prev_bar["low"])
                )
                if is_gap:
                    if breakout_direction == TradeDirection.LONG:
                        gap_size = float(bar["low"] - prev_bar["high"])
                    else:
                        gap_size = float(prev_bar["low"] - bar["high"])

                    if self.displacement_min_atr_pct > 0 and atr_14 > 0:
                        min_gap = (self.displacement_min_atr_pct / 100.0) * atr_14
                        if gap_size < min_gap:
                            size_fail = True

                    if self.displacement_min_body_pct > 0:
                        if _body_pct(bar) < (self.displacement_min_body_pct / 100.0):
                            body_fail = True

            prev_bar = bar

        if size_fail:
            reasons.append("displacement_gap_min_size_not_met")
        if body_fail:
            reasons.append("displacement_gap_min_body_not_met")
        return reasons

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
        interval_min = self.execution_minutes
        interval_str = f"{interval_min}m"

        # Add ATR lookback buffer (14 trading days ≈ 20 calendar days)
        atr_buffer = timedelta(days=30)
        data_start  = start_date - atr_buffer

        if source_info["type"] == "equity":
            try:
                intraday_df = fetch_intraday_chunked(
                    symbol, interval_str, data_start, end_date
                )
            except Exception as exc:
                if interval_str == "1m":
                    log.warning(
                        "[%s] 1m fetch unavailable for requested range. Falling back to 5m execution bars: %s",
                        symbol,
                        exc,
                    )
                    interval_min = 5
                    interval_str = "5m"
                    intraday_df = fetch_intraday_chunked(
                        symbol, interval_str, data_start, end_date
                    )
                else:
                    raise
            daily_df = fetch_daily(symbol, data_start, end_date)
        else:
            intraday_df = load_csv(source_info["path"], symbol)
            daily_df = self._resample_to_daily(intraday_df)

        intraday_df = intraday_df[
            (intraday_df.index.date >= start_date)
            & (intraday_df.index.date < end_date)
        ]

        bars_5m = resample_ohlcv(intraday_df, "5min")
        bars_15m = resample_ohlcv(intraday_df, "15min")

        dxy_df = pd.DataFrame()
        if self.dxy_filter_enabled:
            try:
                dxy_df = fetch_intraday_chunked(
                    self.dxy_symbol,
                    interval_str,
                    data_start,
                    end_date,
                )
                dxy_df = dxy_df[
                    (dxy_df.index.date >= start_date)
                    & (dxy_df.index.date < end_date)
                ]
            except Exception as exc:
                log.warning("[%s] DXY fetch unavailable (%s): %s", symbol, self.dxy_symbol, exc)
                dxy_df = pd.DataFrame()

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
            daily_loss_limit_pct=5.0,
            profit_factor_floor=self.cfg["risk"]["profit_factor_floor"],
            min_trades_pf=self.cfg["risk"]["min_trades_before_pf_check"],
        )

        for session_date in session_dates:
            session_trades, session_summary = self._run_session(
                symbol=symbol,
                session_date=session_date,
                intraday_df=intraday_df,
                    bars_5m=bars_5m,
                    bars_15m=bars_15m,
                    dxy_df=dxy_df,
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
        bars_5m: pd.DataFrame,
        bars_15m: pd.DataFrame,
        dxy_df: pd.DataFrame,
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
                pattern_confirmed=False,
                trend_aligned=False,
                dxy_filter_confirmed=False,
                trigger_candle="",
                trade_executed=False,
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

        eval_post_bars = to_heikin_ashi(post_bars) if self.use_heikin_ashi else post_bars

        # ------------------------------------------------------------------
        # Signal detection
        # ------------------------------------------------------------------
        signal: Optional[SignalContext] = None
        mode_activated = StrategyMode.NO_TRADE

        if manipulation_flagged:
            mode_activated = StrategyMode.MANIPULATION
            signal = detect_manipulation_signal(
                post_bars,
                opening_range,
                initial_spike_direction,
                self.session_end_time,
                require_full_body_outside=True,
                require_extreme_boundary=True,
            )
            if signal is None:
                rejection_reasons.append("no_manipulation_pattern_found")

        else:
            mode_activated = StrategyMode.BREAKOUT
            signal = detect_breakout_signal(
                post_bars,
                opening_range,
                self.session_end_time,
                eval_bars=eval_post_bars,
                require_high_volume_doji=True,
                require_no_opposite_wick=self.use_heikin_ashi and self.require_ha_no_opposite_wick,
                allow_displacement_gap_entry=self.allow_displacement_gap_entry,
                entry_priority=self.entry_priority,
                displacement_min_atr_pct=self.displacement_min_atr_pct,
                displacement_min_body_pct=self.displacement_min_body_pct,
                atr14=atr_14,
            )

            if signal is None:
                # Attempt mean reversion fallback (standard)
                mode_activated = StrategyMode.MEAN_REVERSION
                signal = detect_mean_reversion_signal(
                    post_bars, opening_range, initial_spike_direction, self.session_end_time
                )
                # If still no signal, try 20 MA mean reversion for QQQ and GC=F
                if signal is None and symbol in ("QQQ", "GC=F"):
                    signal = detect_mean_reversion_20ma_signal(
                        post_bars,
                        opening_range,
                        self.session_end_time,
                        deviation_threshold=0.5,  # 0.5% deviation
                        retracement_levels=[0.25, 0.5, 0.75],
                        risk_pct=self.risk_pct,
                        instrument=symbol,
                    )
                if signal is None:
                    rejection_reasons.append("no_signal_found")
                    if self.allow_displacement_gap_entry:
                        rejection_reasons.extend(
                            self._infer_displacement_filter_rejections(
                                post_bars,
                                opening_range,
                                atr_14,
                            )
                        )

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
                trend_aligned=False,
                dxy_filter_confirmed=False,
                trigger_candle="",
                trade_executed=False,
                rejection_reasons=rejection_reasons,
            )

        # ------------------------------------------------------------------
        # Multi-timeframe trend alignment and DXY filter
        # ------------------------------------------------------------------
        trend_state = classify_trend_alignment(
            signal.signal_time,
            intraday_df,
            bars_5m,
            bars_15m,
            ema_1m_period=self.ema_1m_period,
            ema_5m_fast=self.ema_5m_fast,
            ema_5m_slow=self.ema_5m_slow,
            ema_15m_fast=self.ema_15m_fast,
            ema_15m_slow=self.ema_15m_slow,
        ) if self.mtf_enabled else "unknown"

        signal.trend_aligned = (
            (signal.direction == TradeDirection.LONG and trend_state == "bullish")
            or (signal.direction == TradeDirection.SHORT and trend_state == "bearish")
        ) if self.mtf_enabled else True

        if self.require_trend_alignment and not signal.trend_aligned:
            rejection_reasons.append(f"trend_not_aligned:{trend_state}")
            return [], SessionSummary(
                session_date=session_date,
                instrument=symbol,
                or_high=opening_range.high,
                or_low=opening_range.low,
                or_midpoint=opening_range.midpoint,
                atr_14=atr_14,
                manipulation_flagged=manipulation_flagged,
                mode_activated=mode_activated.value,
                breakout_signal_fired=True,
                retest_confirmed=signal.retest_detected,
                pattern_confirmed=bool(signal.pattern_detected),
                trend_aligned=False,
                dxy_filter_confirmed=False,
                trigger_candle=signal.trigger_candle or "",
                trade_executed=False,
                rejection_reasons=rejection_reasons,
            )

        dxy_bias = dxy_bias_at(
            signal.signal_time,
            dxy_df,
            ema_fast=self.dxy_ema_fast,
            ema_slow=self.dxy_ema_slow,
        ) if self.dxy_filter_enabled else "unknown"

        signal.dxy_bias = dxy_bias
        signal.dxy_filter_confirmed = dxy_confirms_direction(
            symbol,
            signal.direction,
            dxy_bias,
            self.dxy_apply_pairs,
        ) if self.dxy_filter_enabled else True

        if self.dxy_filter_enabled and not signal.dxy_filter_confirmed:
            rejection_reasons.append(f"dxy_filter_rejected:{dxy_bias}")
            return [], SessionSummary(
                session_date=session_date,
                instrument=symbol,
                or_high=opening_range.high,
                or_low=opening_range.low,
                or_midpoint=opening_range.midpoint,
                atr_14=atr_14,
                manipulation_flagged=manipulation_flagged,
                mode_activated=mode_activated.value,
                breakout_signal_fired=True,
                retest_confirmed=signal.retest_detected,
                pattern_confirmed=bool(signal.pattern_detected),
                trend_aligned=signal.trend_aligned,
                dxy_filter_confirmed=False,
                trigger_candle=signal.trigger_candle or "",
                trade_executed=False,
                rejection_reasons=rejection_reasons,
            )

        # ------------------------------------------------------------------
        # Fibonacci zone gating + dynamic stop/targets
        # ------------------------------------------------------------------
        fib = get_fib_zones(opening_range, reversal_tp_level=self.reversal_tp_level)
        signal.fib_cheap_zone = fib.cheap_buy_level
        signal.fib_expensive_zone = fib.expensive_sell_level

        if self.use_fib_zone_filter and not in_fib_zone(signal.entry_price, signal.direction, fib):
            rejection_reasons.append("outside_fib_zone")
            return [], SessionSummary(
                session_date=session_date,
                instrument=symbol,
                or_high=opening_range.high,
                or_low=opening_range.low,
                or_midpoint=opening_range.midpoint,
                atr_14=atr_14,
                manipulation_flagged=manipulation_flagged,
                mode_activated=mode_activated.value,
                breakout_signal_fired=True,
                retest_confirmed=signal.retest_detected,
                pattern_confirmed=bool(signal.pattern_detected),
                trend_aligned=signal.trend_aligned,
                dxy_filter_confirmed=signal.dxy_filter_confirmed,
                trigger_candle=signal.trigger_candle or "",
                trade_executed=False,
                rejection_reasons=rejection_reasons,
            )

        if self.dynamic_stop_enabled:
            post_atr = add_atr(post_bars, self.dynamic_stop_atr_period, name="atr_1m")
            atr_val = float(post_atr.loc[post_atr.index <= signal.signal_time].iloc[-1]["atr_1m"]) if not post_atr.loc[post_atr.index <= signal.signal_time].empty else 0.0
            if atr_val > 0:
                if signal.direction == TradeDirection.LONG:
                    signal.stop_loss = round(signal.entry_price - (atr_val * self.dynamic_stop_atr_mult), 6)
                else:
                    signal.stop_loss = round(signal.entry_price + (atr_val * self.dynamic_stop_atr_mult), 6)

        if signal.direction == TradeDirection.LONG:
            risk = signal.entry_price - signal.stop_loss
            if risk <= 0:
                rejection_reasons.append("invalid_dynamic_stop")
                return [], self._no_trade_summary(symbol, session_date, rejection_reasons, opening_range, atr_14, manipulation_flagged)
            signal.one_r_target = round(signal.entry_price + (risk * self.partial_first_scale_ratio), 6)
            signal.take_profit_2r = round(signal.entry_price + risk * 2.0, 6)
            signal.take_profit_3r = round(signal.entry_price + risk * 3.0, 6)
            if signal.mode == StrategyMode.MANIPULATION and self.reversal_touch_and_turn_tp:
                signal.take_profit_2r = fib.tp_reversal_level
        else:
            risk = signal.stop_loss - signal.entry_price
            if risk <= 0:
                rejection_reasons.append("invalid_dynamic_stop")
                return [], self._no_trade_summary(symbol, session_date, rejection_reasons, opening_range, atr_14, manipulation_flagged)
            signal.one_r_target = round(signal.entry_price - (risk * self.partial_first_scale_ratio), 6)
            signal.take_profit_2r = round(signal.entry_price - risk * 2.0, 6)
            signal.take_profit_3r = round(signal.entry_price - risk * 3.0, 6)
            if signal.mode == StrategyMode.MANIPULATION and self.reversal_touch_and_turn_tp:
                signal.take_profit_2r = fib.tp_reversal_level

        signal.partial_scale_pct = self.partial_first_scale_pct
        signal.move_sl_to_be = self.partial_move_sl_to_be

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
            trend_aligned=signal.trend_aligned,
            dxy_filter_confirmed=signal.dxy_filter_confirmed,
            trigger_candle=signal.trigger_candle or "",
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
            trend_aligned=False,
            dxy_filter_confirmed=False,
            trigger_candle="",
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
