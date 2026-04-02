"""
backtest_job.py
===============
Shared orchestration for a single backtest run.

Both the interactive CLI and the unattended daily runner use this module so
artifact generation stays consistent.
"""

from __future__ import annotations

import copy
import json
import logging
from datetime import date
from pathlib import Path

import yaml

from engine.backtester import Backtester
from journal.execution_log import generate_execution_log
from journal.metrics import compare_targets
from journal.recorder import JournalRecorder
from journal.run_report import generate_run_report
from selector.pre_session_selector import run_pre_session_selection
from selector.provider import DefaultSelectionProvider

log = logging.getLogger(__name__)


def _load_frozen_selection(snapshot_path: Path) -> dict | None:
    if not snapshot_path.exists():
        return None
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.warning("Failed to load frozen selection %s: %s", snapshot_path, exc)
        return None


def _save_frozen_selection(snapshot_path: Path, snapshot: dict) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


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
    run_cfg = copy.deepcopy(cfg)
    selection_snapshot = None
    selection_snapshot_source = None

    pre_cfg = run_cfg.get("pre_session", {})
    if pre_cfg.get("enabled", False):
        rules = pre_cfg.get("selection_rules", {})

        freeze_daily_selection = bool(pre_cfg.get("freeze_daily_selection", False))
        frozen_dir_raw = pre_cfg.get("frozen_selection_dir")
        if frozen_dir_raw:
            frozen_dir = Path(str(frozen_dir_raw))
        else:
            frozen_dir = Path(results_dir) / "_selection_state"
        frozen_path = frozen_dir / f"selection_{start_date.isoformat()}.json"

        if freeze_daily_selection:
            selection_snapshot = _load_frozen_selection(frozen_path)
            if selection_snapshot is not None:
                selection_snapshot_source = "frozen"
                log.info("Loaded frozen pre-session selection: %s", frozen_path)

        provider = DefaultSelectionProvider(
            cfg=run_cfg,
            results_dir=results_dir,
            atr_period=run_cfg.get("strategy", {}).get("atr_period", 14),
            min_trades_for_pf=int(rules.get("min_trades_for_pf", 10)),
            pf_lookback_trades=rules.get("pf_lookback_trades"),
        )

        if selection_snapshot is None:
            selection_snapshot = run_pre_session_selection(run_cfg, start_date, provider)
            selection_snapshot_source = "computed"
            if freeze_daily_selection:
                _save_frozen_selection(frozen_path, selection_snapshot)
                log.info("Saved frozen pre-session selection: %s", frozen_path)

        selected_symbols = selection_snapshot.get("selected_symbols", [])
        if selected_symbols:
            run_cfg.setdefault("instruments", {})["equities"] = selected_symbols
            log.info(
                "Pre-session selection enabled (%s). Selected symbols: %s",
                selection_snapshot_source,
                selected_symbols,
            )
        elif pre_cfg.get("fallback_to_config_instruments", True):
            log.warning(
                "Pre-session selection returned no symbols. Falling back to configured instruments."
            )
        else:
            run_cfg.setdefault("instruments", {})["equities"] = []
            log.warning(
                "Pre-session selection returned no symbols and fallback is disabled."
            )

    bt = Backtester(run_cfg)
    result = bt.run(start_date, end_date)

    all_trades = [t for trades in result.instrument_results.values() for t in trades]

    version = run_cfg.get("version", "1.0")
    recorder = JournalRecorder(results_dir=str(results_dir), version=version, config=run_cfg)

    trade_log_path = recorder.save_trade_log(result.instrument_results)
    session_log_path = recorder.save_session_log(result.session_summaries)
    config_snapshot_path = recorder.save_config_snapshot()
    changelog_path = recorder.save_changelog_snapshot(Path(config_path).parent / "changelog.md")

    selection_snapshot_paths = None
    selection_report_path = None
    if selection_snapshot:
        selection_snapshot_paths = recorder.save_selection_snapshot(selection_snapshot)
        selection_report_path = recorder.save_selection_report(selection_snapshot)

    comparison = compare_targets(all_trades, run_cfg["account"]["starting_capital"])
    metrics_2r = comparison["2r"]
    metrics_3r = comparison["3r"]

    report_path = generate_run_report(
        instrument_results=result.instrument_results,
        session_summaries=result.session_summaries,
        metrics_2r=metrics_2r,
        metrics_3r=metrics_3r,
        circuit_halt_events=[],
        config=run_cfg,
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
        config=run_cfg,
        start_date=str(start_date),
        end_date=str(end_date),
    )

    return {
        "config": run_cfg,
        "original_config": cfg,
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
        "selection_snapshot": selection_snapshot,
        "selection_snapshot_source": selection_snapshot_source,
        "selection_snapshot_paths": selection_snapshot_paths,
        "selection_report_path": selection_report_path,
    }
