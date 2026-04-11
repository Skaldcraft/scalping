"""
tests/test_signals.py
====================
Tests for engine/signals.py pattern detection functions.

Covers: _is_hammer, _is_inverted_hammer, _is_bullish_engulfing,
_is_bearish_engulfing, _is_valid_retest_long, _is_valid_retest_short,
_is_full_body_breakout_long, _is_full_body_breakout_short.
"""

import pytest
import pandas as pd
from data.models import TradeDirection

from engine.signals import (
    _is_hammer,
    _is_inverted_hammer,
    _is_bullish_engulfing,
    _is_bearish_engulfing,
    _is_valid_retest_long,
    _is_valid_retest_short,
    _is_full_body_breakout_long,
    _is_full_body_breakout_short,
    detect_reversal_pattern,
)


class TestHammer:
    def test_valid_hammer_detected(self, hammer_bar):
        assert _is_hammer(hammer_bar) == True

    def test_non_hammer_rejected(self, non_hammer_bar):
        assert _is_hammer(non_hammer_bar) == False

    def test_doji_not_hammer(self, doji_bar):
        assert _is_hammer(doji_bar) == False

    def test_bearish_candle_not_hammer(self, full_body_bearish_bar):
        assert _is_hammer(full_body_bearish_bar) == False

    def test_inverted_hammer_not_hammer(self, inverted_hammer_bar):
        assert _is_hammer(inverted_hammer_bar) == False


class TestInvertedHammer:
    def test_valid_inverted_hammer_detected(self, inverted_hammer_bar):
        assert _is_inverted_hammer(inverted_hammer_bar) == True

    def test_normal_bar_not_inverted_hammer(self, non_hammer_bar):
        assert _is_inverted_hammer(non_hammer_bar) == False

    def test_hammer_not_inverted_hammer(self, hammer_bar):
        assert _is_inverted_hammer(hammer_bar) == False

    def test_doji_not_inverted_hammer(self, doji_bar):
        assert _is_inverted_hammer(doji_bar) == False


class TestBullishEngulfing:
    def test_bullish_engulfing_detected(self):
        prior = pd.Series(
            {"open": 100.30, "high": 100.35, "low": 99.80, "close": 99.85, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:44:00"),
        )
        current = pd.Series(
            {"open": 99.80, "high": 100.50, "low": 99.75, "close": 100.40, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_bullish_engulfing(current, prior) == True

    def test_same_direction_engulfing_rejected(self, hammer_bar, full_body_bullish_bar):
        assert _is_bullish_engulfing(full_body_bullish_bar, hammer_bar) == False

    def test_bearish_not_engulfed_by_bullish(self, hammer_bar, full_body_bullish_bar):
        assert _is_bullish_engulfing(hammer_bar, full_body_bullish_bar) == False

    def test_partial_overlap_rejected(self):
        prior = pd.Series(
            {"open": 100.30, "high": 100.35, "low": 99.80, "close": 99.85, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:44:00"),
        )
        current = pd.Series(
            {"open": 99.90, "high": 100.50, "low": 99.85, "close": 100.40, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_bullish_engulfing(current, prior) == False


class TestBearishEngulfing:
    def test_bearish_engulfing_detected(self, bearish_engulfing_current, bearish_engulfing_prior):
        assert _is_bearish_engulfing(bearish_engulfing_current, bearish_engulfing_prior) == True

    def test_same_direction_rejected(self, bearish_engulfing_prior):
        prior = bearish_engulfing_prior
        current = pd.Series(
            {"open": 100.30, "high": 100.50, "low": 99.80, "close": 99.90, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_bearish_engulfing(current, prior) == False


class TestDetectReversalPattern:
    def test_hammer_detected(self, hammer_bar):
        result = detect_reversal_pattern(hammer_bar, None)
        assert result == "hammer"

    def test_inverted_hammer_detected(self, inverted_hammer_bar):
        result = detect_reversal_pattern(inverted_hammer_bar, None)
        assert result == "inverted_hammer"

    def test_bullish_engulfing_detected(self):
        prior = pd.Series(
            {"open": 100.30, "high": 100.35, "low": 99.80, "close": 99.85, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:44:00"),
        )
        current = pd.Series(
            {"open": 99.80, "high": 100.50, "low": 99.75, "close": 100.40, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        result = detect_reversal_pattern(current, prior)
        assert result == "bullish_engulfing"

    def test_no_pattern_returns_none(self, non_hammer_bar):
        result = detect_reversal_pattern(non_hammer_bar, None)
        assert result is None


class TestValidRetest:
    def test_valid_retest_long_low_touches_or_high(self, or_high):
        bar = pd.Series(
            {"open": 100.05, "high": 100.10, "low": 99.95, "close": 100.08, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:50:00"),
        )
        assert _is_valid_retest_long(bar, or_high) == True

    def test_valid_retest_long_wick_touches(self, or_high):
        bar = pd.Series(
            {"open": 100.05, "high": 100.01, "low": 99.90, "close": 100.03, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:50:00"),
        )
        assert _is_valid_retest_long(bar, or_high) == True

    def test_retest_long_rejected_low_above_or_high(self, or_high):
        bar = pd.Series(
            {"open": 100.05, "high": 100.10, "low": 100.05, "close": 100.08, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:50:00"),
        )
        assert _is_valid_retest_long(bar, or_high) == False

    def test_valid_retest_short_high_touches_or_low(self, or_low):
        bar = pd.Series(
            {"open": 98.95, "high": 99.05, "low": 98.95, "close": 98.90, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:50:00"),
        )
        assert _is_valid_retest_short(bar, or_low) == True

    def test_retest_short_rejected_high_below_or_low(self, or_low):
        bar = pd.Series(
            {"open": 98.95, "high": 98.99, "low": 98.90, "close": 98.92, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:50:00"),
        )
        assert _is_valid_retest_short(bar, or_low) == False


class TestFullBodyBreakout:
    def test_full_body_breakout_long_above_or_high(self, or_high):
        bar = pd.Series(
            {"open": 100.10, "high": 100.30, "low": 100.05, "close": 100.25, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_full_body_breakout_long(bar, or_high) == True

    def test_full_body_breakout_long_wick_only_rejected(self, or_high):
        bar = pd.Series(
            {"open": 99.90, "high": 100.10, "low": 99.85, "close": 99.92, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_full_body_breakout_long(bar, or_high) == False

    def test_full_body_breakout_short_below_or_low(self, or_low):
        bar = pd.Series(
            {"open": 98.85, "high": 98.95, "low": 98.80, "close": 98.82, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_full_body_breakout_short(bar, or_low) == True

    def test_full_body_breakout_short_wick_only_rejected(self, or_low):
        bar = pd.Series(
            {"open": 99.10, "high": 99.15, "low": 98.90, "close": 99.05, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_full_body_breakout_short(bar, or_low) == False


class TestEdgeCases:
    def test_zero_range_bar_hammer(self):
        bar = pd.Series(
            {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_hammer(bar) == False

    def test_zero_range_bar_engulfing(self):
        prior = pd.Series(
            {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:44:00"),
        )
        current = pd.Series(
            {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 100000.0},
            name=pd.Timestamp("2024-01-15 09:45:00"),
        )
        assert _is_bullish_engulfing(current, prior) == False
