"""
tests/test_validation.py
=====================
Tests for config validation in backtest_job.py.
"""

import pytest
from backtest_job import validate_config, ConfigValidationError, load_config


def _minimal_cfg(overrides: dict | None = None) -> dict:
    """Minimal valid config for testing."""
    cfg = {
        "version": "1.0",
        "account": {
            "starting_capital": 10000,
            "risk_per_trade_pct": 1.0,
            "daily_loss_limit_pct": 5.0,
        },
        "session": {
            "start_time": "09:30",
            "end_time": "11:00",
            "timezone": "America/New_York",
        },
        "opening_range": {
            "candle_size_minutes": 15,
        },
        "strategy": {
            "execution_timeframe_minutes": 1,
            "atr_period": 14,
            "manipulation_threshold_pct": 25.0,
            "reward_ratios": [2, 3],
            "trend_mode": {
                "allow_displacement_gap_entry": True,
                "entry_priority": "retest_first",
                "displacement_min_atr_pct": 3.0,
                "displacement_min_body_pct": 60.0,
            },
        },
        "risk": {
            "profit_factor_floor": 1.5,
            "min_trades_before_pf_check": 10,
        },
        "instruments": {"equities": ["AAPL"]},
        "pre_session": {"enabled": False},
        "commissions": {"per_trade_flat": 0.50},
    }
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    return cfg


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Shallow merge for test overrides."""
    result = base.copy()
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class TestValidateConfig:
    def test_valid_config_passes(self):
        cfg = _minimal_cfg()
        validate_config(cfg)

    def test_displacement_min_atr_pct_150_raises(self):
        cfg = _minimal_cfg({
            "strategy": {"trend_mode": {"displacement_min_atr_pct": 150.0}}
        })
        with pytest.raises(ConfigValidationError, match="displacement_min_atr_pct"):
            validate_config(cfg)

    def test_displacement_min_body_pct_negative_raises(self):
        cfg = _minimal_cfg({
            "strategy": {"trend_mode": {"displacement_min_body_pct": -5.0}}
        })
        with pytest.raises(ConfigValidationError, match="displacement_min_body_pct"):
            validate_config(cfg)

    def test_displacement_min_atr_pct_zero_logs_warning(self):
        cfg = _minimal_cfg({
            "strategy": {"trend_mode": {"displacement_min_atr_pct": 0.0}}
        })
        validate_config(cfg)

    def test_risk_per_trade_pct_zero_raises(self):
        cfg = _minimal_cfg({
            "account": {"risk_per_trade_pct": 0.0}
        })
        with pytest.raises(ConfigValidationError, match="risk_per_trade_pct"):
            validate_config(cfg)

    def test_risk_per_trade_pct_exceeds_max_raises(self):
        cfg = _minimal_cfg({
            "account": {"risk_per_trade_pct": 10.0}
        })
        with pytest.raises(ConfigValidationError, match="risk_per_trade_pct"):
            validate_config(cfg)

    def test_daily_loss_limit_too_high_raises(self):
        cfg = _minimal_cfg({
            "account": {"daily_loss_limit_pct": 50.0}
        })
        with pytest.raises(ConfigValidationError, match="daily_loss_limit_pct"):
            validate_config(cfg)

    def test_pf_floor_too_low_raises(self):
        cfg = _minimal_cfg({
            "risk": {"profit_factor_floor": 0.1}
        })
        with pytest.raises(ConfigValidationError, match="profit_factor_floor"):
            validate_config(cfg)

    def test_missing_field_raises(self):
        cfg = _minimal_cfg()
        del cfg["strategy"]["trend_mode"]["displacement_min_atr_pct"]
        with pytest.raises(ConfigValidationError, match="displacement_min_atr_pct"):
            validate_config(cfg)

    def test_non_numeric_value_raises(self):
        cfg = _minimal_cfg({
            "strategy": {"trend_mode": {"displacement_min_atr_pct": "invalid"}}
        })
        with pytest.raises(ConfigValidationError, match="must be numeric"):
            validate_config(cfg)

    def test_boundary_values_pass(self):
        cfg = _minimal_cfg({
            "strategy": {"trend_mode": {"displacement_min_atr_pct": 0.0}},
            "account": {
                "risk_per_trade_pct": 0.1,
                "daily_loss_limit_pct": 0.5,
            },
            "risk": {"profit_factor_floor": 0.5},
        })
        validate_config(cfg)

        cfg2 = _minimal_cfg({
            "strategy": {"trend_mode": {
                "displacement_min_atr_pct": 100.0,
                "displacement_min_body_pct": 100.0,
            }},
            "account": {
                "risk_per_trade_pct": 5.0,
                "daily_loss_limit_pct": 20.0,
            },
            "risk": {"profit_factor_floor": 5.0},
        })
        validate_config(cfg2)
