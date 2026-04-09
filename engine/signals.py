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
from typing import Optional

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


def _is_displacement_gap_long(prior: pd.Series, current: pd.Series) -> bool:
    """Bullish displacement gap: current low is fully above prior high."""
    return current["low"] > prior["high"]


def _is_displacement_gap_short(prior: pd.Series, current: pd.Series) -> bool:
    """Bearish displacement gap: current high is fully below prior low."""
    return current["high"] < prior["low"]


def _gap_size(prior: pd.Series, current: pd.Series) -> float:
    """Absolute price gap between the two bars."""
    if current["low"] > prior["high"]:
        return current["low"] - prior["high"]
    if current["high"] < prior["low"]:
        return prior["low"] - current["high"]
    return 0.0


def _body_pct(bar: pd.Series) -> float:
    """Body size as a fraction of total bar range (0–1).  0 for doji."""
    tr = _total_range(bar)
    return (_body_size(bar) / tr) if tr > 0 else 0.0


def _is_opposite_color(bar: pd.Series, direction: TradeDirection) -> bool:
    if direction == TradeDirection.LONG:
        return bar["close"] < bar["open"]
    return bar["close"] > bar["open"]


def _is_clean_pullback(
    prev2: pd.Series,
    prev1: pd.Series,
    direction: TradeDirection,
) -> bool:
    return _is_opposite_color(prev2, direction) and _is_opposite_color(prev1, direction)


def _is_high_volume_doji(current: pd.Series, prev1: pd.Series, prev2: pd.Series) -> bool:
    tr = _total_range(current)
    if tr <= 0:
        return False

    body = _body_size(current)
    upper_wick = current["high"] - max(current["open"], current["close"])
    lower_wick = min(current["open"], current["close"]) - current["low"]

    # Doji-like structure: small body with two meaningful wicks.
    is_doji = (body / tr <= 0.25) and (upper_wick / tr >= 0.25) and (lower_wick / tr >= 0.25)
    if not is_doji:
        return False

    # "High volume" proxy when real volume is unavailable/redundant:
    # candle range must exceed at least one of the two previous ranges.
    return tr > min(_total_range(prev1), _total_range(prev2))


def _has_no_opposite_wick(bar: pd.Series, direction: TradeDirection, tol: float = 1e-9) -> bool:
    body_low = min(bar["open"], bar["close"])
    body_high = max(bar["open"], bar["close"])
    if direction == TradeDirection.LONG:
        return abs(body_low - bar["low"]) <= tol
    return abs(bar["high"] - body_high) <= tol


def _is_qualified_gap(
    prior: pd.Series,
    current: pd.Series,
    direction: "TradeDirection",
    atr14: float,
    min_atr_pct: float,
    min_body_pct: float,
) -> bool:
    """
    Returns True when a raw displacement gap also satisfies both qualifiers:

    A (ATR gate)  : gap size >= min_atr_pct% of the 14-day ATR.
    B (Body gate) : the gap bar has a strong directional body
                    (body / total range >= min_body_pct).

    Either gate is bypassed when its threshold is set to 0.
    """
    from data.models import TradeDirection as _TD  # local import avoids circular ref
    is_gap = (
        _is_displacement_gap_long(prior, current)
        if direction == _TD.LONG
        else _is_displacement_gap_short(prior, current)
    )
    if not is_gap:
        return False

    if min_atr_pct > 0 and atr14 > 0:
        if _gap_size(prior, current) < (min_atr_pct / 100.0) * atr14:
            log.debug(
                "  Gap rejected: size %.5f < %.1f%% ATR (%.5f)",
                _gap_size(prior, current), min_atr_pct, atr14,
            )
            return False

    if min_body_pct > 0:
        if _body_pct(current) < min_body_pct / 100.0:
            log.debug(
                "  Gap rejected: body_pct %.2f < %.1f%%",
                _body_pct(current) * 100, min_body_pct,
            )
            return False

    return True


# ---------------------------------------------------------------------------
# Mode A: Breakout + Slingshot Retest (Casper SMC)
# ---------------------------------------------------------------------------

def detect_breakout_signal(
    bars: pd.DataFrame,
    opening_range: OpeningRange,
    session_end_time,
    eval_bars: Optional[pd.DataFrame] = None,
    require_high_volume_doji: bool = True,
    require_no_opposite_wick: bool = False,
    allow_displacement_gap_entry: bool = False,
    entry_priority: str = "retest_first",
    displacement_min_atr_pct: float = 0.0,
    displacement_min_body_pct: float = 0.0,
    atr14: float = 0.0,
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
    retest_seen = False
    trigger_name = None

    if eval_bars is None:
        eval_bars = bars

    use_gap_first = entry_priority == "gap_first"

    def _build_breakout_signal(
        ts,
        direction: TradeDirection,
        entry_price: float,
        signal_time,
        retest_detected: bool,
        displacement_detected: bool,
        trigger_candle: Optional[str] = None,
    ) -> Optional[SignalContext]:
        sl = opening_range.midpoint
        if direction == TradeDirection.LONG:
            risk = entry_price - sl
            if risk <= 0:
                return None
            tp2 = round(entry_price + risk * 2, 6)
            tp3 = round(entry_price + risk * 3, 6)
        else:
            risk = sl - entry_price
            if risk <= 0:
                return None
            tp2 = round(entry_price - risk * 2, 6)
            tp3 = round(entry_price - risk * 3, 6)

        return SignalContext(
            session_date=str(ts.date()),
            instrument="",
            opening_range=opening_range,
            atr_14=0.0,
            atr_threshold=0.0,
            manipulation_flagged=False,
            mode=StrategyMode.BREAKOUT,
            direction=direction,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit_2r=tp2,
            take_profit_3r=tp3,
            signal_time=signal_time,
            retest_detected=retest_detected,
            displacement_detected=displacement_detected,
            breakout_candle_time=breakout_bar_time,
            trigger_candle=trigger_candle,
        )

    prev_bar = None
    for ts, bar in bars.iterrows():
        if ts.time() >= session_end_time:
            break

        # --- Step 1: Detect breakout candle ---
        if breakout_direction is None:
            if _is_full_body_breakout_long(bar, or_high):
                breakout_direction = TradeDirection.LONG
                breakout_bar_time  = ts
                log.debug("  Breakout LONG detected at %s", ts)
                prev_bar = bar
                continue
            elif _is_full_body_breakout_short(bar, or_low):
                breakout_direction = TradeDirection.SHORT
                breakout_bar_time  = ts
                log.debug("  Breakout SHORT detected at %s", ts)
                prev_bar = bar
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

        # --- Step 3A: Displacement gap entry (gap-first policy) ---
        if (
            use_gap_first
            and allow_displacement_gap_entry
            and breakout_direction is not None
            and prev_bar is not None
        ):
            gap_qualified = _is_qualified_gap(
                prev_bar, bar, breakout_direction,
                atr14, displacement_min_atr_pct, displacement_min_body_pct,
            )

            if gap_qualified:
                next_idx = bars.index.get_loc(ts) + 1
                if next_idx < len(bars):
                    entry_price = float(bar["close"])
                    sig = _build_breakout_signal(
                        ts=ts,
                        direction=breakout_direction,
                        entry_price=entry_price,
                        signal_time=ts.to_pydatetime(),
                        retest_detected=False,
                        displacement_detected=True,
                        trigger_candle="displacement_gap",
                    )
                    if sig is not None:
                        prev_bar = bar
                        return sig

        # --- Step 3B: Detect valid retest ---
        idx = bars.index.get_loc(ts)
        eval_bar = eval_bars.iloc[idx]

        if breakout_direction == TradeDirection.LONG and _is_valid_retest_long(bar, or_high):
            retest_seen = True

        if breakout_direction == TradeDirection.SHORT and _is_valid_retest_short(bar, or_low):
            retest_seen = True

        if (
            breakout_direction is not None
            and retest_seen
            and idx >= 2
            and require_high_volume_doji
        ):
            prev1_eval = eval_bars.iloc[idx - 1]
            prev2_eval = eval_bars.iloc[idx - 2]
            if _is_clean_pullback(prev2_eval, prev1_eval, breakout_direction):
                if _is_high_volume_doji(eval_bar, prev1_eval, prev2_eval):
                    confirmed = True
                    if require_no_opposite_wick:
                        next_idx = idx + 1
                        if next_idx >= len(eval_bars):
                            confirmed = False
                        else:
                            confirmed = _has_no_opposite_wick(
                                eval_bars.iloc[next_idx], breakout_direction
                            )
                    if confirmed:
                        trigger_name = "high_volume_doji"
                        entry_price = float(bar["close"])
                        sig = _build_breakout_signal(
                            ts=ts,
                            direction=breakout_direction,
                            entry_price=entry_price,
                            signal_time=ts.to_pydatetime(),
                            retest_detected=True,
                            displacement_detected=False,
                            trigger_candle=trigger_name,
                        )
                        if sig is not None:
                            prev_bar = bar
                            return sig

        if breakout_direction == TradeDirection.SHORT and _is_valid_retest_short(bar, or_low) and not require_high_volume_doji:
            next_idx = bars.index.get_loc(ts) + 1
            if next_idx >= len(bars):
                prev_bar = bar
                continue
            entry_bar = bars.iloc[next_idx]
            entry_price = float(entry_bar["open"])
            sig = _build_breakout_signal(
                ts=ts,
                direction=TradeDirection.SHORT,
                entry_price=entry_price,
                signal_time=entry_bar.name.to_pydatetime(),
                retest_detected=True,
                displacement_detected=False,
                trigger_candle="retest",
            )
            if sig is None:
                prev_bar = bar
                continue

            prev_bar = bar
            return sig

        if breakout_direction == TradeDirection.LONG and _is_valid_retest_long(bar, or_high) and not require_high_volume_doji:
            next_idx = bars.index.get_loc(ts) + 1
            if next_idx >= len(bars):
                log.debug("  Retest LONG confirmed but no next bar available.")
                prev_bar = bar
                continue
            entry_bar = bars.iloc[next_idx]
            entry_price = float(entry_bar["open"])
            sig = _build_breakout_signal(
                ts=ts,
                direction=TradeDirection.LONG,
                entry_price=entry_price,
                signal_time=entry_bar.name.to_pydatetime(),
                retest_detected=True,
                displacement_detected=False,
                trigger_candle="retest",
            )
            if sig is None:
                prev_bar = bar
                continue
            prev_bar = bar
            return sig

        # --- Step 3C: Displacement gap entry (retest-first policy fallback) ---
        if (
            (not use_gap_first)
            and allow_displacement_gap_entry
            and breakout_direction is not None
            and prev_bar is not None
        ):
            gap_qualified = _is_qualified_gap(
                prev_bar, bar, breakout_direction,
                atr14, displacement_min_atr_pct, displacement_min_body_pct,
            )
            if gap_qualified:
                entry_price = float(bar["close"])
                sig = _build_breakout_signal(
                    ts=ts,
                    direction=breakout_direction,
                    entry_price=entry_price,
                    signal_time=ts.to_pydatetime(),
                    retest_detected=False,
                    displacement_detected=True,
                    trigger_candle="displacement_gap",
                )
                if sig is not None:
                    prev_bar = bar
                    return sig

        if breakout_direction == TradeDirection.SHORT:
            if _is_valid_retest_short(bar, or_low):
                next_idx = bars.index.get_loc(ts) + 1
                if next_idx >= len(bars):
                    prev_bar = bar
                    continue
                entry_bar = bars.iloc[next_idx]
                entry_price = float(entry_bar["open"])
                sig = _build_breakout_signal(
                    ts=ts,
                    direction=TradeDirection.SHORT,
                    entry_price=entry_price,
                    signal_time=entry_bar.name.to_pydatetime(),
                    retest_detected=True,
                    displacement_detected=False,
                )
                if sig is None:
                    prev_bar = bar
                    continue

                prev_bar = bar
                return sig

        prev_bar = bar

    return None


# ---------------------------------------------------------------------------
# Mode B: Manipulation / Reversal (ProRealAlgos)
# ---------------------------------------------------------------------------

def detect_manipulation_signal(
    bars: pd.DataFrame,
    opening_range: OpeningRange,
    initial_direction: TradeDirection,   # direction of the manipulation spike
    session_end_time,
    require_full_body_outside: bool = True,
    require_extreme_boundary: bool = True,
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

        # Pattern must CLOSE completely outside the opening range.
        if require_full_body_outside:
            bar_is_outside = (min(bar["open"], bar["close"]) > or_high) or (
                max(bar["open"], bar["close"]) < or_low
            )
        else:
            bar_is_outside = (bar["close"] > or_high) or (bar["close"] < or_low)
        if not bar_is_outside:
            prev_bar = bar
            continue

        if require_extreme_boundary:
            if reversal_direction == TradeDirection.SHORT and bar["high"] < or_high:
                prev_bar = bar
                continue
            if reversal_direction == TradeDirection.LONG and bar["low"] > or_low:
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
                    trigger_candle=pattern,
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
