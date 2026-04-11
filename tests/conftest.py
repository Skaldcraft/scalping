"""
tests/conftest.py
=================
Shared pytest fixtures for synthetic OHLCV data and common test utilities.
"""

import pandas as pd
from datetime import datetime, time
import pytest


def _make_bar(
    timestamp: str,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100000.0,
) -> pd.Series:
    """Create a single OHLCV bar as a pandas Series."""
    return pd.Series(
        {"open": open, "high": high, "low": low, "close": close, "volume": volume},
        name=pd.Timestamp(timestamp),
    )


@pytest.fixture
def hammer_bar():
    """Valid bullish hammer: small body near top, long lower wick.
    Body ≤35% of range, lower wick ≥60% of range.
    """
    return _make_bar("2024-01-15 09:45:00", open=100.10, high=100.50, low=99.00, close=100.15)


@pytest.fixture
def inverted_hammer_bar():
    """Valid inverted hammer: small body near bottom, long upper wick.
    Body ≤35% of range, upper wick ≥60% of range.
    """
    return _make_bar("2024-01-15 09:45:00", open=100.00, high=101.50, low=100.05, close=100.10)


@pytest.fixture
def bullish_engulfing_prior():
    """Prior BEARISH bar for bullish engulfing pattern test."""
    return _make_bar("2024-01-15 09:44:00", open=100.30, high=100.35, low=99.80, close=99.85)


@pytest.fixture
def bullish_engulfing_current(bullish_engulfing_prior):
    """Current BULLISH bar that engulfs the prior bearish bar.

    Must satisfy: current.close > prior.open AND current.open < prior.close.
    """
    return _make_bar(
        "2024-01-15 09:45:00",
        open=99.80,
        high=100.50,
        low=99.75,
        close=100.40,
    )
    # bullish_engulfing_prior = open=100.30, close=99.85 (bearish)
    # current.close=100.40 > prior.open=100.30 ✓
    # current.open=99.80 < prior.close=99.85 ✓


@pytest.fixture
def bearish_engulfing_prior():
    """Prior BULLISH bar for bearish engulfing pattern test."""
    return _make_bar("2024-01-15 09:44:00", open=100.00, high=100.35, low=99.95, close=100.30)


@pytest.fixture
def bearish_engulfing_current(bearish_engulfing_prior):
    """Current BEARISH bar that engulfs the prior bullish bar."""
    return _make_bar(
        "2024-01-15 09:45:00",
        open=100.35,
        high=100.40,
        low=99.10,
        close=99.50,
    )


@pytest.fixture
def non_hammer_bar():
    """A normal candle that should NOT be detected as a hammer."""
    return _make_bar("2024-01-15 09:45:00", open=100.00, high=100.40, low=99.80, close=100.20)


@pytest.fixture
def full_body_bullish_bar():
    """Full bullish candle for breakout detection."""
    return _make_bar("2024-01-15 09:45:00", open=99.50, high=100.20, low=99.45, close=100.15)


@pytest.fixture
def full_body_bearish_bar():
    """Full bearish candle for breakout detection."""
    return _make_bar("2024-01-15 09:45:00", open=100.50, high=100.55, low=99.80, close=99.85)


@pytest.fixture
def doji_bar():
    """Doji with equal open/close — should NOT be a hammer."""
    return _make_bar("2024-01-15 09:45:00", open=100.00, high=100.10, low=99.90, close=100.00)


@pytest.fixture
def or_high():
    """Opening range high for retest detection tests."""
    return 100.00


@pytest.fixture
def or_low():
    """Opening range low for retest detection tests."""
    return 99.00
