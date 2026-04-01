# Precision Scalping Utility — Beginner Guide

A practical guide for people who are new to trading and want to understand **what scalping is**, **what this utility does**, and **how to use it safely and clearly**.

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

## 4) How the strategy works in plain language

The utility follows a fixed sequence.

### Step 1 — It defines the session
The tool looks at a time window such as:

- **Start:** `09:30` New York time
- **End:** `11:00` New York time

This is the period in which new trades are allowed.

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

## 5) What kind of data it uses

The utility can work with two main data paths:

### A) Equities / ETFs / indices
Examples:

- `AAPL`
- `NVDA`
- `AMZN`
- `QQQ`
- `SPY`

These are fetched automatically through **Yahoo Finance** when you run a backtest.

### B) Forex
For Forex, the utility expects you to provide your own **CSV files** in `data_files/`.

Example section in `config/settings.yaml`:

```yaml
instruments:
  forex_csv_files:
    EURUSD: "data_files/EURUSD_5min.csv"
```

---

## 6) How to activate and use real data

For **equities**, real historical data is already connected.
You do **not** need to write special API code.

You just need at least one symbol listed in `config/settings.yaml`:

```yaml
instruments:
  equities:
    - AAPL
    - NVDA
    - AMZN
    - QQQ
    - SPY
```

Then run:

```powershell
python main.py --start 2026-03-20 --end 2026-03-27 --config config/settings.yaml
```

That command will use **all symbols in the config**.

### One symbol example
```powershell
python main.py --start 2026-03-20 --end 2026-03-27 --config config/settings_equities_sample.yaml
```

### Three-symbol example
If your config contains `AAPL`, `NVDA`, and `QQQ`, run:

```powershell
python main.py --start 2026-03-20 --end 2026-03-27 --config config/settings.yaml
```

### All-symbol example
If your config contains five or more symbols, the same command runs them all:

```powershell
python main.py --start 2026-03-20 --end 2026-03-27 --config config/settings.yaml
```

> The difference is not the command itself — it is the list of symbols inside the config file.

---

## 7) The easiest way to use the tool: the dashboard

The beginner-friendly way to use the project is the **Streamlit dashboard**.

### Start the dashboard
```powershell
python -m streamlit run dashboard/app.py
```

Then open the local browser page shown by Streamlit.

### What you can do in the dashboard

- choose a **date range**
- select one or more **symbols**
- pick the **opening-range candle size**
- adjust **risk settings**
- click **Run Backtest**
- review charts, tables, and downloadable files

### Typical beginner workflow

1. Open the dashboard.
2. Choose a recent date range.
3. Select one symbol first, such as `AAPL`.
4. Run the backtest.
5. Review the results.
6. Then try multiple symbols together.

---

## 8) Command-line usage

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

## 9) Daily and weekly automation

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

## 10) Understanding the results

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

## 11) Key metrics explained simply

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

## 12) Risk controls built into the tool

The utility is not only looking for entries. It also contains controls intended to limit overtrading and poor conditions.

Examples include:

- **risk per trade**
- **daily loss limit**
- **profit factor floor**
- **minimum trade count before some checks activate**

This encourages more disciplined testing.

---

## 13) What the tool does well

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

## 14) What the tool does **not** do

It is important to be realistic.

This utility does **not**:

- guarantee future profits
- replace trading education or risk management
- send live broker orders
- remove slippage or execution differences from the real world
- prove that a strategy will work the same way in the future

Backtesting is a way to **study behavior**, not a promise of future performance.

---

## 15) Best practices for beginners

If you are new to trading, this is a good approach:

1. Start with **one symbol**.
2. Use a **short date range** first.
3. Read the `run_report.txt` after each test.
4. Look at **drawdown**, not only profit.
5. Change **one setting at a time**.
6. Keep notes on what changed and why.
7. Avoid making conclusions from a very small number of trades.

---

## 16) Example beginner workflow

### First session
- Run the dashboard.
- Select `AAPL`.
- Use a 1–2 week date range.
- Run the test.
- Read the metrics and the report.

### Second session
- Add `NVDA` and `QQQ`.
- Compare whether the same rules behave similarly.
- Review which symbol had better stability.

### Third session
- Run all configured symbols.
- Check the per-instrument table.
- Compare win rate, net P&L, and drawdown.

---

## 17) Troubleshooting basics

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

## 18) Glossary of terms

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

## 19) Final reminder

This utility is best used as a **learning and analysis assistant**.

For a beginner, its value is not only whether a backtest is profitable, but also:

- understanding how rules behave
- seeing how market conditions change
- learning how risk affects outcomes
- building a more disciplined process

If you want, you can add a short link to this guide from the main `README.md` for easier access.