"""
weekly_batch.py
===============
Runs the strategy week by week across a date range and builds a rolling
weekly report from the saved run artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest_job import load_config, run_backtest_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("weekly_batch")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precision Scalping Utility — weekly batch runner"
    )
    parser.add_argument("--start", required=True, help="Batch start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Batch end date (YYYY-MM-DD)")
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to settings YAML file (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Root folder for batch outputs (default: results)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def split_into_calendar_weeks(start_date: date, end_date: date) -> list[tuple[date, date]]:
    weeks = []
    current = start_date
    while current <= end_date:
        days_until_sunday = 6 - current.weekday()
        week_end = min(current + timedelta(days=days_until_sunday), end_date)
        weeks.append((current, week_end))
        current = week_end + timedelta(days=1)
    return weeks


def status_label(metrics: dict, review_cfg: dict) -> str:
    min_trades = int(review_cfg.get("min_trades_for_setup_review", 10))
    if metrics.get("total_trades", 0) < min_trades:
        return "Too little data"

    win_rate_pct = metrics.get("win_rate", 0) * 100
    pf = metrics.get("profit_factor") or 0.0
    dd_pct = metrics.get("max_drawdown_pct", 0) * 100

    if (
        win_rate_pct >= float(review_cfg.get("good_win_rate_pct", 60.0))
        and pf >= float(review_cfg.get("good_profit_factor", 1.5))
        and dd_pct <= float(review_cfg.get("good_drawdown_pct", 3.0))
    ):
        return "Good"
    if (
        win_rate_pct >= float(review_cfg.get("mixed_win_rate_pct", 45.0))
        and pf >= float(review_cfg.get("mixed_profit_factor", 1.0))
        and dd_pct <= float(review_cfg.get("mixed_drawdown_pct", 5.0))
    ):
        return "Mixed"
    return "Weak"


def mean_safe(items, key):
    values = [item.get(key) for item in items if item.get(key) is not None]
    if not values:
        return None
    return round(mean(values), 2)


def summarize_week(week_start: date, week_end: date, run_data: dict, cfg: dict) -> dict:
    result = run_data["result"]
    metrics_2r = run_data["metrics_2r"]
    metrics_3r = run_data["metrics_3r"]
    review_cfg = cfg.get("weekly_review", {}) or {}
    by_mode = metrics_2r.get("by_mode", {}) or {}
    by_inst = metrics_2r.get("by_instrument", {}) or {}

    best_mode = None
    weakest_mode = None
    if by_mode:
        ranked = sorted(by_mode.items(), key=lambda item: item[1].get("net_pnl", 0), reverse=True)
        best_mode = ranked[0][0]
        weakest_mode = ranked[-1][0]

    best_symbol = None
    weakest_symbol = None
    if by_inst:
        ranked_symbols = sorted(by_inst.items(), key=lambda item: item[1].get("net_pnl", 0), reverse=True)
        best_symbol = ranked_symbols[0][0]
        weakest_symbol = ranked_symbols[-1][0]

    status = status_label(metrics_2r, review_cfg)
    sessions = sum(len(v) for v in result.session_summaries.values())
    total_trades = metrics_2r.get("total_trades", 0)
    pf2 = metrics_2r.get("profit_factor")
    pf3 = metrics_3r.get("profit_factor")

    if pf2 is not None:
        highlight = (
            f"This week reviewed {sessions} sessions and {total_trades} trades. "
            f"Win rate was {metrics_2r.get('win_rate', 0)*100:.1f}%, profit factor was {pf2:.3f}."
        )
    else:
        highlight = (
            f"This week reviewed {sessions} sessions and {total_trades} trades. "
            f"Win rate was {metrics_2r.get('win_rate', 0)*100:.1f}%.")

    takeaway = [
        f"The week is classified as {status.lower()}.",
        f"Best setup: {best_mode.replace('_', ' ').title()}" if best_mode else "Best setup: not enough data.",
        f"Weakest setup: {weakest_mode.replace('_', ' ').title()}" if weakest_mode else "Weakest setup: not enough data.",
    ]

    watch = [
        f"Watch whether {best_symbol} stays the strongest symbol." if best_symbol else "Watch symbol performance as more data accumulates.",
        f"Watch whether {weakest_symbol} improves or stays weak." if weakest_symbol else "Watch whether the weaker setup improves.",
        "Watch whether win rate and profit factor stay above the mixed threshold.",
    ]

    run_dir = run_data["recorder"].directory
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "status": status,
        "sessions": sessions,
        "trades": total_trades,
        "win_rate_2r": round(metrics_2r.get("win_rate", 0) * 100, 2),
        "win_rate_3r": round(metrics_3r.get("win_rate", 0) * 100, 2),
        "profit_factor_2r": pf2,
        "profit_factor_3r": pf3,
        "net_pnl_2r": metrics_2r.get("net_pnl", 0),
        "net_pnl_3r": metrics_3r.get("net_pnl", 0),
        "drawdown_pct_2r": round(metrics_2r.get("max_drawdown_pct", 0) * 100, 2),
        "best_mode": best_mode,
        "weakest_mode": weakest_mode,
        "best_symbol": best_symbol,
        "weakest_symbol": weakest_symbol,
        "run_dir": str(run_dir),
        "summary_text": highlight,
        "takeaway": " ".join(takeaway),
        "watch": " ".join(watch),
    }


def move_week_run(run_data: dict, week_start: date, week_end: date, week_root: Path, version: str) -> Path:
    source_dir = run_data["recorder"].directory
    dest_dir = week_root / f"{week_start.isoformat()}_to_{week_end.isoformat()}_v{version}"
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.move(str(source_dir), str(dest_dir))
    run_data["recorder"].run_dir = dest_dir
    run_data["trade_log_path"] = dest_dir / "trade_log.csv"
    run_data["session_log_path"] = dest_dir / "session_log.csv"
    run_data["config_snapshot_path"] = dest_dir / "config_snapshot.yaml"
    run_data["changelog_path"] = dest_dir / "changelog.md"
    run_data["report_path"] = dest_dir / "run_report.txt"
    run_data["exec_log_path"] = dest_dir / "execution_log.json"
    return dest_dir


def write_weekly_outputs(batch_dir: Path, weekly_rows: list[dict], cfg: dict, start_date: date, end_date: date) -> tuple[Path, Path, Path]:
    summary_csv = batch_dir / "weekly_summary.csv"
    summary_json = batch_dir / "weekly_summary.json"
    report_txt = batch_dir / "weekly_report.txt"
    report_json = batch_dir / "weekly_report.json"

    fieldnames = list(weekly_rows[0].keys()) if weekly_rows else []
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(weekly_rows)

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(weekly_rows, f, indent=2)

    report = build_batch_report(batch_dir.name, weekly_rows, cfg, start_date, end_date)
    report_txt.write_text(report, encoding="utf-8")

    batch_json = {
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "weeks": weekly_rows,
        "summary": {
            "weeks_processed": len(weekly_rows),
            "avg_win_rate_2r": mean_safe(weekly_rows, "win_rate_2r"),
            "avg_profit_factor_2r": mean_safe(weekly_rows, "profit_factor_2r"),
            "total_net_pnl_2r": round(sum(row.get("net_pnl_2r", 0) for row in weekly_rows), 2),
        },
    }
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(batch_json, f, indent=2)

    return summary_csv, report_txt, report_json


def build_batch_report(batch_name: str, weekly_rows: list[dict], cfg: dict, start_date: date, end_date: date) -> str:
    lines = [
        "=" * 72,
        "PRECISION SCALPING UTILITY — WEEKLY BATCH REPORT",
        f"Batch: {batch_name}",
        f"Period: {start_date.isoformat()} to {end_date.isoformat()}",
        f"Version: {cfg.get('version', '1.0')}",
        "=" * 72,
        "",
    ]

    if not weekly_rows:
        lines += ["No weekly runs were generated.", ""]
        return "\n".join(lines)

    lines += [
        f"Weeks processed: {len(weekly_rows)}",
        f"Average 2R win rate: {mean_safe(weekly_rows, 'win_rate_2r'):.2f}%" if mean_safe(weekly_rows, 'win_rate_2r') is not None else "Average 2R win rate: N/A",
        f"Average 2R profit factor: {mean_safe(weekly_rows, 'profit_factor_2r'):.2f}" if mean_safe(weekly_rows, 'profit_factor_2r') is not None else "Average 2R profit factor: N/A",
        f"Total 2R net P&L: ${sum(row.get('net_pnl_2r', 0) for row in weekly_rows):,.2f}",
        "",
        "Weekly Breakdown",
        "-" * 40,
    ]

    for row in weekly_rows:
        lines += [
            f"{row['week_start']} to {row['week_end']}  [{row['status']}]",
            f"  Sessions: {row['sessions']}  Trades: {row['trades']}  Win Rate: {row['win_rate_2r']:.1f}%  PF: {row['profit_factor_2r'] if row['profit_factor_2r'] is not None else 'N/A'}  Net P&L: ${row['net_pnl_2r']:,.2f}",
            f"  Note: {row['takeaway']}",
            f"  Watch: {row['watch']}",
            "",
        ]

    best_week = max(weekly_rows, key=lambda row: row.get("net_pnl_2r", 0))
    weakest_week = min(weekly_rows, key=lambda row: row.get("net_pnl_2r", 0))
    lines += [
        "Long-View Takeaway",
        "-" * 40,
        f"Best week: {best_week['week_start']} to {best_week['week_end']} (${best_week['net_pnl_2r']:,.2f})",
        f"Weakest week: {weakest_week['week_start']} to {weakest_week['week_end']} (${weakest_week['net_pnl_2r']:,.2f})",
        "",
    ]

    return "\n".join(lines)


def main():
    args = parse_args()
    logging.getLogger().setLevel(args.log_level)

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    if start_date > end_date:
        log.error("Start date must be on or before end date.")
        sys.exit(1)

    config_path = Path(args.config)
    cfg = load_config(config_path)

    root = Path(args.results_root)
    root.mkdir(parents=True, exist_ok=True)
    batch_dir = root / f"batch_{start_date.isoformat()}_to_{end_date.isoformat()}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    week_root = batch_dir / "weeks"
    week_root.mkdir(parents=True, exist_ok=True)

    weeks = split_into_calendar_weeks(start_date, end_date)
    weekly_rows = []

    log.info("Starting weekly batch across %d week(s).", len(weeks))

    for index, (week_start, week_end) in enumerate(weeks, 1):
        log.info("Week %d/%d: %s to %s", index, len(weeks), week_start, week_end)
        run_data = run_backtest_job(cfg, week_start, week_end, config_path, results_dir=week_root)
        moved_dir = move_week_run(run_data, week_start, week_end, week_root, cfg.get("version", "1.0"))
        weekly_rows.append(summarize_week(week_start, week_end, run_data, cfg))
        log.info("Saved weekly results to %s", moved_dir)

    summary_csv, report_txt, report_json = write_weekly_outputs(batch_dir, weekly_rows, cfg, start_date, end_date)
    log.info("Weekly summary saved: %s", summary_csv)
    log.info("Weekly report saved: %s", report_txt)
    log.info("Weekly JSON report saved: %s", report_json)
    print(f"Weekly batch complete. Results saved to: {batch_dir}")


if __name__ == "__main__":
    main()
