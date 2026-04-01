"""
journal/execution_log.py
========================
Records a machine-readable, per-session audit trail of every decision
the utility made during a backtest run.

Unlike the trade log (which records only executed trades), the execution
log records ALL sessions — including those where no signal was found —
capturing the full decision chain from opening range calculation through
to trade entry or rejection reason.

This log is the primary tool for diagnosing why specific sessions
produced no trade and for identifying systematic gaps in the strategy's
filtering logic.

Output: results/<run>/execution_log.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from data.models import SessionSummary, TradeResult

log = logging.getLogger(__name__)


def generate_execution_log(
    session_summaries:   Dict[str, List[SessionSummary]],
    instrument_results:  Dict[str, List[TradeResult]],
    run_dir:             Path,
    version:             str,
    config:              dict,
    start_date:          str,
    end_date:            str,
) -> Path:
    """
    Builds and saves the execution log as a structured JSON file.

    Parameters
    ----------
    session_summaries  : Per-instrument list of SessionSummary objects.
    instrument_results : Per-instrument list of TradeResult objects.
    run_dir            : Output directory for this run.
    version            : Config version string.
    config             : Full configuration dict (embedded for traceability).
    start_date         : Backtest start date string.
    end_date           : Backtest end date string.
    """
    # Index trades by trade_id for quick lookup
    trade_index: Dict[str, TradeResult] = {}
    for trades in instrument_results.values():
        for t in trades:
            trade_index[t.trade_id] = t

    # Build log
    log_entries = []
    for sym, summaries in session_summaries.items():
        for s in summaries:
            entry = _build_entry(s, trade_index)
            log_entries.append(entry)

    # Sort chronologically
    log_entries.sort(key=lambda e: (e["session_date"], e["instrument"]))

    # Aggregate statistics for header
    total     = len(log_entries)
    executed  = sum(1 for e in log_entries if e["trade_executed"])
    no_signal = sum(1 for e in log_entries if not e["trade_executed"])
    manip     = sum(
        1 for e in log_entries if e.get("phase_0", {}).get("manipulation_flagged")
    )

    # Rejection reason frequency
    rejection_counts: Dict[str, int] = {}
    for e in log_entries:
        for r in e.get("rejection_reasons", []):
            rejection_counts[r] = rejection_counts.get(r, 0) + 1
    rejection_counts = dict(
        sorted(rejection_counts.items(), key=lambda x: x[1], reverse=True)
    )

    output = {
        "meta": {
            "utility":          "Precision Scalping Utility",
            "version":          version,
            "generated_at":     datetime.now().isoformat(),
            "backtest_period":  f"{start_date} to {end_date}",
            "instruments":      list(session_summaries.keys()),
            "config_summary": {
                "or_minutes":             config["opening_range"]["candle_size_minutes"],
                "atr_manipulation_pct":   config["strategy"]["manipulation_threshold_pct"],
                "risk_per_trade_pct":     config["account"]["risk_per_trade_pct"],
                "daily_loss_limit_pct":   config["account"]["daily_loss_limit_pct"],
                "session_window":         f"{config['session']['start_time']}–{config['session']['end_time']}",
            },
        },
        "aggregate": {
            "total_sessions":           total,
            "sessions_with_trade":      executed,
            "sessions_without_trade":   no_signal,
            "signal_rate_pct":          round(executed / total * 100, 1) if total else 0,
            "manipulation_sessions":    manip,
            "manipulation_rate_pct":    round(manip / total * 100, 1) if total else 0,
            "rejection_reason_counts":  rejection_counts,
        },
        "sessions": log_entries,
    }

    path = run_dir / "execution_log.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    log.info(
        "Execution log saved: %s (%d sessions, %d trades)",
        path, total, executed,
    )
    return path


# ---------------------------------------------------------------------------
# Entry builder
# ---------------------------------------------------------------------------

def _build_entry(s: SessionSummary, trade_index: Dict[str, TradeResult]) -> dict:
    entry = {
        "session_date":          s.session_date,
        "instrument":            s.instrument,
        "phase_0": {
            "or_high":           s.or_high,
            "or_low":            s.or_low,
            "or_midpoint":       s.or_midpoint,
            "or_range":          round(s.or_high - s.or_low, 6) if s.or_high else 0,
            "atr_14":            s.atr_14,
            "atr_threshold":     round(s.atr_14 * 0.25, 6) if s.atr_14 else 0,
            "manipulation_flagged": s.manipulation_flagged,
        },
        "phase_1": {
            "mode_activated":    s.mode_activated,
            "breakout_fired":    s.breakout_signal_fired,
            "retest_confirmed":  s.retest_confirmed,
            "pattern_confirmed": s.pattern_confirmed,
        },
        "trade_executed":        s.trade_executed,
        "rejection_reasons":     s.rejection_reasons,
        "trade_id":              s.trade_id,
        "trade_detail":          None,
    }

    # If a trade was executed, embed a compact trade summary
    if s.trade_id and s.trade_id in trade_index:
        t = trade_index[s.trade_id]
        entry["trade_detail"] = {
            "mode":          t.mode,
            "direction":     t.direction,
            "entry_price":   t.entry_price,
            "stop_loss":     t.stop_loss,
            "tp_2r":         t.take_profit_2r,
            "tp_3r":         t.take_profit_3r,
            "pattern":       t.pattern_detected,
            "exit_reason":   t.exit_reason,
            "outcome_2r":    t.outcome_2r,
            "pnl_2r":        t.pnl_2r,
            "outcome_3r":    t.outcome_3r,
            "pnl_3r":        t.pnl_3r,
        }

    return entry
