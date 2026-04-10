"""
engine/trade.py
===============
Trade object construction and resolution.

Given a confirmed SignalContext, this module:
  1. Calculates position size based on account risk parameters.
  2. Iterates remaining session bars to determine whether the 2R and 3R
     targets were hit before the stop-loss, or the session gate closed.

Both 2R and 3R outcomes are tracked independently on every trade.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd

from data.models import SignalContext, TradeDirection, TradeResult, ExitReason

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------

def calculate_position_size(
    entry_price: float,
    stop_loss: float,
    account_equity: float,
    risk_pct: float,        # e.g. 1.0 for 1%
    commission: float = 0.0,
) -> tuple[float, float]:
    """
    Returns (position_size, risk_amount) based on a fixed fractional
    risk model.

    position_size = risk_amount / (entry_to_stop distance)

    The commission is subtracted from the effective risk budget so that
    all P&L calculations are net of transaction costs.
    """
    risk_amount = (risk_pct / 100.0) * account_equity - commission
    if risk_amount <= 0:
        return 0.0, 0.0

    stop_distance = abs(entry_price - stop_loss)
    if stop_distance == 0:
        return 0.0, 0.0

    position_size = risk_amount / stop_distance
    return round(position_size, 4), round(risk_amount, 4)


# ---------------------------------------------------------------------------
# Trade resolution
# ---------------------------------------------------------------------------

def resolve_trade(
    signal: SignalContext,
    remaining_bars: pd.DataFrame,
    account_equity: float,
    risk_pct: float,
    commission: float,
    instrument: str,
    session_end_time,
) -> TradeResult:
    """
    Simulate the outcome of a trade given the post-entry bars.

    The function iterates bar-by-bar.  On each bar it checks:
      - Whether the SL has been hit (low for longs, high for shorts)
      - Whether the 2R TP has been hit (high for longs, low for shorts)
      - Whether the 3R TP has been hit

    Both TP targets are tracked concurrently; once one is hit it is
    recorded and tracking continues for the other.  If the session ends
    before either is resolved, the trade closes at the last bar's close.
    """
    trade_id = str(uuid.uuid4())[:8].upper()

    entry_price = signal.entry_price
    sl          = signal.stop_loss
    tp2         = signal.take_profit_2r
    tp3         = signal.take_profit_3r
    one_r       = signal.one_r_target
    direction   = signal.direction

    position_size, risk_amount = calculate_position_size(
        entry_price, sl, account_equity, risk_pct, commission
    )

    # Track resolution state for each target independently
    result_2r = {
        "resolved": False,
        "exit_time": None,
        "exit_price": None,
        "outcome": None,
        "pnl": None,
        "partial_taken": False,
        "partial_time": None,
        "partial_price": None,
        "partial_pnl": 0.0,
    }
    result_3r = {
        "resolved": False,
        "exit_time": None,
        "exit_price": None,
        "outcome": None,
        "pnl": None,
        "partial_taken": False,
        "partial_time": None,
        "partial_price": None,
        "partial_pnl": 0.0,
    }

    partial_scale = max(0.0, min(signal.partial_scale_pct / 100.0, 1.0))
    remaining_scale = 1.0 - partial_scale
    stop_2r = sl
    stop_3r = sl

    exit_reason = ExitReason.SESSION_END
    # For 20MA mean reversion, allow custom exit reason from signal.extra_info
    custom_exit_reason = None
    if hasattr(signal, 'extra_info') and signal.extra_info is not None:
        custom_exit_reason = signal.extra_info.get('exit_reason')

    for ts, bar in remaining_bars.iterrows():
        bar_time = ts.to_pydatetime()

        # Session gate — close any open targets at bar close
        if ts.time() >= session_end_time:
            close_price = float(bar["close"])
            if not result_2r["resolved"]:
                _close_scaled_target(
                    result=result_2r,
                    exit_time=bar_time,
                    exit_price=close_price,
                    entry_price=entry_price,
                    direction=direction,
                    position_size=position_size,
                    commission=commission,
                    remaining_scale=remaining_scale if result_2r["partial_taken"] else 1.0,
                )
            if not result_3r["resolved"]:
                _close_scaled_target(
                    result=result_3r,
                    exit_time=bar_time,
                    exit_price=close_price,
                    entry_price=entry_price,
                    direction=direction,
                    position_size=position_size,
                    commission=commission,
                    remaining_scale=remaining_scale if result_3r["partial_taken"] else 1.0,
                )
            exit_reason = ExitReason.SESSION_END
            break

        if direction == TradeDirection.LONG:
            bar_low = float(bar["low"])
            bar_high = float(bar["high"])
            hit_sl_2r = bar_low <= stop_2r
            hit_sl_3r = bar_low <= stop_3r
            hit_one_r = (one_r is not None) and (bar_high >= one_r)
            hit_tp2 = bar_high >= tp2
            hit_tp3 = bar_high >= tp3
        else:
            bar_low = float(bar["low"])
            bar_high = float(bar["high"])
            hit_sl_2r = bar_high >= stop_2r
            hit_sl_3r = bar_high >= stop_3r
            hit_one_r = (one_r is not None) and (bar_low <= one_r)
            hit_tp2 = bar_low <= tp2
            hit_tp3 = bar_low <= tp3

        # Conservative ordering: stop checks first, then profit events.
        if hit_sl_2r and not result_2r["resolved"]:
            _close_scaled_target(
                result=result_2r,
                exit_time=bar_time,
                exit_price=stop_2r,
                entry_price=entry_price,
                direction=direction,
                position_size=position_size,
                commission=commission,
                remaining_scale=remaining_scale if result_2r["partial_taken"] else 1.0,
            )
            result_2r["outcome"] = "loss"
            exit_reason = ExitReason.SL_HIT

        if hit_sl_3r and not result_3r["resolved"]:
            _close_scaled_target(
                result=result_3r,
                exit_time=bar_time,
                exit_price=stop_3r,
                entry_price=entry_price,
                direction=direction,
                position_size=position_size,
                commission=commission,
                remaining_scale=remaining_scale if result_3r["partial_taken"] else 1.0,
            )
            result_3r["outcome"] = "loss"
            exit_reason = ExitReason.SL_HIT

        if hit_one_r and one_r is not None:
            if (not result_2r["resolved"]) and (not result_2r["partial_taken"]) and partial_scale > 0:
                _take_partial(
                    result=result_2r,
                    exit_time=bar_time,
                    exit_price=one_r,
                    entry_price=entry_price,
                    direction=direction,
                    position_size=position_size,
                    commission=commission,
                    partial_scale=partial_scale,
                )
                if signal.move_sl_to_be:
                    stop_2r = entry_price

            if (not result_3r["resolved"]) and (not result_3r["partial_taken"]) and partial_scale > 0:
                _take_partial(
                    result=result_3r,
                    exit_time=bar_time,
                    exit_price=one_r,
                    entry_price=entry_price,
                    direction=direction,
                    position_size=position_size,
                    commission=commission,
                    partial_scale=partial_scale,
                )
                if signal.move_sl_to_be:
                    stop_3r = entry_price

        if hit_tp2 and not result_2r["resolved"]:
            _close_scaled_target(
                result=result_2r,
                exit_time=bar_time,
                exit_price=tp2,
                entry_price=entry_price,
                direction=direction,
                position_size=position_size,
                commission=commission,
                remaining_scale=remaining_scale if result_2r["partial_taken"] else 1.0,
            )
            result_2r["outcome"] = "win"
            if custom_exit_reason == "tp_25_only":
                exit_reason = ExitReason.TP_25_ONLY
            elif custom_exit_reason == "tp_25_and_monitor":
                exit_reason = ExitReason.TP_25_AND_MONITOR
            elif custom_exit_reason == "trend_reversal":
                exit_reason = ExitReason.TREND_REVERSAL
            else:
                exit_reason = ExitReason.TP_HIT

        if hit_tp3 and not result_3r["resolved"]:
            _close_scaled_target(
                result=result_3r,
                exit_time=bar_time,
                exit_price=tp3,
                entry_price=entry_price,
                direction=direction,
                position_size=position_size,
                commission=commission,
                remaining_scale=remaining_scale if result_3r["partial_taken"] else 1.0,
            )
            result_3r["outcome"] = "win"
            exit_reason = ExitReason.TP_HIT

        # Both targets resolved — done
        if result_2r["resolved"] and result_3r["resolved"]:
            break

    # Handle any targets not yet resolved (session ended, loop exhausted)
    if remaining_bars.empty:
        _close_scaled_target(
            result_2r,
            signal.signal_time,
            entry_price,
            entry_price,
            direction,
            position_size,
            commission,
            remaining_scale=remaining_scale if result_2r["partial_taken"] else 1.0,
        )
        _close_scaled_target(
            result_3r,
            signal.signal_time,
            entry_price,
            entry_price,
            direction,
            position_size,
            commission,
            remaining_scale=remaining_scale if result_3r["partial_taken"] else 1.0,
        )

    or_ = signal.opening_range
    return TradeResult(
        trade_id=trade_id,
        session_date=signal.session_date,
        instrument=instrument,
        mode=signal.mode.value,
        direction=signal.direction.value,
        or_high=or_.high,
        or_low=or_.low,
        or_midpoint=or_.midpoint,
        atr_14=signal.atr_14,
        manipulation_flagged=signal.manipulation_flagged,
        pattern_detected=signal.pattern_detected or "",
        entry_time=signal.signal_time,
        entry_price=entry_price,
        stop_loss=sl,
        take_profit_2r=tp2,
        take_profit_3r=tp3,
        position_size=position_size,
        risk_amount=risk_amount,
        one_r_target=one_r,
        partial_scale_pct=signal.partial_scale_pct,
        partial_exit_time=result_2r["partial_time"] or result_3r["partial_time"],
        partial_exit_price=result_2r["partial_price"] or result_3r["partial_price"],
        stop_moved_to_be=signal.move_sl_to_be and (
            result_2r["partial_taken"] or result_3r["partial_taken"]
        ),
        exit_time_2r=result_2r["exit_time"],
        exit_price_2r=result_2r["exit_price"],
        outcome_2r=result_2r["outcome"],
        pnl_2r=result_2r["pnl"],
        exit_time_3r=result_3r["exit_time"],
        exit_price_3r=result_3r["exit_price"],
        outcome_3r=result_3r["outcome"],
        pnl_3r=result_3r["pnl"],
        exit_reason=exit_reason.value,
    )


def _close_scaled_target(
    result: dict,
    exit_time,
    exit_price,
    entry_price,
    direction: TradeDirection,
    position_size: float,
    commission: float,
    remaining_scale: float,
):
    """Resolve one target using remaining position size after optional partial scale-out."""
    if result["resolved"]:
        return
    result["resolved"]   = True
    result["exit_time"]  = exit_time
    result["exit_price"] = exit_price

    qty = max(0.0, position_size * remaining_scale)
    if direction == TradeDirection.LONG:
        gross = (exit_price - entry_price) * qty
    else:
        gross = (entry_price - exit_price) * qty

    leg_commission = commission * remaining_scale
    result["pnl"] = round(result.get("partial_pnl", 0.0) + gross - leg_commission, 4)
    if result["outcome"] is None:
        result["outcome"] = "win" if result["pnl"] > 0 else "loss"


def _take_partial(
    result: dict,
    exit_time,
    exit_price,
    entry_price,
    direction: TradeDirection,
    position_size: float,
    commission: float,
    partial_scale: float,
):
    if result["resolved"] or result["partial_taken"]:
        return

    qty = max(0.0, position_size * partial_scale)
    if direction == TradeDirection.LONG:
        gross = (exit_price - entry_price) * qty
    else:
        gross = (entry_price - exit_price) * qty

    part_commission = commission * partial_scale
    result["partial_taken"] = True
    result["partial_time"] = exit_time
    result["partial_price"] = exit_price
    result["partial_pnl"] = round(gross - part_commission, 4)
