# Project Overview Artifact
**Project:** Precision Scalping Utility (PulseTrader)  
**Analysis Mode:** Deep  
**Date:** 2026-04-11  
**Confidence:** High  

---

## 1. Executive Summary

### What the Project Is
A mechanical backtesting engine for opening-range scalping strategies targeting the first 90 minutes of the New York session (9:30–11:00 ET). The system simulates trades based on a unified hybrid strategy combining three source frameworks (Casper SMC, ProRealAlgos, Jdub Trades).

### Current Maturity and Operational State
- **Maturity:** Production-ready with active automation (daily runs, weekly batches)
- **State:** Operational; actively used for live strategy evaluation
- **Version:** v1.0 (as defined in config/settings.yaml)

### Top 3 Issues or Opportunities
1. **No automated test suite** — No pytest or unit tests exist; all validation is manual via dashboard
2. **yfinance data dependency** — Limited to ~30 days of 1m data and ~60 days of 5m data; no institutional-grade data source
3. **DXY filter dependency** — External bias filter relies on Yahoo Finance DXY symbol; could fail silently if symbol delists or changes

### Analysis Mode and Confidence
- Mode: Deep (full audit across all sections)
- Confidence: High (verified via code inspection, documentation review, and configuration analysis)

---

## 2. Project Map

### Major Modules and Their Responsibilities

| Module | Directory | Responsibility |
|---|---|---|
| **data** | `data/` | Data ingestion (yfinance + CSV), validation, core dataclasses |
| **engine** | `engine/` | Backtesting core: session gating, OR calculation, signal detection, trade resolution |
| **risk** | `risk/` | Position sizing, circuit breakers (daily loss limit, profit factor floor) |
| **journal** | `journal/` | Result recording, metrics calculation, run reports, execution logs |
| **dashboard** | `dashboard/` | Streamlit web UI for interactive backtesting and result exploration |
| **selector** | `selector/` | Pre-session symbol ranking and selection based on ATR and PF filters |
| **config** | `config/` | YAML settings, changelog |
| **Workflow** | `Workflow/` | Skill-based project review workflow documentation |

### High-Level Architecture Shape
```
┌─────────────────────────────────────────────────────┐
│                   CLI / Dashboard                   │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼──────────┐
              │   backtest_job   │  (orchestration)
              └────────┬──────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────▼────┐      ┌─────▼────┐     ┌────▼──────┐
│ selector │      │ Backtester│     │ Journal   │
│ (pre-run)│      │  (core)  │     │ (outputs) │
└──────────┘      └─────┬────┘     └───────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    ┌────▼────┐   ┌─────▼────┐  ┌────▼────┐
    │ signals │   │  trade   │  │ circuit │
    │         │   │          │  │ breaker │
    └─────────┘   └──────────┘  └─────────┘
```

### External Integrations and System Boundaries
- **Data Source:** Yahoo Finance (yfinance) for equities, indices, forex, and gold
- **Optional CSV Input:** User-supplied OHLCV files for custom forex/backtest data
- **Automation:** Windows Task Scheduler via PowerShell scripts
- **Output:** Local filesystem (results/) — no cloud storage or API integration
- **Dashboard:** Local Streamlit app on localhost:8501

---

## 3. How the System Works

### Primary Workflows

#### 3.1 Backtesting Flow (main.py / daily_run.py)
1. Load configuration from `config/settings.yaml`
2. Build instrument list (equities, optional CSV forex)
3. For each instrument and date:
   - Fetch intraday data (1m/5m bars) via yfinance
   - Fetch daily data for ATR calculation
   - Gate to NY session window (9:30–11:00 ET)
   - Calculate opening range from first N-minute candle
   - Compute 14-day ATR
   - Determine strategy mode (Breakout / Manipulation / Mean Reversion)
   - Detect signal via pattern matching
   - If signal: resolve trade bar-by-bar with position sizing
   - Apply circuit breaker checks
   - Record session summary
4. Generate output artifacts (trade_log.csv, session_log.csv, run_report.txt, execution_log.json)

#### 3.2 Pre-Session Selection Flow
1. Run before market open (09:25 ET) via scheduler
2. Load tracked universe (14 symbols: equities, indices, forex, gold)
3. Fetch 14-day ATR and trading history for each symbol
4. Apply filters: profit factor >= 1.5, spread data quality
5. Rank remaining symbols by ATR
6. Select Top-N (default: 3) symbols for the session
7. Freeze selection for the day (avoids intraday selection drift)

#### 3.3 Dashboard Flow (dashboard/app.py)
1. Streamlit app loads default config
2. User configures date range, strategy parameters, and equity selection via sidebar
3. Backtester runs with user parameters
4. Results displayed: equity curve, trade journal, metrics panels, mode breakdown
5. Weekly views: long-view equity trends, batch reports
6. Results Manager: browse, move to trash, restore, permanently delete past runs

### Data Flow
```
yfinance API / CSV → data/fetcher → pandas DataFrame
                                          ↓
                              Backtester (per session)
                                          ↓
            ┌─────────────────────────────┼─────────────────────────────┐
            ↓                             ↓                             ↓
    signals.py (detect)          engine/trade.py (resolve)     circuit_breaker.py
            ↓                             ↓                             ↓
    SignalContext                  TradeResult                  halt events
                                          ↓
                              JournalRecorder → filesystem
                                          ↓
                            trade_log.csv, session_log.csv,
                            run_report.txt, execution_log.json
```

### Failure Paths and Fallback Behavior
- **yfinance fetch failure:** Falls back from 1m to 5m bars; logs warning
- **Empty data:** Session skipped with "no data" reason in execution log
- **No signal:** Session logged as NO_TRADE with rejection reasons
- **Daily loss limit breached:** Circuit breaker halts further entries for that day
- **Profit factor below floor:** System halts and requires manual review
- **Pre-session selection returns empty:** Falls back to configured instruments if enabled

---

## 4. Capability Matrix

| Capability | Status | Confidence | Key Dependencies | Notes |
|---|---|---|---|---|
| Opening range calculation | Implemented | High | SessionGate, pandas | Supports 5m and 15m candles |
| ATR calculation | Implemented | High | yfinance daily data | 14-day period fixed |
| Manipulation mode detection | Implemented | High | Hammer/Engulfing pattern detection | Threshold: 25% ATR |
| Breakout mode detection | Implemented | High | Full-body candle detection | Retest confirmation required |
| Mean reversion fallback | Implemented | High | Failed breakout detection | Also 20 MA deviation for QQQ/GC=F |
| Displacement gap entry | Implemented | Medium | ATR size and body filters | Configurable min thresholds |
| Multi-timeframe trend alignment | Implemented | High | EMA on 1m/5m/15m bars | Can be disabled |
| DXY external bias filter | Implemented | Medium | Yahoo Finance DXY symbol | Only for EUR/GBP pairs |
| Fibonacci zone filter | Implemented | Medium | OR boundaries | Reversal TP at 38.2% level |
| Dynamic stop loss | Implemented | High | ATR on 1m bars | Multiplier: 1.75x |
| Position sizing (1% fixed-fractional) | Implemented | High | Current equity | Risk percentage hard-coded to 1% |
| Concurrent 2R/3R tracking | Implemented | High | TradeResult dataclass | Both tracked from same entry |
| Partial profit taking | Implemented | High | 50% scale at 1R | Move SL to BE after partial |
| Daily loss circuit breaker | Implemented | High | Session equity tracking | 5% hard limit |
| Profit factor circuit breaker | Implemented | High | Rolling PF calculation | Activates after 10 trades |
| Pre-session symbol selection | Implemented | High | yfinance history, ATR | Top-N ranking |
| Selection freezing | Implemented | High | JSON snapshot | Prevents intraday drift |
| CSV data ingestion | Implemented | High | pandas | Case-insensitive columns |
| Trade log CSV export | Implemented | High | pandas | Complete trade record |
| Session log CSV export | Implemented | High | pandas | Includes no-trade sessions |
| Prose run report | Implemented | High | journal/run_report.py | Third-person narrative |
| JSON execution log | Implemented | High | json module | Per-session decision audit |
| Config snapshot per run | Implemented | High | pyyaml | Version stamped |
| Changelog snapshot per run | Implemented | High | shutil | For traceability |
| Streamlit web dashboard | Implemented | High | streamlit, plotly | Localhost only |
| Equity curve visualization | Implemented | High | plotly | 2R and 3R overlaid |
| Weekly batch reporting | Implemented | High | weekly_batch.py | Aggregated weekly analysis |
| Daily automation (Windows) | Implemented | High | PowerShell scripts | Task Scheduler integration |
| Intraday 15m automation | Implemented | High | PowerShell scheduler | Runs during 09:25-11:00 |
| Automated test suite | Missing | High | — | No pytest/tests directory |
| Live trading execution | Missing | High | — | Backtesting only |
| Institutional data source | Missing | Medium | — | yfinance only; ~30 day 1m limit |

---

## 5. Dependency and Operations Posture

### Build, Test, and Deployment Model
- **Installation:** pip install -r requirements.txt
- **Runtime:** Python 3.11+; no build step required
- **Deployment:** Local only; no containerization or remote deployment
- **Testing:** No automated tests; manual validation via dashboard

### Observability, Monitoring, and Alerting Posture
- **Logging:** Python stdlib logging; configurable log level (DEBUG/INFO/WARNING/ERROR)
- **Output artifacts:** Structured files (CSV, JSON, TXT, YAML) for each run
- **Dashboard:** Real-time visualization of equity curve, metrics, trade journal
- **No external monitoring:** No Prometheus, Grafana, or alerting integration

### Maintenance Sustainability Signals

| Signal | Status | Notes |
|---|---|---|
| Stale dependencies | Low risk | Requirements specify minimum versions; no known security advisories |
| Missing owners | Low risk | Single-owner project; clear documentation of responsibilities |
| Undocumented processes | Low risk | Comprehensive README, beginner guide, changelog |
| Single points of failure | Medium risk | yfinance API is critical; no fallback if Yahoo changes/delists symbols |
| Technical debt | Low-Medium | Signals module has complex nested logic; refactor candidate for clarity |
| Test coverage | **High risk** | Zero automated tests; all validation is manual |

---

## 6. Risk Register

| Severity | Finding | Operational Impact | Evidence | Confidence |
|---|---|---|---|---|
| **High** | No automated test suite | Changes to strategy logic cannot be validated automatically; regression risk is high | No test files found in repository | High |
| **High** | yfinance data dependency — 1m bars limited to ~30 days | Cannot run long-duration intraday backtests without chunking; 5m fallback may reduce signal quality | yfinance documentation; backtester.py:260-271 fallback logic | High |
| **Medium** | DXY symbol (DX-Y.NYB) could delist or change | DXY filter would silently pass/fail differently; may affect EUR/GBP pair direction bias | Source: config/settings.yaml; code: backtester.py:286-301 | Medium |
| **Medium** | No CI/CD pipeline | Code changes require manual testing; no automated quality gates | No .github/workflows, Jenkinsfile, or similar | High |
| **Medium** | signals.py complexity — 900+ lines with multiple nested conditions | Hard to audit, test, or modify without introducing bugs | engine/signals.py:901 lines | High |
| **Low** | Config allows risky parameter overrides (e.g., 0% displacement_min_atr_pct) | Gaps could qualify without minimum size; allows high-frequency low-quality entries | config/settings.yaml:67-69; engine/signals.py:402-408 | High |
| **Low** | Session gate (11:00 ET) is hard-coded in config, not parameter | Cannot easily experiment with different session windows | config/settings.yaml:19; dashboard/app.py:336 | High |
| **Low** | No rate limiting or retry logic on yfinance fetches | Multiple symbols with long date ranges could trigger API throttling | data/fetcher.py uses raw yfinance without backoff | Medium |

---

## 7. Prioritized Recommendations

| Timeline | Recommendation | Expected Impact | Direction | Effort |
|---|---|---|---|---|
| **Quick win** | Add basic pytest tests for signal detection logic | Reduce regression risk when modifying signals.py | Test engine/signals.py pattern detection functions in isolation | S |
| **Quick win** | Document yfinance limitations in README | Prevent user frustration from unexpected data gaps | Add data availability notes section | S |
| **Near-term** | Implement test suite for backtester core | Validate trade resolution, circuit breakers, position sizing | Create tests/ directory; test engine/trade.py, risk/circuit_breaker.py | M |
| **Near-term** | Add retry/backoff logic to yfinance fetcher | Improve reliability for long batch runs across many symbols | Wrap fetch_intraday_chunked with tenacity or manual retry | M |
| **Near-term** | Parameter validation at load time | Prevent invalid configs (e.g., displacement_min_atr_pct=0) from silently affecting behavior | Add validation in backtest_job.py or Backtester.__init__ | M |
| **Strategic** | Extract signals.py into separate classes | Improve testability and reduce cognitive load | Refactor into ModeDetector classes (BreakoutMode, ManipulationMode, MeanReversionMode) | L |
| **Strategic** | Add institutional data source option (Polygon.io) | Remove yfinance limitations for professional backtesting | Extend data/fetcher.py with Polygon REST client | XL |

---

## 8. Transition Readiness

### Components or Artifacts That Are Reusable and Well-Documented
- **Core backtesting engine (engine/)** — Well-structured, data-source agnostic; only data/fetcher.py knows about yfinance
- **Risk management module (risk/)** — Standalone CircuitBreaker and position sizer; can be reused in live trading systems
- **Configuration-driven design** — All parameters in YAML; strategy changes without code modification
- **Journal output system** — Structured CSV/JSON/TXT outputs; ready for ingestion by external systems
- **Dashboard UI** — Clean Streamlit implementation; theme customization and responsive layout

### Gaps That Must Be Closed Before Safe Migration or Handoff
1. **Test coverage is zero** — Any builder inheriting this codebase must add tests before modifying strategy logic
2. **No deployment automation** — Local-only; no Docker, no CI/CD; handoff assumes local Windows environment
3. **Hard-coded assumptions** — Session times, DXY symbol, and Yahoo dependency are implicit; must be documented for external builders

### Minimum Next Steps for the Receiving Builder or Team
1. Add a test suite covering at least the signal detection and risk management modules
2. Document the yfinance data limitations and upgrade path to institutional data
3. Review signals.py for refactoring opportunities; target: <300 lines per mode class

---

## 9. Assumptions and Unknowns

### Explicit Assumptions Made Where Evidence Was Missing
- **Windows-only automation assumed** — PowerShell scripts and Task Scheduler are Windows-specific; assumed from run_daily.ps1, run_intraday.ps1, register_intraday_task.ps1
- **Python 3.11+ required** — Stated in README; not verified against requirements.txt (which specifies pandas>=2.0.0, which requires Python 3.9+)
- **Single-user operation** — No authentication on dashboard; no multi-user considerations
- **No cloud deployment target** — All paths assume local filesystem; no AWS/GCP/Azure references found

### Items That Could Not Be Assessed and Why
- **Actual backtest performance** — No live run data examined; metrics are configuration-based (benchmarks from README)
- **API rate limit behavior** — yfinance rate limiting not tested; chunking logic mitigates but not characterized
- **Symbol delist/change risk** — DXY (DX-Y.NYB) and other Yahoo symbols not verified against current availability
- **Python version compatibility** — requirements.txt lacks upper bounds; Python 3.11+ assumed but not enforced

### What Additional Access or Context Would Improve Confidence
- **Live run data samples** — Actual trade_log.csv and execution_log.json from recent runs would confirm signal quality
- **Historical performance metrics** — Weekly batch reports would reveal strategy drift over time
- **Dashboard usage patterns** — How often the app is used, what parameters users change most
- **Git history** — Would reveal evolution of strategy logic and which changes caused performance shifts

---

*Artifact generated by Project Overview skill (Deep mode)*
*Compatible with: Antigravity, Cursor, Windsurf, Claude, and any agent-capable tool*
