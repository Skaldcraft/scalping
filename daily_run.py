"""
daily_run.py
============
Unattended daily runner for the Precision Scalping Utility.

By default it backtests the previous business day and writes a standard
versioned results folder. Intended to be scheduled from Windows Task Scheduler.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from backtest_job import load_config, run_backtest_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("daily_run")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precision Scalping Utility — daily unattended runner"
    )
    parser.add_argument(
        "--date",
        help="Trading date to process (YYYY-MM-DD). Defaults to the previous business day.",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to settings YAML file (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def previous_business_day(today: date) -> date:
    weekday = today.weekday()
    if weekday == 0:
        return today - timedelta(days=3)
    if weekday == 6:
        return today - timedelta(days=2)
    return today - timedelta(days=1)


def main():
    args = parse_args()
    logging.getLogger().setLevel(args.log_level)

    config_path = Path(args.config)
    try:
        cfg = load_config(config_path)
    except FileNotFoundError as exc:
        log.error(str(exc))
        sys.exit(1)

    target_day = date.fromisoformat(args.date) if args.date else previous_business_day(date.today())
    start_date = target_day
    end_date = target_day + timedelta(days=1)

    log.info("Precision Scalping Utility v%s", cfg.get("version", "?"))
    log.info("Daily run date  : %s", target_day)
    log.info("Backtest period : %s → %s", start_date, end_date)

    run_data = run_backtest_job(cfg, start_date, end_date, config_path)
    all_trades = run_data["all_trades"]
    m2 = run_data["metrics_2r"]
    m3 = run_data["metrics_3r"]

    if not all_trades:
        log.warning("Daily run completed with zero trades.")

    print("\n" + "=" * 60)
    print(f"  DAILY RUN COMPLETE — {len(all_trades)} trades")
    print("=" * 60)
    print(f"  2R  Win Rate: {m2['win_rate']*100:.1f}%  |  PF: {m2['profit_factor'] or 'N/A'}  |  Net P&L: ${m2['net_pnl']:,.2f}")
    print(f"  3R  Win Rate: {m3['win_rate']*100:.1f}%  |  PF: {m3['profit_factor'] or 'N/A'}  |  Net P&L: ${m3['net_pnl']:,.2f}")
    print(f"\n  Results saved to: {run_data['recorder'].directory}")
    print(f"  Run report     : {run_data['report_path']}")
    print(f"  Execution log  : {run_data['exec_log_path']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
