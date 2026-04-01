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
    direction   = signal.direction

    position_size, risk_amount = calculate_position_size(
        entry_price, sl, account_equity, risk_pct, commission
    )

    # Track resolution state for each target independently
    result_2r = {"resolved": False, "exit_time": None, "exit_price": None,
                 "outcome": None, "pnl": None}
    result_3r = {"resolved": False, "exit_time": None, "exit_price": None,
                 "outcome": None, "pnl": None}

    exit_reason = ExitReason.SESSION_END

    for ts, bar in remaining_bars.iterrows():
        bar_time = ts.to_pydatetime()

        # Session gate — close any open targets at bar close
        if ts.time() >= session_end_time:
            close_price = float(bar["close"])
            if not result_2r["resolved"]:
                _close_at(result_2r, bar_time, close_price, entry_price,
                          direction, position_size, commission)
            if not result_3r["resolved"]:
                _close_at(result_3r, bar_time, close_price, entry_price,
                          direction, position_size, commission)
            exit_reason = ExitReason.SESSION_END
            break

        if direction == TradeDirection.LONG:
            hit_sl  = bar["low"]  <= sl
            hit_tp2 = bar["high"] >= tp2
            hit_tp3 = bar["high"] >= tp3
        else:
            hit_sl  = bar["high"] >= sl
            hit_tp2 = bar["low"]  <= tp2
            hit_tp3 = bar["low"]  <= tp3

        # Stop-loss hit — closes all open targets
        if hit_sl:
            exit_reason = ExitReason.SL_HIT
            if not result_2r["resolved"]:
                _close_at(result_2r, bar_time, sl, entry_price,
                          direction, position_size, commission)
                result_2r["outcome"] = "loss"
            if not result_3r["resolved"]:
                _close_at(result_3r, bar_time, sl, entry_price,
                          direction, position_size, commission)
                result_3r["outcome"] = "loss"
            break

        if hit_tp2 and not result_2r["resolved"]:
            _close_at(result_2r, bar_time, tp2, entry_price,
                      direction, position_size, commission)
            result_2r["outcome"] = "win"
            exit_reason = ExitReason.TP_HIT

        if hit_tp3 and not result_3r["resolved"]:
            _close_at(result_3r, bar_time, tp3, entry_price,
                      direction, position_size, commission)
            result_3r["outcome"] = "win"
            exit_reason = ExitReason.TP_HIT

        # Both targets resolved — done
        if result_2r["resolved"] and result_3r["resolved"]:
            break

    # Handle any targets not yet resolved (session ended, loop exhausted)
    if remaining_bars.empty:
        _close_at(result_2r, signal.signal_time, entry_price, entry_price,
                  direction, position_size, commission)
        _close_at(result_3r, signal.signal_time, entry_price, entry_price,
                  direction, position_size, commission)

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


def _close_at(result: dict, exit_time, exit_price, entry_price,
              direction: TradeDirection, position_size: float, commission: float):
    """Resolve one target at a given exit price."""
    if result["resolved"]:
        return
    result["resolved"]   = True
    result["exit_time"]  = exit_time
    result["exit_price"] = exit_price

    if direction == TradeDirection.LONG:
        gross = (exit_price - entry_price) * position_size
    else:
        gross = (entry_price - exit_price) * position_size

    result["pnl"] = round(gross - commission, 4)
    if result["outcome"] is None:
        result["outcome"] = "win" if result["pnl"] > 0 else "loss"
