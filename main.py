"""
main.py
=======
CLI entry point for the Precision Scalping Utility backtester.

Usage:
    python main.py --start 2024-01-01 --end 2024-06-30
    python main.py --start 2024-01-01 --end 2024-06-30 --config config/settings.yaml

For the interactive web dashboard run:
    streamlit run dashboard/app.py
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from backtest_job import load_config, run_backtest_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precision Scalping Utility — CLI Backtester"
    )
    parser.add_argument(
        "--start", required=True,
        help="Backtest start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end", required=True,
        help="Backtest end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--config", default="config/settings.yaml",
        help="Path to settings YAML file (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.getLogger().setLevel(args.log_level)

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        sys.exit(1)

    cfg = load_config(config_path)

    start_date = date.fromisoformat(args.start)
    end_date   = date.fromisoformat(args.end)

    if start_date >= end_date:
        log.error("Start date must be before end date.")
        sys.exit(1)

    log.info("Precision Scalping Utility v%s", cfg.get("version", "?"))
    log.info("Backtest period : %s → %s", start_date, end_date)
    log.info("Instruments     : %s", cfg["instruments"].get("equities", []))
    log.info("Opening range   : %d minutes", cfg["opening_range"]["candle_size_minutes"])

    run_data = run_backtest_job(cfg, start_date, end_date, config_path)
    all_trades = run_data["all_trades"]
    m2 = run_data["metrics_2r"]
    m3 = run_data["metrics_3r"]
    recorder = run_data["recorder"]
    report_path = run_data["report_path"]
    exec_log_path = run_data["exec_log_path"]

    if not all_trades:
        log.warning("Backtest completed with zero trades.")

    # Print summary to terminal
    print("\n" + "=" * 60)
    print(f"  BACKTEST COMPLETE — {len(all_trades)} trades")
    print("=" * 60)
    print(f"  2R  Win Rate: {m2['win_rate']*100:.1f}%  |  "
          f"PF: {m2['profit_factor'] or 'N/A'}  |  "
          f"Net P&L: ${m2['net_pnl']:,.2f}")
    print(f"  3R  Win Rate: {m3['win_rate']*100:.1f}%  |  "
          f"PF: {m3['profit_factor'] or 'N/A'}  |  "
          f"Net P&L: ${m3['net_pnl']:,.2f}")
    print(f"\n  Results saved to: {recorder.directory}")
    print(f"  Run report     : {report_path}")
    print(f"  Execution log  : {exec_log_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
