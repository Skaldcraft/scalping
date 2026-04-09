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

import pandas as pd

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

    gate_status_counts = _build_gate_status_counts(log_entries)

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
            "gate_status_counts":       gate_status_counts,
        },
        "sessions": log_entries,
    }

    path = run_dir / "execution_log.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    diagnostics_rows = _build_diagnostics_rows(log_entries)
    diagnostics_path = run_dir / "execution_diagnostics.csv"
    pd.DataFrame(diagnostics_rows).to_csv(diagnostics_path, index=False)

    log.info(
        "Execution log saved: %s (%d sessions, %d trades). Diagnostics: %s",
        path, total, executed, diagnostics_path,
    )
    return path


# ---------------------------------------------------------------------------
# Entry builder
# ---------------------------------------------------------------------------

def _build_entry(s: SessionSummary, trade_index: Dict[str, TradeResult]) -> dict:
    gate_trace = _build_gate_trace(s)

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
            "trend_aligned":     s.trend_aligned,
            "dxy_filter_confirmed": s.dxy_filter_confirmed,
            "trigger_candle":    s.trigger_candle,
        },
        "decision_trace":        gate_trace,
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
            "one_r_target":  t.one_r_target,
            "partial_scale_pct": t.partial_scale_pct,
            "partial_exit_time": t.partial_exit_time,
            "partial_exit_price": t.partial_exit_price,
            "stop_moved_to_be": t.stop_moved_to_be,
            "pattern":       t.pattern_detected,
            "exit_reason":   t.exit_reason,
            "outcome_2r":    t.outcome_2r,
            "pnl_2r":        t.pnl_2r,
            "outcome_3r":    t.outcome_3r,
            "pnl_3r":        t.pnl_3r,
        }

    entry["reasoning_and_logic"] = _reasoning_and_logic(entry)

    return entry


def _reasoning_and_logic(entry: dict) -> str:
    phase0 = entry.get("phase_0") or {}
    phase1 = entry.get("phase_1") or {}
    reasons = entry.get("rejection_reasons") or []

    if entry.get("trade_executed"):
        if bool(phase1.get("retest_confirmed")):
            return (
                "The system saw a valid touch-and-turn retest, confirming the Slingshot effect before committing capital."
            )
        if str(phase1.get("trigger_candle", "")).lower() == "displacement_gap":
            return (
                "The system detected aggressive institutional momentum through a displacement gap and allowed continuation execution."
            )
        return (
            "The session passed the active structure and safety gates, so the system executed within base-hit risk controls."
        )

    if bool(phase0.get("manipulation_flagged")):
        return (
            "The opening range signaled institutional engineering, but the follow-through confirmation was not strong enough for a safe entry."
        )

    if any(str(r).startswith("trend_not_aligned") for r in reasons):
        return (
            "The setup was skipped because the small-timeframe move did not align with the higher-timeframe trend wind at our back."
        )

    if any(str(r) == "displacement_gap_min_body_not_met" for r in reasons) or any(
        str(r) == "displacement_gap_min_size_not_met" for r in reasons
    ):
        return (
            "The system detected a potential move, but the footprint was too light: candle body strength or displacement size did not show solid institutional intent."
        )

    if any(str(r) == "no_signal_found" for r in reasons):
        return (
            "The utility stayed patient because no clean trigger appeared; this avoids forced entries during noisy, unrewarding tape."
        )

    if any(str(r) == "outside_fib_zone" for r in reasons):
        return (
            "Price location was outside the preferred value zone, so the setup was filtered to avoid chasing extended conditions."
        )

    if any(str(r) == "circuit_breaker_active" for r in reasons):
        return (
            "The system safety lock was active, so execution was intentionally blocked to protect simulated capital."
        )

    return "No qualifying setup reached execution quality thresholds during this session."


def _build_gate_trace(s: SessionSummary) -> List[dict]:
    reasons = s.rejection_reasons or []

    def _failed_exact(reason: str) -> bool:
        return reason in reasons

    def _failed_prefix(prefix: str) -> bool:
        return any(r.startswith(prefix) for r in reasons)

    trace = [
        {
            "order": 1,
            "gate": "safety_lock",
            "status": "failed" if _failed_exact("circuit_breaker_active") else "passed",
            "detail": "daily loss and global breaker checks",
        },
        {
            "order": 2,
            "gate": "trend_alignment",
            "status": "failed" if _failed_prefix("trend_not_aligned") else ("passed" if s.trend_aligned else "skipped"),
            "detail": "1m EMA100 + 5m/15m EMA20/50 direction agreement",
        },
        {
            "order": 3,
            "gate": "dxy_filter",
            "status": "failed" if _failed_prefix("dxy_filter_rejected") else ("passed" if s.dxy_filter_confirmed else "skipped"),
            "detail": "external DXY correlation filter for mapped forex pairs",
        },
        {
            "order": 4,
            "gate": "trigger_candle",
            "status": "passed" if bool(s.trigger_candle) else "skipped",
            "detail": s.trigger_candle or "no trigger recorded",
        },
        {
            "order": 5,
            "gate": "fibonacci_zone",
            "status": "failed" if _failed_exact("outside_fib_zone") else "passed",
            "detail": "cheap-zone buys and expensive-zone sells",
        },
        {
            "order": 6,
            "gate": "execution",
            "status": "passed" if s.trade_executed else "failed",
            "detail": "trade submitted only when all required gates pass",
        },
    ]

    return trace


def _build_gate_status_counts(log_entries: List[dict]) -> Dict[str, Dict[str, int]]:
    gate_counts: Dict[str, Dict[str, int]] = {}
    for e in log_entries:
        for gate in e.get("decision_trace", []):
            gate_name = str(gate.get("gate", "unknown"))
            status = str(gate.get("status", "unknown"))
            gate_counts.setdefault(gate_name, {"passed": 0, "failed": 0, "skipped": 0, "unknown": 0})
            if status not in gate_counts[gate_name]:
                gate_counts[gate_name][status] = 0
            gate_counts[gate_name][status] += 1

    for gate_name, counts in gate_counts.items():
        gate_counts[gate_name] = dict(sorted(counts.items(), key=lambda kv: kv[0]))

    return dict(sorted(gate_counts.items(), key=lambda kv: kv[0]))


def _build_diagnostics_rows(log_entries: List[dict]) -> List[dict]:
    rows: List[dict] = []
    for e in log_entries:
        row = {
            "session_date": e.get("session_date"),
            "instrument": e.get("instrument"),
            "trade_executed": e.get("trade_executed", False),
            "trade_id": e.get("trade_id"),
            "mode_activated": (e.get("phase_1") or {}).get("mode_activated"),
            "trigger_candle": (e.get("phase_1") or {}).get("trigger_candle"),
            "rejection_reasons": "; ".join(e.get("rejection_reasons", [])),
            "Reasoning and Logic": e.get("reasoning_and_logic", ""),
        }

        for gate in e.get("decision_trace", []):
            gate_name = str(gate.get("gate", "unknown"))
            row[f"gate_{gate_name}"] = gate.get("status")

        trade_detail = e.get("trade_detail") or {}
        row["direction"] = trade_detail.get("direction")
        row["entry_price"] = trade_detail.get("entry_price")
        row["stop_loss"] = trade_detail.get("stop_loss")
        row["tp_2r"] = trade_detail.get("tp_2r")
        row["tp_3r"] = trade_detail.get("tp_3r")
        row["one_r_target"] = trade_detail.get("one_r_target")
        row["partial_scale_pct"] = trade_detail.get("partial_scale_pct")
        row["partial_exit_time"] = trade_detail.get("partial_exit_time")
        row["partial_exit_price"] = trade_detail.get("partial_exit_price")
        row["stop_moved_to_be"] = trade_detail.get("stop_moved_to_be")

        rows.append(row)

    return rows
