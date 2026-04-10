"""
data/models.py
==============
Core dataclasses shared across all modules of the Precision Scalping Utility.
All inter-module communication is mediated through these structures to ensure
a single source of truth for every data shape in the system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class StrategyMode(str, Enum):
    BREAKOUT       = "breakout"
    MANIPULATION   = "manipulation"
    MEAN_REVERSION = "mean_reversion"
    NO_TRADE       = "no_trade"


class TradeDirection(str, Enum):
    LONG  = "long"
    SHORT = "short"


class ExitReason(str, Enum):
    TP_HIT       = "tp_hit"
    SL_HIT       = "sl_hit"
    SESSION_END  = "session_end"
    CIRCUIT_BREAK = "circuit_breaker"
    TP_25_ONLY   = "tp_25_only"         # 25% retracement hit, 50% not broken
    TP_25_AND_MONITOR = "tp_25_and_monitor" # 25% hit, monitoring for more
    TREND_REVERSAL = "trend_reversal"   # 75% retracement, swing mode


# ---------------------------------------------------------------------------
# Market structure
# ---------------------------------------------------------------------------

@dataclass
class OpeningRange:
    """High, low, and midpoint of the first N-minute candle of the session."""
    high:               float
    low:                float
    midpoint:           float
    candle_range:       float          # high - low
    candle_size_minutes: int
    open_time:          datetime
    close_time:         datetime


# ---------------------------------------------------------------------------
# Signal context — carries all intermediate state from Phase 0 through
# signal detection.  Passed between engine modules; never mutated once
# a TradeResult has been created from it.
# ---------------------------------------------------------------------------

@dataclass
class SignalContext:
    session_date:        str
    instrument:          str
    opening_range:       OpeningRange
    atr_14:              float
    atr_threshold:       float          # 25% of ATR
    manipulation_flagged: bool
    mode:                StrategyMode
    direction:           Optional[TradeDirection] = None
    entry_price:         Optional[float] = None
    stop_loss:           Optional[float] = None
    take_profit_2r:      Optional[float] = None
    take_profit_3r:      Optional[float] = None
    signal_time:         Optional[datetime] = None
    pattern_detected:    Optional[str] = None   # 'hammer','inv_hammer','engulfing'
    displacement_detected: bool = False
    retest_detected:     bool = False
    breakout_candle_time: Optional[datetime] = None
    trend_aligned:        bool = False
    dxy_filter_confirmed: bool = False
    dxy_bias:             Optional[str] = None
    fib_cheap_zone:       Optional[float] = None
    fib_expensive_zone:   Optional[float] = None
    trigger_candle:       Optional[str] = None
    one_r_target:         Optional[float] = None
    partial_scale_pct:    float = 50.0
    move_sl_to_be:        bool = True
    rejection_reasons:   List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Trade result — the canonical record of one executed trade
# ---------------------------------------------------------------------------

@dataclass
class TradeResult:
    """
    Complete, immutable record of a single simulated trade.
    Outcomes for 2R and 3R reward targets are tracked independently,
    allowing direct comparison of both R/R configurations from a single run.
    """
    # --- identity ---
    trade_id:           str
    session_date:       str
    instrument:         str
    mode:               str             # StrategyMode value
    direction:          str             # TradeDirection value

    # --- opening range context ---
    or_high:            float
    or_low:             float
    or_midpoint:        float
    atr_14:             float
    manipulation_flagged: bool
    pattern_detected:   str

    # --- execution ---
    entry_time:         datetime
    entry_price:        float
    stop_loss:          float
    take_profit_2r:     float
    take_profit_3r:     float
    position_size:      float           # units / shares / lots
    risk_amount:        float           # dollars risked
    one_r_target:       Optional[float] = None
    partial_scale_pct:  float = 50.0
    partial_exit_time:  Optional[datetime] = None
    partial_exit_price: Optional[float] = None
    stop_moved_to_be:   bool = False

    # --- 2R outcome ---
    exit_time_2r:       Optional[datetime] = None
    exit_price_2r:      Optional[float]   = None
    outcome_2r:         Optional[str]     = None  # 'win' | 'loss'
    pnl_2r:             Optional[float]   = None

    # --- 3R outcome ---
    exit_time_3r:       Optional[datetime] = None
    exit_price_3r:      Optional[float]   = None
    outcome_3r:         Optional[str]     = None
    pnl_3r:             Optional[float]   = None

    exit_reason:        Optional[str]     = None  # ExitReason value


# ---------------------------------------------------------------------------
# Session summary — one record per calendar day per instrument, regardless
# of whether a trade was taken.  Feeds the execution_log and run_report.
# ---------------------------------------------------------------------------

@dataclass
class SessionSummary:
    session_date:          str
    instrument:            str
    or_high:               float
    or_low:                float
    or_midpoint:           float
    atr_14:                float
    manipulation_flagged:  bool
    mode_activated:        str
    breakout_signal_fired: bool
    retest_confirmed:      bool
    pattern_confirmed:     bool
    trend_aligned:         bool = False
    dxy_filter_confirmed:  bool = False
    trigger_candle:        str = ""
    trade_executed:        bool = False
    trade_id:              Optional[str]  = None
    rejection_reasons:     List[str]      = field(default_factory=list)
