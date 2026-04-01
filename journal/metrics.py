"""
journal/metrics.py
==================
Computes performance metrics from a list of TradeResult objects.

Metrics are computed independently for 2R and 3R reward targets
to enable direct comparison.  All figures are net of commissions
(P&L values on TradeResult are already net of commission at resolve time).
"""

import math
from typing import Dict, List, Optional

import pandas as pd

from data.models import TradeResult


def compute_metrics(
    trades: List[TradeResult],
    starting_capital: float,
    target: str = "2r",   # "2r" or "3r"
) -> dict:
    """
    Compute the full suite of performance metrics for a list of trades.

    Parameters
    ----------
    trades          : List of resolved TradeResult objects.
    starting_capital: Account equity at the start of the period.
    target          : Which R target to evaluate ('2r' or '3r').
    """
    if not trades:
        return _empty_metrics()

    pnl_attr    = f"pnl_{target}"
    outcome_attr = f"outcome_{target}"

    pnls     = [getattr(t, pnl_attr) or 0.0 for t in trades]
    outcomes = [getattr(t, outcome_attr) or "loss" for t in trades]

    wins   = [p for p, o in zip(pnls, outcomes) if o == "win"]
    losses = [p for p, o in zip(pnls, outcomes) if o == "loss"]

    total_trades  = len(trades)
    win_count     = len(wins)
    loss_count    = len(losses)
    win_rate      = win_count / total_trades if total_trades else 0.0

    gross_profit  = sum(w for w in wins   if w > 0)
    gross_loss    = abs(sum(l for l in losses if l < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    net_pnl  = sum(pnls)
    avg_win  = (gross_profit / win_count)  if win_count  else 0.0
    avg_loss = (gross_loss   / loss_count) if loss_count else 0.0

    # Equity curve for drawdown calculation
    equity_curve = _build_equity_curve(pnls, starting_capital)
    max_drawdown, max_drawdown_pct = _max_drawdown(equity_curve)

    # Sharpe ratio (annualised, assuming ~252 trading sessions/year)
    sharpe = _sharpe(pnls)

    # Per-mode breakdown
    modes = {}
    for mode in ("breakout", "manipulation", "mean_reversion"):
        mode_trades = [t for t in trades if t.mode == mode]
        if mode_trades:
            mode_pnls = [getattr(t, pnl_attr) or 0.0 for t in mode_trades]
            mode_wins = sum(1 for t in mode_trades if getattr(t, outcome_attr) == "win")
            modes[mode] = {
                "trades":   len(mode_trades),
                "wins":     mode_wins,
                "win_rate": round(mode_wins / len(mode_trades), 4),
                "net_pnl":  round(sum(mode_pnls), 4),
            }

    # Per-instrument breakdown
    instruments = {}
    for sym in set(t.instrument for t in trades):
        sym_trades = [t for t in trades if t.instrument == sym]
        sym_pnls   = [getattr(t, pnl_attr) or 0.0 for t in sym_trades]
        sym_wins   = sum(1 for t in sym_trades if getattr(t, outcome_attr) == "win")
        instruments[sym] = {
            "trades":   len(sym_trades),
            "wins":     sym_wins,
            "win_rate": round(sym_wins / len(sym_trades), 4),
            "net_pnl":  round(sum(sym_pnls), 4),
        }

    return {
        "target":           target,
        "total_trades":     total_trades,
        "wins":             win_count,
        "losses":           loss_count,
        "win_rate":         round(win_rate, 4),
        "gross_profit":     round(gross_profit, 4),
        "gross_loss":       round(gross_loss, 4),
        "net_pnl":          round(net_pnl, 4),
        "profit_factor":    round(profit_factor, 4) if profit_factor else None,
        "avg_win":          round(avg_win, 4),
        "avg_loss":         round(avg_loss, 4),
        "max_drawdown":     round(max_drawdown, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "sharpe_ratio":     round(sharpe, 4) if sharpe else None,
        "equity_curve":     equity_curve,
        "by_mode":          modes,
        "by_instrument":    instruments,
    }


def compare_targets(
    trades: List[TradeResult],
    starting_capital: float,
) -> dict:
    """Return side-by-side metrics for 2R and 3R for the same trade list."""
    return {
        "2r": compute_metrics(trades, starting_capital, "2r"),
        "3r": compute_metrics(trades, starting_capital, "3r"),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_equity_curve(pnls: List[float], starting_capital: float) -> List[float]:
    curve = [starting_capital]
    equity = starting_capital
    for p in pnls:
        equity += p
        curve.append(round(equity, 4))
    return curve


def _max_drawdown(equity_curve: List[float]):
    if len(equity_curve) < 2:
        return 0.0, 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = peak - v
        dd_pct = dd / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
    return max_dd, max_dd_pct


def _sharpe(pnls: List[float], periods_per_year: int = 252) -> Optional[float]:
    if len(pnls) < 2:
        return None
    mean = sum(pnls) / len(pnls)
    variance = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (mean / std) * math.sqrt(periods_per_year)


def _empty_metrics() -> dict:
    return {
        "target": "", "total_trades": 0, "wins": 0, "losses": 0,
        "win_rate": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
        "net_pnl": 0.0, "profit_factor": None, "avg_win": 0.0, "avg_loss": 0.0,
        "max_drawdown": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": None,
        "equity_curve": [], "by_mode": {}, "by_instrument": {},
    }
