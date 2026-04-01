"""
backtest_job.py
===============
Shared orchestration for a single backtest run.

Both the interactive CLI and the unattended daily runner use this module so
artifact generation stays consistent.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import yaml

from engine.backtester import Backtester
from journal.execution_log import generate_execution_log
from journal.metrics import compare_targets
from journal.recorder import JournalRecorder
from journal.run_report import generate_run_report

log = logging.getLogger(__name__)


def load_config(config_path: str | Path) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_backtest_job(
    cfg: dict,
    start_date: date,
    end_date: date,
    config_path: str | Path,
    results_dir: str | Path = "results",
) -> dict:
    bt = Backtester(cfg)
    result = bt.run(start_date, end_date)

    all_trades = [t for trades in result.instrument_results.values() for t in trades]

    version = cfg.get("version", "1.0")
    recorder = JournalRecorder(results_dir=str(results_dir), version=version, config=cfg)

    trade_log_path = recorder.save_trade_log(result.instrument_results)
    session_log_path = recorder.save_session_log(result.session_summaries)
    config_snapshot_path = recorder.save_config_snapshot()
    changelog_path = recorder.save_changelog_snapshot(Path(config_path).parent / "changelog.md")

    comparison = compare_targets(all_trades, cfg["account"]["starting_capital"])
    metrics_2r = comparison["2r"]
    metrics_3r = comparison["3r"]

    report_path = generate_run_report(
        instrument_results=result.instrument_results,
        session_summaries=result.session_summaries,
        metrics_2r=metrics_2r,
        metrics_3r=metrics_3r,
        circuit_halt_events=[],
        config=cfg,
        start_date=str(start_date),
        end_date=str(end_date),
        version=version,
        run_dir=recorder.directory,
    )

    exec_log_path = generate_execution_log(
        session_summaries=result.session_summaries,
        instrument_results=result.instrument_results,
        run_dir=recorder.directory,
        version=version,
        config=cfg,
        start_date=str(start_date),
        end_date=str(end_date),
    )

    return {
        "config": cfg,
        "result": result,
        "all_trades": all_trades,
        "comparison": comparison,
        "metrics_2r": metrics_2r,
        "metrics_3r": metrics_3r,
        "recorder": recorder,
        "trade_log_path": trade_log_path,
        "session_log_path": session_log_path,
        "config_snapshot_path": config_snapshot_path,
        "changelog_path": changelog_path,
        "report_path": report_path,
        "exec_log_path": exec_log_path,
    }
