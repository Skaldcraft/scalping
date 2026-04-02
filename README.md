# Precision Scalping Utility

A mechanical backtesting engine for opening-range scalping strategies.
Removes emotion and guesswork from the evaluation process by implementing a fully
objective, rule-based simulation of intraday price action during the first 90 minutes
of the New York session, driven by a fixed tracked universe and a pre-session Top-N selector.

---

## What It Does

The utility simulates a unified hybrid strategy derived from three source
frameworks (Casper SMC, ProRealAlgos, Jdub Trades) and produces:

- A **trade-by-trade journal** of every simulated entry and exit
- **Concurrent 2:1 and 3:1 reward-ratio results** from the same signal set
- A **third-person run report** narrating what the utility did and why
- A **per-session execution log** recording every decision point (including
  sessions where no trade was taken)
- A **per-run config snapshot** and **copied changelog** for version traceability
- An **equity curve**, mode breakdown, and instrument comparison via a
  web dashboard

---

## Strategy Logic Summary

```
Phase 0 (pre-session):   Rank the tracked universe before the open
                         Compute 14-day ATR and apply selector filters
Phase 1 (opening range): Mark H/L/midpoint of first N-minute candle
                         Compare range to 25% of ATR

If range >= 25% ATR  →  MANIPULATION MODE
  Wait for Hammer / Inverted Hammer / Engulfing outside the range
  Enter opposite to the initial spike direction

If range < 25% ATR   →  BREAKOUT MODE
  Wait for full-body candle close outside the range
  Wait for valid retest or qualified displacement gap
  Enter on open of next candle

If breakout fails    →  MEAN REVERSION MODE
  Enter toward opposite boundary of the opening range

All modes:
  Stop-Loss  : OR midpoint (Fibonacci 0.5 level)
  Take-Profit: 2:1 and 3:1 tracked concurrently
  Session gate: no new entries after 11:00 ET
```

---

## Installation

### Requirements
- Python 3.11 or higher
- pip

### Steps

```bash
# 1. Unzip the project
unzip scalping_utility.zip
cd scalping_utility

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Running the Dashboard (recommended)

```bash
python -m streamlit run dashboard/app.py
```

Then open `http://localhost:8501` in your browser.

The sidebar lets you configure all parameters interactively. Press
**Run Backtest** to execute.

---

## Running from the CLI

```bash
python main.py --start 2024-01-01 --end 2024-06-30
```

Options:

| Flag | Default | Description |
|---|---|---|
| `--start` | required | Backtest start date (YYYY-MM-DD) |
| `--end` | required | Backtest end date (YYYY-MM-DD) |
| `--config` | `config/settings.yaml` | Path to config file |
| `--log-level` | `INFO` | DEBUG / INFO / WARNING / ERROR |

Results are saved automatically to `results/<timestamp>_v<version>/`.

---

## Configuration

All parameters live in `config/settings.yaml`. Edit this file to change
the strategy without touching any code.

Key parameters:

```yaml
opening_range:
  candle_size_minutes: 15        # 5 or 15

strategy:
  manipulation_threshold_pct: 25.0  # % of ATR that flags a manipulation candle

account:
  starting_capital: 10000
  risk_per_trade_pct: 1.0
  daily_loss_limit_pct: 5.0

risk:
  profit_factor_floor: 1.5
  min_trades_before_pf_check: 10
```

### Tracked Universe and Selection

The default configuration now uses a fixed tracked universe under `pre_session.universe`.
That universe includes equities, indices, Yahoo-compatible forex symbols, and gold.

Normal production flow:

1. PulseTrader loads the fixed tracked universe.
2. The pre-session selector ranks that universe.
3. The Top-N session selection is used for the run.

Research-only alternatives still exist if you want to test a custom subset, but that is no longer the primary workflow.

### Daily Automation

Use `daily_run.py` for unattended runs. It processes the previous business day by default and writes the same versioned results folder.

```bash
python daily_run.py
```

For Windows Task Scheduler, you can point the task at `run_daily.ps1`.

Recommended action:

```powershell
powershell.exe -ExecutionPolicy Bypass -File run_daily.ps1
```

Batch fallback:

```bat
run_daily.bat
```

```powershell
.\run_daily.ps1
```

Recommended schedule:
- Run once per day after the New York session is closed, for example around `6:00 PM ET`.
- On Windows, create a Task Scheduler task that runs `powershell.exe -ExecutionPolicy Bypass -File run_daily.ps1` from the project root.

If you need to target a specific date:

```bash
python daily_run.py --date 2026-03-20 --config config/settings.yaml
```

### Intraday 15-Minute Automation (Windows)

If you want the utility to rerun automatically during market hours, use the included PowerShell helpers:

```powershell
powershell.exe -ExecutionPolicy Bypass -File register_intraday_task.ps1
```

What this does:
- creates a Windows scheduled task named `PulseTrader Intraday 15m`
- triggers every `15` minutes
- only performs the real run during `09:25` to `11:00` **New York time**
- uses `run_intraday.ps1`, which calls `daily_run.py` for the current ET date
- reuses the frozen daily selection for the date when pre-session selection is enabled

Useful commands:

```powershell
# Test the intraday runner immediately
powershell.exe -ExecutionPolicy Bypass -File run_intraday.ps1 -ForceRun

# Inspect the scheduled task
schtasks.exe /Query /TN "PulseTrader Intraday 15m" /V /FO LIST

# Remove the scheduled task if needed
schtasks.exe /Delete /TN "PulseTrader Intraday 15m" /F
```

### Weekly Batch Report

Run a full weekly batch over a date range:

```bash
python weekly_batch.py --start 2026-01-05 --end 2026-03-27 --config config/settings.yaml
```

What it creates:
- `results/batch_2026-01-05_to_2026-03-27/weekly_summary.csv`
- `results/batch_2026-01-05_to_2026-03-27/weekly_report.txt`
- `results/batch_2026-01-05_to_2026-03-27/weekly_report.json`
- `results/batch_2026-01-05_to_2026-03-27/weeks/` with one folder per week

### Daily Workflow

1. Edit locally in your code editor.
   - Change strategy, UI, docs, or config files in this workspace.
2. Run a quick local test.
   - CLI: `python main.py --start YYYY-MM-DD --end YYYY-MM-DD --config <config-file>`
   - Daily runner: `python daily_run.py`
3. Check the dashboard locally.
   - Run: `python -m streamlit run dashboard/app.py`
   - Review the charts, trade table, and run report.
4. Update versioning if strategy logic changed.
   - Increment `version` in `config/settings.yaml`.
   - Add a note to `config/changelog.md`.
5. Commit the change locally.
   - From this project folder: `git add .` then `git commit -m "<message>"`
6. Push to GitHub.
   - From this project folder: `git push`
   - This updates `https://github.com/Skaldcraft/scalping.git`.
7. Refresh the app if needed.
   - For local use: stop and restart Streamlit or rerun the CLI.
   - For hosted deployments: let the deployment pipeline pull the new commit.

---

## Alternate Forex / CSV Data

The default tracked universe already includes Yahoo-compatible forex and gold symbols.
If you want to backtest an alternate dataset, you can still provide your own CSV files.

Use CSV data when:

- you want to compare Yahoo-compatible feeds against your own history
- you want tighter control over the forex dataset
- you want to test symbols not covered by the default tracked universe

To backtest from CSV:

1. Obtain OHLCV CSV files from a provider (e.g. Dukascopy, TrueFX, Forex Tester).
2. Place the files in the `data_files/` directory.
3. Add entries to `config/settings.yaml`:

```yaml
instruments:
  forex_csv_files:
    EURUSD: "data_files/EURUSD_5min.csv"
    GBPUSD: "data_files/GBPUSD_5min.csv"
```

### Expected CSV format

| Column | Type | Notes |
|---|---|---|
| `timestamp` | datetime | ISO 8601 preferred. ET timezone preferred. |
| `open` | float | |
| `high` | float | |
| `low` | float | |
| `close` | float | |
| `volume` | float | Optional — set to 0 if unavailable |

Column names are case-insensitive. Common alternatives (`date`, `datetime`,
`time`) are detected automatically.

---

## Output Files

Every run creates a timestamped folder in `results/`:

```
results/
└── 20240815_143022_v1.0/
    ├── trade_log.csv         All executed trades with full entry/exit detail
    ├── session_log.csv       Every session evaluated (including no-trade sessions)
    ├── run_report.txt        Third-person prose narrative of the run
    ├── execution_log.json    Per-session decision audit trail
    ├── config_snapshot.yaml  Exact configuration used for this run
    └── changelog.md          Snapshot of the version history used by that run
```

These artifacts are written even when a run produces zero trades.

### run_report.txt

An objective, third-person account of what the utility did. Covers:
- Run scope (instruments, dates, parameters)
- Session activity and mode activation counts per instrument
- Signal filtering funnel (how many sessions cleared each filter)
- Circuit breaker events (if any)
- 2R vs 3R performance comparison with a plain-language verdict
- Refinement notes flagging any metrics below benchmark

### execution_log.json

Machine-readable per-session log. For every session it records:
- Opening range values and ATR
- Whether the manipulation threshold was triggered
- Which strategy mode was activated
- Whether breakout / retest / pattern conditions were met
- Rejection reasons for sessions with no trade
- Compact trade detail for sessions where a trade was executed

---

## Versioning and Change Tracking

Every time you change strategy logic or parameters:

1. Increment `version` in `config/settings.yaml`
2. Add an entry to `config/changelog.md` describing what changed and why

The version is stamped into every results folder name and into each
`execution_log.json` header, so result sets from different versions
remain permanently distinguishable.

---

## Project Structure

```
scalping_utility/
├── config/
│   ├── settings.yaml          All parameters
│   └── changelog.md           Version history
│
├── data/
│   ├── models.py              Core dataclasses
│   ├── fetcher.py             yfinance + CSV loaders
│   └── validator.py           Data quality checks
│
├── engine/
│   ├── session.py             Session gating (9:30–11:00 ET)
│   ├── opening_range.py       OR calculation + ATR filter
│   ├── signals.py             Breakout, Manipulation, Mean Reversion detectors
│   ├── trade.py               Bar-by-bar trade resolution
│   └── backtester.py          Main orchestration loop
│
├── risk/
│   ├── position_sizer.py      1% fixed-fractional sizing
│   └── circuit_breaker.py     Daily loss halt + PF floor monitor
│
├── journal/
│   ├── recorder.py            File writer for all outputs
│   ├── metrics.py             Win rate, PF, drawdown, Sharpe
│   ├── run_report.py          Third-person prose run narrative
│   └── execution_log.py       Per-session JSON decision log
│
├── dashboard/
│   └── app.py                 Streamlit web UI
│
├── data_files/                Drop Forex CSV files here
├── results/                   Auto-generated after each run
├── requirements.txt
├── main.py                    CLI entry point
└── README.md
```

---

## Recommended First Run

```bash
# Verify installation with a short date range using the default tracked universe
python main.py --start 2024-10-01 --end 2024-12-31
```

This tests roughly 65 sessions on the tracked universe with the current selector workflow and should
complete in under two minutes. Then open the dashboard to explore the results:

```bash
python -m streamlit run dashboard/app.py
```

---

## Data Availability Notes

| Source | Interval | Max History |
|---|---|---|
| yfinance (tracked equities / indices / Yahoo symbols) | 1m | ~30 calendar days |
| yfinance (tracked equities / indices / Yahoo symbols) | 5m | ~60 days per request (chunked automatically) |
| yfinance (tracked equities / indices / Yahoo symbols) | 15m | ~60 days per request |
| User CSV (alternate Forex / custom feed) | Any | Unlimited — depends on your data file |

For backtests longer than 60 days on equity instruments, the fetcher
automatically splits the request into 58-day chunks and reassembles the data.

For institutional-grade historical data with no yfinance limitations,
Polygon.io (~$29/month) is the recommended upgrade path. The fetcher
module can be extended to support it by replacing the `fetch_intraday`
function with a Polygon REST client while keeping all downstream modules
identical.

---

## Circuit Breakers

Two automated halts are enforced during simulation:

| Trigger | Condition | Effect |
|---|---|---|
| Daily Loss Limit | Session P&L ≤ −5% of session-start equity | No new entries for remainder of that day |
| Profit Factor Floor | Rolling PF < 1.5 after ≥ 10 trades | All entries halted; logged as a refinement flag |

Both events are recorded in `execution_log.json` and summarised in `run_report.txt`.

---

## Benchmarks (from strategy documentation)

| Metric | Target |
|---|---|
| Win Rate | 70% (retest confirmation model) |
| Profit Factor | ≥ 1.5 |
| Risk per trade | 1% of equity |
| Max daily loss | 5% of equity |
| Session window | 09:30–11:00 ET |

The run report flags any metric that falls below these benchmarks and
suggests specific parameter adjustments.
