# Precision Scalping Utility — Beginner Guide

A practical guide for people who are new to trading and want to understand **what scalping is**, **what this utility does**, and **how to use it safely and clearly**.

## Table of contents

- [1) What is this tool?](#1-what-is-this-tool)
- [2) What is scalping?](#2-what-is-scalping)
- [3) What this utility studies](#3-what-this-utility-studies)
- [4) What the tracked universe means](#4-what-the-tracked-universe-means)
- [5) How the strategy works in plain language](#5-how-the-strategy-works-in-plain-language)
- [6) What kind of data it uses](#6-what-kind-of-data-it-uses)
- [7) How real data works now](#7-how-real-data-works-now)
- [8) The easiest way to use the tool: the dashboard](#8-the-easiest-way-to-use-the-tool-the-dashboard)
- [9) Command-line usage](#9-command-line-usage)
- [10) Daily and weekly automation](#10-daily-and-weekly-automation)
- [11) Understanding the results](#11-understanding-the-results)
- [12) Key metrics explained simply](#12-key-metrics-explained-simply)
- [13) Risk controls built into the tool](#13-risk-controls-built-into-the-tool)
- [14) What the tool does well](#14-what-the-tool-does-well)
- [15) What the tool does not do](#15-what-the-tool-does-not-do)
- [16) Best practices for beginners](#16-best-practices-for-beginners)
- [17) Example beginner workflow](#17-example-beginner-workflow)
- [18) Troubleshooting basics](#18-troubleshooting-basics)
- [19) Glossary of terms](#19-glossary-of-terms)
- [20) Final reminder](#20-final-reminder)

---

## 1) What is this tool?

The **Precision Scalping Utility** is a **backtesting and review tool**.

It helps you answer questions like:

- *If I had followed this scalping strategy in the past, what would have happened?*
- *Which symbols behaved better?*
- *What were the win rate, profit factor, and drawdown?*
- *Did the strategy find trades, or did market conditions reject them?*

> **Important:** This utility is **not** an automatic live-trading bot and does **not** place broker orders. It is designed to **analyze historical market data** and simulate how a rule-based scalping strategy would have performed.

---

## 2) What is scalping?

**Scalping** is a style of trading that aims to capture **small price moves** over a short period of time.

A scalper typically:

- focuses on short timeframes such as **1-minute, 5-minute, or 15-minute charts**
- enters and exits trades quickly
- looks for repeatable patterns instead of large long-term moves
- uses strict risk control because many trades can happen in a short session

In simple words:

> A scalper is trying to take small, controlled pieces of movement from the market rather than holding for days or weeks.

---

## 3) What this utility studies

This utility focuses on a specific kind of scalping idea:

### **Opening-range trading**
It studies what happens near the start of the New York session, especially around the **first few minutes after the market opens**.

The core idea is:

1. Measure the first candle or first block of candles.
2. Mark that initial area as the **opening range**.
3. Decide whether price is showing:
   - a **breakout**
   - a **manipulation / fake move**
   - or a **mean-reversion setup**
4. Simulate entries, stop-loss, and take-profit levels.

This makes the process more **mechanical** and less emotional.

---

## 4) What the tracked universe means

PulseTrader now works with a **tracked universe**.

This means the tool starts from a **fixed pool of instruments** that it monitors regularly, instead of expecting you to define a brand-new symbol list every time you run it.

In simple terms:

- the **tracked universe** is the full pool PulseTrader watches
- the **pre-session selector** ranks that pool before the New York session
- the tool then trades only the **Top-N session selection** for that run when selection is enabled

So there are two different ideas:

- **Tracked universe** = everything PulseTrader is allowed to consider
- **Session selection** = the smaller set chosen for the current day

This is useful because it keeps the process consistent and makes daily selection more objective.

### Why the universe is split into categories

The tracked universe is grouped by market type because these instruments do not behave exactly the same way:

| Category | What it includes | Why it matters |
|---|---|---|
| **Equities** | Individual companies such as `AAPL`, `NVDA`, `MSFT` | Single stocks can move sharply on company-specific momentum and often fit reversal logic well. |
| **Indices** | Market-tracking instruments such as `QQQ`, `SPY` | Indices often behave more smoothly and are useful for trend-style continuation logic. |
| **Forex** | Currency pairs such as `EUR/USD`, `GBP/USD`, `USD/JPY` | Forex trades nearly continuously and can react differently to session overlap, liquidity, and macro news. |
| **Gold / Metals** | Gold instruments such as `XAU/USD` | Gold often responds to risk sentiment, inflation expectations, and macro flows differently from stocks or currencies. |

The distinction matters because a strategy can behave differently on:

- a single stock
- a broad index
- a currency pair
- a metal like gold

That is one reason PulseTrader separates the **tracked universe** from the **session selection** and keeps detailed performance records.

---

## 5) How the strategy works in plain language

The utility follows a fixed sequence.

### Step 1 — It defines the session
The tool looks at a time window such as:

- **Pre-session selector:** `09:25` New York time
- **Start:** `09:30` New York time
- **End:** `11:00` New York time

The selector can rank the tracked universe before the session opens. New trades are then only allowed during the active session window.

### Step 2 — It marks the opening range
It uses the first **5-minute** or **15-minute** candle to define:

- the opening range **high**
- the opening range **low**
- the opening range **midpoint**

These levels are used later for entries and stops.

### Step 3 — It measures volatility with ATR
The tool calculates **ATR (Average True Range)** from daily data.

ATR is used to estimate whether the first move of the session was:

- relatively normal, or
- unusually strong and possibly manipulative

### Step 4 — It chooses a mode
Depending on market behavior, the utility activates one of these modes:

| Mode | Meaning |
|---|---|
| **Breakout** | Price pushes beyond the opening range and confirms the move. |
| **Manipulation** | The opening move looks exaggerated, and the strategy watches for a reversal signal. |
| **Mean Reversion** | If the breakout fails, the strategy looks for price to move back toward the range. |
| **No Trade** | Conditions were not good enough for a valid setup. |

### Step 5 — It simulates trade management
If a valid signal appears, the utility simulates:

- **entry price**
- **stop-loss**
- **2R target**
- **3R target**
- **position sizing** based on risk
- **commission costs**

The stop-loss is usually based on the **opening-range midpoint**, and both **2:1** and **3:1 reward targets** are tracked for comparison.

### Step 6 — It records everything
After the run, the utility saves:

- trade-by-trade results
- session summaries
- a narrative report
- an execution log
- a snapshot of the config used

---

## 6) What kind of data it uses

The utility can work with two main data paths:

### A) Equities / ETFs / indices / tracked Yahoo symbols
Examples:

- `AAPL`
- `NVDA`
- `AMZN`
- `QQQ`
- `SPY`

The tracked universe can also include Yahoo-compatible symbols for other asset types, including Forex and Gold.

These are fetched automatically through **Yahoo Finance** when you run a backtest.

### B) Forex
Forex can be used in **two ways** in the current setup:

1. **Tracked-universe Yahoo-compatible symbols (default flow)**
   - Example symbols in the tracked universe: `EURUSD=X`, `GBPUSD=X`, `JPY=X`
   - These are evaluated by the same pre-session selector and Top-N process as other tracked instruments.

2. **Local CSV override path (optional)**
   - Use this when you want tighter control over your Forex feed quality or want to compare providers.
   - Place files in `data_files/` and map them in config.

Example CSV mapping in `config/settings.yaml`:

```yaml
instruments:
  forex_csv_files:
    EURUSD: "data_files/EURUSD_5min.csv"
```

When CSV is usually preferable:

- you need a fixed historical dataset for reproducible tests
- you want to control data quality and timestamps explicitly
- you want to test symbols/timeframes not covered by your default tracked feed

Practical note on reliability:

- Forex is kept in the automated tracked universe, but spread/data-quality controls can be stricter than equities.
- If needed, use selector rules to enforce stricter inclusion (for example spread missing policy = reject, plus spread thresholds).

---

## 7) How real data works now

PulseTrader now uses a **tracked-universe-first** workflow.

That means:

- the fixed tracked universe is defined in `config/settings.yaml`
- the pre-session selector reviews that universe before the session opens
- the selector chooses the **Top-N session selection**
- the strategy then trades only that smaller session list when selection is enabled

So in the current setup, “using real data” usually does **not** mean manually picking symbols one by one.
It means making sure the tracked universe is configured and letting the selector do the daily filtering.

### What is already connected

The current tracked universe includes Yahoo-compatible symbols for:

- equities
- indices
- Forex
- gold

That means historical market data can be fetched automatically for the default tracked universe without writing extra API code.

### What still needs attention

Some selector inputs are still optional or partially manual, depending on what you want to test:

- **Profit Factor history** comes from prior saved trade results
- **Spread data** can be supplied through manual overrides if needed
- **Research Overrides** in the dashboard are only for testing custom subsets, not the normal production workflow

### When CSV files still matter

CSV files are still useful if:

- you want to test an alternate Forex dataset
- you want to compare Yahoo-compatible symbols against your own imported data
- you want tighter control over the exact historical feed being used

So CSV-based Forex is still supported, but it is no longer the only way the tool can work with non-equity instruments.

---

## 8) The easiest way to use the tool: the dashboard

The beginner-friendly way to use the project is the **Streamlit dashboard**.

### Start the dashboard
```powershell
python -m streamlit run dashboard/app.py
```

Then open the local browser page shown by Streamlit.

### What you can do in the dashboard

- choose a **date range**
- review the **tracked universe**
- adjust **pre-session selection controls**
- pick the **opening-range candle size**
- adjust **trend-mode controls**
- adjust **risk settings**
- click **Run Backtest**
- review charts, tables, no-trade reasons, and downloadable files

### Typical beginner workflow

1. Open the dashboard.
2. Choose a recent date range.
3. Confirm the tracked universe and Top-N selection settings.
4. Run the backtest.
5. Review the latest run, session selection, and results.
6. Use Research Overrides only if you want to test a custom subset.

---

## 9) Command-line usage

If you prefer the terminal, you can run the tool directly.

### Standard command
```powershell
python main.py --start YYYY-MM-DD --end YYYY-MM-DD --config config/settings.yaml
```

### Example
```powershell
python main.py --start 2026-03-20 --end 2026-03-27 --config config/settings.yaml --log-level INFO
```

### Useful arguments

| Flag | Meaning |
|---|---|
| `--start` | Start date of the backtest |
| `--end` | End date of the backtest |
| `--config` | Which YAML settings file to use |
| `--log-level` | Verbosity level such as `INFO` or `DEBUG` |

---

## 10) Daily and weekly automation

The project also includes automation helpers.

### Daily run
```powershell
python daily_run.py
```

This processes the previous business day by default.

### PowerShell wrapper
```powershell
.\run_daily.ps1
```

### Weekly batch
```powershell
python weekly_batch.py --start 2026-01-05 --end 2026-03-27 --config config/settings.yaml
```

These are useful when you want to build a regular review habit.

---

## 11) Understanding the results

Each run creates a folder inside `results/`.

Example:

```text
results/20260401_161940_v1.0/
```

Inside that folder you may see:

| File | Purpose |
|---|---|
| `trade_log.csv` | Every trade with entries, exits, direction, and results |
| `session_log.csv` | A session-by-session record, including no-trade sessions |
| `run_report.txt` | A readable summary of what happened |
| `execution_log.json` | Detailed decision trace for debugging and review |
| `config_snapshot.yaml` | The exact settings used for that run |
| `changelog.md` | Version notes copied for reference |

---

## 12) Key metrics explained simply

Here are the main numbers you will see.

### Win Rate
The percentage of trades that were winners.

- Example: a 60% win rate means 6 out of 10 trades won.

### Net P&L
The total money gained or lost over the test period.

- Positive = profit
- Negative = loss

### Profit Factor
A ratio comparing gross profits to gross losses.

- above `1.0` = profitable overall
- above `1.5` = generally stronger
- below `1.0` = losses outweigh profits

### Max Drawdown
The largest peak-to-trough decline during the run.

This helps you understand how painful the losing periods might feel.

### Sharpe Ratio
A basic measure of return relative to volatility.

For beginners, it can be treated as a rough “quality of returns” number.

---

## 13) Risk controls built into the tool

The utility is not only looking for entries. It also contains controls intended to limit overtrading and poor conditions.

Examples include:

- **risk per trade**
- **daily loss limit**
- **profit factor floor**
- **minimum trade count before some checks activate**

This encourages more disciplined testing.

---

## 14) What the tool does well

### Strengths
- gives a **consistent, rule-based review**
- removes much of the emotion from analysis
- compares **2R and 3R targets** from the same trades
- records both **trades** and **non-trades**
- makes it easier to compare symbols and periods

### Good use cases
- learning how opening-range scalping behaves
- comparing a few symbols over the same week
- seeing whether rules are too strict or too loose
- reviewing how the strategy changes after parameter updates

---

## 15) What the tool does **not** do

It is important to be realistic.

This utility does **not**:

- guarantee future profits
- replace trading education or risk management
- send live broker orders
- remove slippage or execution differences from the real world
- prove that a strategy will work the same way in the future

Backtesting is a way to **study behavior**, not a promise of future performance.

---

## 16) Best practices for beginners

If you are new to trading, this is a good approach:

1. Start with **one symbol**.
2. Use a **short date range** first.
3. Read the `run_report.txt` after each test.
4. Look at **drawdown**, not only profit.
5. Change **one setting at a time**.
6. Keep notes on what changed and why.
7. Avoid making conclusions from a very small number of trades.

---

## 17) Example beginner workflow

### Path A (recommended): tracked-universe workflow

1. Open the dashboard.
2. Keep the default **tracked universe** and pre-session selector enabled.
3. Use a short date range (for example 1-2 weeks).
4. Run the backtest.
5. Review:
  - session Top-N selection
  - no-trade reasons (if any)
  - per-instrument performance
6. Repeat with a different date range before changing strategy settings.

### Path B (optional didactic mode): research overrides

Use this only when you want to isolate behavior for learning.

1. Open **Research Overrides** in the Backtest sidebar.
2. Enable override for this run.
3. Test a small subset (for example 1-2 symbols) over a short range.
4. Compare mode behavior and stability between symbols.
5. Disable override and return to Path A for normal workflow.

This gives you educational clarity without replacing the default selector-driven process.

---

## 18) Troubleshooting basics

### “No trades were produced”
Possible reasons:

- the chosen dates had no valid setups
- the signal rules were too strict
- there was limited or missing data
- the selected session window did not allow an entry

### “Backtest failed”
Possible reasons:

- a symbol name is invalid
- the date range is too large for the requested intraday interval
- a Forex CSV file is missing or formatted incorrectly

### “Only a few days of data”
That usually means the test range is very short, which may not be enough to judge the strategy properly.

---

## 19) Glossary of terms

| Term | Plain-language meaning |
|---|---|
| **ATR (Average True Range)** | A measure of how much price usually moves. It is used here to judge volatility. |
| **Backtest** | A simulation using historical data to see how a strategy would have behaved in the past. |
| **Breakout** | When price moves outside a defined range and continues in that direction. |
| **Broker** | The platform or company used to place real trades in the market. |
| **Candle / Candlestick** | A chart bar showing open, high, low, and close for a time period. |
| **Commission** | The trading cost charged per trade. |
| **CSV** | A spreadsheet-like text file used to store historical market data. |
| **Daily loss limit** | A risk rule that stops trading after a maximum allowed loss for the day. |
| **Drawdown** | A decline in account value from a previous peak. |
| **Entry** | The moment a trade is opened. |
| **Equity** | Account value at a given moment. |
| **Execution log** | A detailed record of what the system checked and decided during each session. |
| **Forex** | The foreign exchange market, where currency pairs such as `EURUSD` are traded. |
| **Intraday** | Activity that happens within the same trading day. |
| **Liquidity** | How easily something can be bought or sold without causing a large price move. |
| **Manipulation** | In this project, a sharp opening move that may be a trap or false push before reversal. |
| **Mean reversion** | The idea that price may return toward its earlier range after a failed move. |
| **Opening range** | The high and low formed by the first 5- or 15-minute period of the session. |
| **P&L (Profit and Loss)** | How much money was made or lost. |
| **Position size** | How many units or shares are taken in a trade. |
| **Profit factor** | Gross profit divided by gross loss. A measure of overall strategy efficiency. |
| **Retest** | When price returns to a breakout level to confirm it before continuing. |
| **Reward-to-risk (R or R:R)** | A comparison between expected profit and allowed loss. Example: `2R` means a reward twice the risk. |
| **Scalping** | A short-term trading style focused on capturing small moves quickly. |
| **Session** | A defined period of market activity, such as the New York morning session. |
| **Sharpe ratio** | A simplified measure of return quality relative to variability. |
| **Signal** | The condition that tells the strategy a trade setup may be valid. |
| **Slippage** | The difference between the expected trade price and the actual executed price. |
| **Stop-loss** | A price level where the trade is closed to limit loss. |
| **Ticker / Symbol** | The market code for an asset, such as `AAPL` or `QQQ`. |
| **Volatility** | The degree to which price moves up and down. |
| **Win rate** | The percentage of trades that ended in profit. |

---

## 20) Final reminder

This utility is best used as a **learning and analysis assistant**.

For a beginner, its value is not only whether a backtest is profitable, but also:

- understanding how rules behave
- seeing how market conditions change
- learning how risk affects outcomes
- building a more disciplined process

If you want, you can add a short link to this guide from the main `README.md` for easier access.