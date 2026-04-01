"""
engine/signals.py
=================
Signal detection for the unified hybrid ruleset.

Three modes are implemented as a sequential decision tree applied to
post-opening-range bars.  Each mode produces a SignalContext with all
entry parameters populated, or returns None if no valid signal is found.

Mode selection:
  - Manipulation Mode  : opening range >= 25% of 14-day ATR
  - Breakout Mode      : default when manipulation is NOT flagged
  - Mean Reversion     : fallback when a breakout fails (candle closes
                         back inside the range after a valid breakout candle)

Entry logic summary:
  Breakout   : full-body candle close outside OR → permissive retest
               (wick or body touches boundary, candle closes outside) → enter
  Manipulation: hammer / inverted-hammer / engulfing candle outside OR → enter
               in the direction OPPOSITE to the initial spike
  Mean Rev   : breakout candle confirmed but subsequent candle closes
               back inside OR → enter toward opposite OR boundary
"""

import logging
from typing import Optional, Tuple

import pandas as pd

from data.models import (
    OpeningRange, SignalContext, StrategyMode, TradeDirection
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Candlestick pattern helpers
# ---------------------------------------------------------------------------

_HAMMER_BODY_RATIO   = 0.35   # body ≤ 35% of total candle range
_HAMMER_WICK_RATIO   = 0.60   # lower/upper wick ≥ 60% of total range
_ENGULF_BODY_RATIO   = 1.0    # engulfing body must exceed prior body entirely


def _body_size(bar: pd.Series) -> float:
    return abs(bar["close"] - bar["open"])


def _total_range(bar: pd.Series) -> float:
    return bar["high"] - bar["low"]


def _is_bullish(bar: pd.Series) -> bool:
    return bar["close"] > bar["open"]


def _is_hammer(bar: pd.Series) -> bool:
    """
    Bullish hammer: small body near the top, long lower wick.
    Signals institutional buying stepping in after a downward spike.
    """
    tr = _total_range(bar)
    if tr == 0:
        return False
    body   = _body_size(bar)
    lower_wick = min(bar["open"], bar["close"]) - bar["low"]
    return (
        body / tr <= _HAMMER_BODY_RATIO and
        lower_wick / tr >= _HAMMER_WICK_RATIO
    )


def _is_inverted_hammer(bar: pd.Series) -> bool:
    """
    Inverted hammer: small body near the bottom, long upper wick.
    Signals institutional selling stepping in after an upward spike.
    """
    tr = _total_range(bar)
    if tr == 0:
        return False
    body       = _body_size(bar)
    upper_wick = bar["high"] - max(bar["open"], bar["close"])
    return (
        body / tr <= _HAMMER_BODY_RATIO and
        upper_wick / tr >= _HAMMER_WICK_RATIO
    )


def _is_bullish_engulfing(current: pd.Series, prior: pd.Series) -> bool:
    """Current bullish bar's body fully engulfs the prior bearish bar's body."""
    return (
        _is_bullish(current) and
        not _is_bullish(prior) and
        current["close"] > prior["open"] and
        current["open"]  < prior["close"]
    )


def _is_bearish_engulfing(current: pd.Series, prior: pd.Series) -> bool:
    """Current bearish bar's body fully engulfs the prior bullish bar's body."""
    return (
        not _is_bullish(current) and
        _is_bullish(prior) and
        current["close"] < prior["open"] and
        current["open"]  > prior["close"]
    )


def detect_reversal_pattern(
    current: pd.Series,
    prior: Optional[pd.Series],
) -> Optional[str]:
    """
    Check for any of the four institutional reversal patterns specified by
    ProRealAlgos.  Returns the pattern name or None.
    """
    if _is_hammer(current):
        return "hammer"
    if _is_inverted_hammer(current):
        return "inverted_hammer"
    if prior is not None:
        if _is_bullish_engulfing(current, prior):
            return "bullish_engulfing"
        if _is_bearish_engulfing(current, prior):
            return "bearish_engulfing"
    return None


# ---------------------------------------------------------------------------
# Retest detection (permissive — wick counts)
# ---------------------------------------------------------------------------

def _is_valid_retest_long(
    bar: pd.Series,
    or_high: float,
) -> bool:
    """
    A long retest is valid when:
      - The bar's LOW (wick or body) touches or enters the OR high
      - The bar CLOSES above OR high (outside the range)
    This implements the permissive interpretation: a wick touching the
    boundary is sufficient to trigger the 'slingshot' retest.
    """
    return bar["low"] <= or_high and bar["close"] > or_high


def _is_valid_retest_short(
    bar: pd.Series,
    or_low: float,
) -> bool:
    """
    A short retest is valid when:
      - The bar's HIGH (wick or body) touches or enters the OR low
      - The bar CLOSES below OR low (outside the range)
    """
    return bar["high"] >= or_low and bar["close"] < or_low


# ---------------------------------------------------------------------------
# Breakout detection
# ---------------------------------------------------------------------------

def _is_full_body_breakout_long(bar: pd.Series, or_high: float) -> bool:
    """Full candle BODY (open and close) must be above OR high — wicks excluded."""
    return min(bar["open"], bar["close"]) > or_high


def _is_full_body_breakout_short(bar: pd.Series, or_low: float) -> bool:
    """Full candle BODY must be below OR low."""
    return max(bar["open"], bar["close"]) < or_low


# ---------------------------------------------------------------------------
# Mode A: Breakout + Slingshot Retest (Casper SMC)
# ---------------------------------------------------------------------------

def detect_breakout_signal(
    bars: pd.DataFrame,
    opening_range: OpeningRange,
    session_end_time,
) -> Optional[SignalContext]:
    """
    Scans post-opening bars for:
      1. A full-body candle close outside the opening range.
      2. A subsequent valid retest (permissive: wick touches boundary,
         candle closes outside).
      3. Entry on the open of the bar immediately following the retest.

    Returns a SignalContext with all entry parameters set, or None.
    """
    or_high = opening_range.high
    or_low  = opening_range.low

    breakout_direction: Optional[TradeDirection] = None
    breakout_bar_time  = None

    for i, (ts, bar) in enumerate(bars.iterrows()):
        if ts.time() >= session_end_time:
            break

        # --- Step 1: Detect breakout candle ---
        if breakout_direction is None:
            if _is_full_body_breakout_long(bar, or_high):
                breakout_direction = TradeDirection.LONG
                breakout_bar_time  = ts
                log.debug("  Breakout LONG detected at %s", ts)
                continue
            elif _is_full_body_breakout_short(bar, or_low):
                breakout_direction = TradeDirection.SHORT
                breakout_bar_time  = ts
                log.debug("  Breakout SHORT detected at %s", ts)
                continue

        # --- Step 2: Watch for mean reversion (breakout failure) ---
        if breakout_direction == TradeDirection.LONG:
            # Bar closes back inside range → breakout failed
            if bar["close"] < or_high:
                log.debug("  Breakout LONG failed at %s — switching to mean reversion.", ts)
                return None   # caller will call detect_mean_reversion_signal

        if breakout_direction == TradeDirection.SHORT:
            if bar["close"] > or_low:
                log.debug("  Breakout SHORT failed at %s — switching to mean reversion.", ts)
                return None

        # --- Step 3: Detect valid retest ---
        if breakout_direction == TradeDirection.LONG:
            if _is_valid_retest_long(bar, or_high):
                # Entry is on the NEXT bar
                next_idx = bars.index.get_loc(ts) + 1
                if next_idx >= len(bars):
                    log.debug("  Retest LONG confirmed but no next bar available.")
                    return None
                entry_bar = bars.iloc[next_idx]
                entry_price = float(entry_bar["open"])
                sl  = opening_range.midpoint
                risk = entry_price - sl
                if risk <= 0:
                    continue
                return SignalContext(
                    session_date=str(ts.date()),
                    instrument="",          # filled by backtester
                    opening_range=opening_range,
                    atr_14=0.0,             # filled by backtester
                    atr_threshold=0.0,
                    manipulation_flagged=False,
                    mode=StrategyMode.BREAKOUT,
                    direction=TradeDirection.LONG,
                    entry_price=entry_price,
                    stop_loss=sl,
                    take_profit_2r=round(entry_price + risk * 2, 6),
                    take_profit_3r=round(entry_price + risk * 3, 6),
                    signal_time=entry_bar.name.to_pydatetime(),
                    retest_detected=True,
                    breakout_candle_time=breakout_bar_time,
                )

        if breakout_direction == TradeDirection.SHORT:
            if _is_valid_retest_short(bar, or_low):
                next_idx = bars.index.get_loc(ts) + 1
                if next_idx >= len(bars):
                    return None
                entry_bar = bars.iloc[next_idx]
                entry_price = float(entry_bar["open"])
                sl  = opening_range.midpoint
                risk = sl - entry_price
                if risk <= 0:
                    continue
                return SignalContext(
                    session_date=str(ts.date()),
                    instrument="",
                    opening_range=opening_range,
                    atr_14=0.0,
                    atr_threshold=0.0,
                    manipulation_flagged=False,
                    mode=StrategyMode.BREAKOUT,
                    direction=TradeDirection.SHORT,
                    entry_price=entry_price,
                    stop_loss=sl,
                    take_profit_2r=round(entry_price - risk * 2, 6),
                    take_profit_3r=round(entry_price - risk * 3, 6),
                    signal_time=entry_bar.name.to_pydatetime(),
                    retest_detected=True,
                    breakout_candle_time=breakout_bar_time,
                )

    return None


# ---------------------------------------------------------------------------
# Mode B: Manipulation / Reversal (ProRealAlgos)
# ---------------------------------------------------------------------------

def detect_manipulation_signal(
    bars: pd.DataFrame,
    opening_range: OpeningRange,
    initial_direction: TradeDirection,   # direction of the manipulation spike
    session_end_time,
) -> Optional[SignalContext]:
    """
    After a manipulation candle is flagged, scan for a reversal candlestick
    pattern (Hammer / Inverted Hammer / Engulfing) that forms OUTSIDE the
    opening range.

    Entry direction is OPPOSITE to the initial spike (e.g., spike up → short).
    """
    or_high = opening_range.high
    or_low  = opening_range.low

    reversal_direction = (
        TradeDirection.SHORT if initial_direction == TradeDirection.LONG
        else TradeDirection.LONG
    )

    prev_bar = None
    for ts, bar in bars.iterrows():
        if ts.time() >= session_end_time:
            break

        # Pattern must form OUTSIDE the opening range
        bar_is_outside = (bar["close"] > or_high) or (bar["close"] < or_low)
        if not bar_is_outside:
            prev_bar = bar
            continue

        pattern = detect_reversal_pattern(bar, prev_bar)

        if pattern:
            # Validate pattern direction matches expected reversal
            valid = (
                (reversal_direction == TradeDirection.SHORT and
                 pattern in ("inverted_hammer", "bearish_engulfing")) or
                (reversal_direction == TradeDirection.LONG and
                 pattern in ("hammer", "bullish_engulfing"))
            )
            if valid:
                next_idx = bars.index.get_loc(ts) + 1
                if next_idx >= len(bars):
                    prev_bar = bar
                    continue

                entry_bar   = bars.iloc[next_idx]
                entry_price = float(entry_bar["open"])
                sl          = opening_range.midpoint

                if reversal_direction == TradeDirection.SHORT:
                    risk = sl - entry_price
                    if risk <= 0:
                        prev_bar = bar
                        continue
                    tp2 = round(entry_price - risk * 2, 6)
                    tp3 = round(entry_price - risk * 3, 6)
                else:
                    risk = entry_price - sl
                    if risk <= 0:
                        prev_bar = bar
                        continue
                    tp2 = round(entry_price + risk * 2, 6)
                    tp3 = round(entry_price + risk * 3, 6)

                log.debug(
                    "  Manipulation reversal pattern '%s' confirmed at %s, "
                    "direction=%s", pattern, ts, reversal_direction.value
                )

                return SignalContext(
                    session_date=str(ts.date()),
                    instrument="",
                    opening_range=opening_range,
                    atr_14=0.0,
                    atr_threshold=0.0,
                    manipulation_flagged=True,
                    mode=StrategyMode.MANIPULATION,
                    direction=reversal_direction,
                    entry_price=entry_price,
                    stop_loss=sl,
                    take_profit_2r=tp2,
                    take_profit_3r=tp3,
                    signal_time=entry_bar.name.to_pydatetime(),
                    pattern_detected=pattern,
                )

        prev_bar = bar

    return None


# ---------------------------------------------------------------------------
# Mode C: Mean Reversion fallback (Jdub Trades)
# ---------------------------------------------------------------------------

def detect_mean_reversion_signal(
    bars: pd.DataFrame,
    opening_range: OpeningRange,
    failed_breakout_direction: TradeDirection,
    session_end_time,
) -> Optional[SignalContext]:
    """
    When a breakout candle forms but the subsequent candle closes back
    inside the range (failed breakout), switch to mean reversion mode.

    Entry: from the failed breakout side toward the opposite OR boundary.
    Target: the opposite boundary (not a fixed R multiple).
    SL: midpoint.
    """
    or_high = opening_range.high
    or_low  = opening_range.low
    midpoint = opening_range.midpoint

    # Reversal direction is opposite to failed breakout
    entry_direction = (
        TradeDirection.SHORT if failed_breakout_direction == TradeDirection.LONG
        else TradeDirection.LONG
    )

    for ts, bar in bars.iterrows():
        if ts.time() >= session_end_time:
            break

        # Wait for price to re-enter the range clearly
        price_in_range = or_low < bar["close"] < or_high

        if price_in_range:
            next_idx = bars.index.get_loc(ts) + 1
            if next_idx >= len(bars):
                return None

            entry_bar   = bars.iloc[next_idx]
            entry_price = float(entry_bar["open"])
            sl          = midpoint

            if entry_direction == TradeDirection.SHORT:
                risk  = sl - entry_price
                tp_target = or_low   # target opposite boundary
            else:
                risk  = entry_price - sl
                tp_target = or_high

            if risk <= 0:
                continue

            tp2 = round(entry_price + (tp_target - entry_price) * 0.8, 6)  # 80% to boundary
            tp3 = tp_target   # full boundary as 3R proxy

            log.debug("  Mean reversion signal at %s, direction=%s", ts, entry_direction.value)

            return SignalContext(
                session_date=str(ts.date()),
                instrument="",
                opening_range=opening_range,
                atr_14=0.0,
                atr_threshold=0.0,
                manipulation_flagged=False,
                mode=StrategyMode.MEAN_REVERSION,
                direction=entry_direction,
                entry_price=entry_price,
                stop_loss=sl,
                take_profit_2r=tp2,
                take_profit_3r=tp3,
                signal_time=entry_bar.name.to_pydatetime(),
            )

    return None
