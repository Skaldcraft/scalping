# Handoff Package: Precision Scalping Utility
**Package Version:** v1.0  
**Date:** 2026-04-11  
**Gatekeeper Decision:** Conditional (71/100, Hold Cycle 1 of 2)

---

## 1. Package Metadata

| Field | Value |
|---|---|
| **Project** | Precision Scalping Utility (PulseTrader) |
| **Date** | 2026-04-11 |
| **Package Version** | v1.0 |
| **Gatekeeper Decision** | Conditional — All 5 gates pass (G4: Conditional Pass); Score: 71/100 |
| **Producing Builder Role** | Technical Lead |
| **Receiving Builder Role** | Receiving Builder (as defined in Implementation Guide Section 5) |
| **Changelog** | (v1.0 — Initial package; no prior versions) |

---

## 2. Executive Transfer Summary

This package hands off a fully documented, production-capable trading backtesting engine. The project — named PulseTrader — mechanically simulates opening-range scalping strategies during the first 90 minutes of the New York trading session using data from Yahoo Finance. It generates trade journals, equity curves, run reports, and an interactive Streamlit dashboard.

The project is **conditionally ready** for full execution. Five readiness gates all pass, but Gate G4 received a Conditional Pass because three Medium-severity security and configuration issues remain open: a CSV injection vulnerability in data ingestion, missing input validation on dashboard parameters, and an unresolved CVE in the pyyaml dependency. All three are addressable in under one sprint of effort.

**The single most important thing to know before opening anything else:** The project has zero automated tests. Every change to strategy logic carries unmitigated regression risk. ACT-001 (add basic signal detection tests) must be the first action taken — it unblocks all subsequent strategy modifications.

**What this package includes:** Complete architecture documentation, a prioritized action plan with 8 items, a risk register with 8 findings, a security review with 8 vulnerabilities, and a day-by-day first-week guide.

**What this package does not include:** A completed test suite, a deployed CI/CD pipeline, or an institutional data source. These are all on the execution plan.

---

## 3. Source Traceability

| Artifact | Date | Coverage Status | Confidence |
|---|---|---|---|
| Project Overview | 2026-04-11 | Complete (9 sections, all required) | High |
| Project Action Planner | 2026-04-11 | Complete (8 actions, all priority groups) | High |
| Readiness Gatekeeper | 2026-04-11 | Complete (5 gates, all evaluated) | High |
| Security Review | 2026-04-11 | Present (8 findings, all domains analyzed) | Medium |

---

## 4. Current-State Snapshot

### Architecture and Capability Highlights

**What the project does:** The Precision Scalping Utility backtests a unified hybrid scalping strategy that combines three source frameworks (Casper SMC, ProRealAlgos, Jdub Trades). It operates exclusively during the New York session (9:30–11:00 ET) and evaluates opening-range setups on a fixed universe of 14 instruments (equities, indices, forex, gold).

**Core capabilities implemented:**
- Opening range calculation (5m and 15m candle options)
- Three strategy modes: Breakout, Manipulation (reversal), Mean Reversion
- Concurrent 2:1 and 3:1 reward ratio tracking from the same entry
- Multi-timeframe trend alignment (EMA on 1m/5m/15m bars)
- DXY external bias filter for EUR/GBP pair direction
- Fibonacci zone gating with dynamic stop loss
- Pre-session symbol selection (Top-N ranking by ATR and profit factor)
- Circuit breakers: daily loss limit (-5%) and profit factor floor (1.5 after 10 trades)
- Interactive Streamlit dashboard with equity curves, trade journal, and weekly views
- Daily and intraday automation via Windows Task Scheduler

**Technology stack:**
- Python 3.11+, pandas, numpy, plotly, streamlit, yfinance, pyyaml
- No containerization; local Windows deployment

### Dependency and Operational Posture Summary

| Area | Status |
|---|---|
| Installation | Works — `pip install -r requirements.txt` |
| CLI execution | Works — `python main.py --start YYYY-MM-DD --end YYYY-MM-DD` |
| Dashboard | Works — `python -m streamlit run dashboard/app.py` |
| Daily automation | Works — PowerShell scripts + Task Scheduler (Windows only) |
| Test coverage | **None** — Zero automated tests |
| CI/CD | **None** — No pipeline exists |
| Dependency pinning | Partial — No upper bounds in requirements.txt |
| Secrets management | Clear — No secrets currently present |

### Top 3 Active Risks

| # | Risk | Severity | Mitigation Status | Notes |
|---|---|---|---|---|
| 1 | pyyaml CVE-2020-14343 (arbitrary code execution in <6.0.1) | **Critical (historical)** | **Open** | Must verify 6.0.1+ is installed; pin in requirements.txt |
| 2 | Zero automated test coverage | High | Open | ACT-001 is first action in the plan |
| 3 | CSV injection in user-supplied data files | Medium | Open | SEC-002; fix is ACT-005 (near-term) |

---

## 5. Prioritized Execution Plan

### Now (Quick wins) — Execute in Week 1

| ID | Title | Owner | Effort | First Action |
|---|---|---|---|---|
| ACT-001 | Add basic pytest tests for signal detection | QA Engineer | S | Create `tests/` directory; install pytest; write first test for `_is_hammer()` |
| ACT-002 | Document yfinance data limitations in README | Documentation Lead | S | Add "Data Availability" section to README.md with 1m/5m limits |
| ACT-003 | Add parameter validation at config load time | Backend Engineer | S | Add `validate_config()` function in backtest_job.py; write test cases |

### Next (Near-term) — Execute in Weeks 2–3

| ID | Title | Owner | Effort | Prerequisite |
|---|---|---|---|---|
| ACT-004 | Implement test suite for backtester core | QA Engineer | M | ACT-001 (test infrastructure must exist) |
| ACT-005 | Add retry/backoff logic to yfinance fetcher | Backend Engineer | M | ACT-003 (validation should be stable first) |
| ACT-006 | Review and document DXY symbol dependency | Technical Lead | S | None |

### Later (Strategic roadmap)

| ID | Title | Rationale | Prerequisite | Effort |
|---|---|---|---|---|
| ACT-007 | Refactor signals.py into mode classes | 900+ lines; hard to test; refactor improves maintainability | ACT-004 (tests in place first) | L |
| ACT-008 | Plan institutional data source upgrade (Polygon.io) | yfinance limits backtest scope (~30 days 1m); institutional data enables longer runs | ACT-006 (DXY dependency documented) | XL |

### Dependency Sequence (from Action Planner)

```
Week 1 (Parallel):
  ACT-001 (signal tests) ──┐
  ACT-002 (README docs)    ├─ No dependencies — run all three in parallel
  ACT-003 (param validation)─┘

Week 2-3:
  ACT-004 (backtester tests) ← requires ACT-001
  ACT-005 (retry/backoff)   ← requires ACT-003
  ACT-006 (DXY docs)        ← no dependencies; parallel with ACT-004/005

Week 4+:
  ACT-007 (signals.py refactor) ← requires ACT-004
  ACT-008 (institutional data) ← requires ACT-006
```

---

## 6. Risk and Control Register

| ID | Risk | Severity | Mitigation Status | Quality Gate | Rollback Note |
|---|---|---|---|---|---|
| SEC-001 | Dashboard unauthenticated (local only) | Medium | Open | Add warning banner on non-loopback access | Remove banner; no data changes |
| SEC-002 | CSV injection from user-supplied files | Medium | Open (fix: ACT-005) | Formula-prefixed cells rejected; test case added | Revert to raw pd.read_csv() |
| SEC-003 | No dashboard input bounds validation | Medium | Open (fix: ACT-003) | Out-of-range inputs produce error; no crash | Remove min/max from sidebar inputs |
| SEC-004 | No dependency CVE scanning in CI | Low | Open | pip-audit in CI; requirements.txt pinned | Remove pip-audit step |
| SEC-005 | Secrets may be logged in plaintext | Low | Suspected | API keys from env vars only; no full config logging | Revert logging changes |
| SEC-006 | results/ not in .gitignore | Low | Open | `git check-ignore results/` confirms | Remove from .gitignore |
| SEC-007 | unsafe_allow_html in dashboard | Low | Open | Remove flag; use native Streamlit components | Re-add flag |
| SEC-008 | PowerShell scripts run with full user privileges | Low | Open | Document least-privilege automation user | Revert to original account |
| pyyaml CVE | CVE-2020-14343 in pyyaml<6.0.1 | **Critical** | **Open (fix: ACT-003)** | `pip show pyyaml` shows 6.0.1+; requirements.txt pinned | Revert to >=6.0 |
| Overview-01 | yfinance 1m data limited to ~30 days | Medium | Accepted | Documented in README; CSV fallback path exists | N/A |
| Overview-02 | DXY symbol (DX-Y.NYB) dependency | Medium | Open (fix: ACT-006) | Documented in README with upgrade path | N/A |
| Overview-03 | signals.py complexity (900+ lines) | Medium | Open (fix: ACT-007) | Refactored to <300 lines per mode class | Revert refactor |
| Overview-04 | No CI/CD pipeline | Medium | Accepted | No pipeline; manual validation | N/A |

### Flagged Open Risks Requiring Explicit Acceptance

| ID | Risk | Severity | Requires Acceptance? | Acceptance Rationale |
|---|---|---|---|---|
| pyyaml CVE | Arbitrary code execution in pyyaml<6.0.1 | Critical | **Yes — before any runs** | Known CVE; fix is trivial; no operational impact |
| SEC-002 | CSV injection in user-supplied files | Medium | **Yes — before CSV ingestion is used** | Affects users who provide custom CSV data |
| SEC-003 | Dashboard input validation gap | Medium | **Yes — before parameter experimentation** | Affects users who change strategy parameters |
| Overview-01 | yfinance data limits | Medium | **Yes — before long backtests** | Affects backtest duration and accuracy |
| Overview-04 | No CI/CD | Medium | **Yes — before any code changes** | Affects regression risk on all changes |

---

## 7. Mandatory Conditions

Pulled verbatim from Readiness Gatekeeper artifact (Section 5). These must be resolved before or during the first week.

| Fix | Rationale | Owner | Acceptance Criterion | Effort |
|---|---|---|---|---|
| **Verify pyyaml>=6.0.1 and pin in requirements.txt** | CVE-2020-14343 affects pyyaml<6.0.1; requirements.txt allows 6.0.0 which is vulnerable | Backend Engineer | `pip show pyyaml` shows Version: 6.0.1 or later; requirements.txt shows `pyyaml>=6.0.1` (exact pin) | S |
| **Add basic pytest tests for signal detection (ACT-001)** | Zero test coverage is the top operational risk; must establish baseline before any strategy changes | QA Engineer | `pytest tests/test_signals.py -v` passes; ≥70% line coverage on signals.py | S |
| **Add parameter validation at config load time (ACT-003)** | Invalid config values (e.g., displacement_min_atr_pct=0 or 150) are silently accepted; prevents misconfiguration | Backend Engineer | Invalid config raises ConfigValidationError with field name and valid range | S |
| **Add input bounds validation on dashboard (SEC-003)** | Unbounded sidebar inputs can crash or misbehave; confirmed Medium security finding | Frontend Engineer | Out-of-range inputs (dates >1yr, capital >$10M, risk>5%) produce clear error; no crash | S |
| **Add CSV sanitization to data/fetcher.py (SEC-002)** | Formula injection payloads in user-supplied CSVs are processed unsafely; confirmed Medium security finding | Backend Engineer | CSV with `=cmd|'/C calc'!A0` payload rejected or sanitized; test case added | M |

### What Is Permitted to Proceed Now

| Activity | Status | Controls |
|---|---|---|
| Dashboard usage (local, localhost only) | Permitted | Warning banner required; no external access |
| CLI runs with existing default config | Permitted | Do not change parameters until ACT-003 merged |
| Daily/weekly automation (as-is) | Permitted | No changes to automation scripts |
| Reading and analyzing results | Permitted | No restrictions |

### What Is NOT Permitted

| Activity | Until |
|---|---|
| Any modification to strategy logic | ACT-001 (signal tests) is merged |
| Modifications to data/fetcher.py | SEC-002 (CSV sanitization) is merged |
| Parameter experimentation via dashboard | SEC-003 (input validation) is merged |
| Running with new/custom CSV data files | SEC-002 is merged |
| Any change to Python dependencies | pyyaml is verified and pinned |

---

## 8. First-Week Start Guide

### Day 1 — Verify and Orient

**Objective:** Confirm environment access, validate pyyaml CVE status, and establish baseline understanding.

**Actions:**
1. Clone repository and verify branch permissions
2. Run `pip show pyyaml` — confirm Version is 6.0.1 or later
3. If Version < 6.0.1: `pip install pyyaml>=6.0.1` immediately; update requirements.txt to `pyyaml==<installed_version>`
4. Run a baseline backtest: `python main.py --start 2024-10-01 --end 2024-12-31`
5. Launch dashboard: `python -m streamlit run dashboard/app.py` — confirm it loads at localhost:8501
6. Run `pytest --collect-only` to confirm no tests exist yet (expected state)

**Required inputs:** Python 3.11+, pip, git access, internet connection (for yfinance)
**End-of-day check:** Does the baseline backtest complete without errors? Is the dashboard accessible?

---

### Day 2 — Document Data Limits and Validate Configuration

**Objective:** Address ACT-002 (README documentation) and ACT-003 (parameter validation).

**Actions:**
1. Add "Data Availability" section to README.md covering: yfinance 1m (~30 days), 5m (~60 days) limits; CSV fallback path; Polygon.io as upgrade recommendation
2. Add `validate_config()` function to backtest_job.py validating: displacement_min_atr_pct (0-100), displacement_min_body_pct (0-100), risk_pct (0-5), daily_loss_limit_pct (0-20)
3. Raise `ConfigValidationError` with field name and valid range for violations
4. Test: run backtest with `displacement_min_atr_pct=150` in config — confirm clear error
5. Run backtest with default config — confirm no error

**Required inputs:** README.md, backtest_job.py, valid default config
**End-of-day check:** Does README document data limits? Does invalid config raise a clear error?

---

### Day 3 — Establish Test Infrastructure

**Objective:** Address ACT-001 (basic signal tests). This is the most important action in the entire plan.

**Actions:**
1. Create `tests/` directory in project root
2. Install pytest: `pip install pytest pytest-cov`
3. Create `tests/test_signals.py` with fixtures for synthetic OHLCV data
4. Write first test: `_is_hammer()` returns True for valid hammer, False for non-hammer
5. Write tests for: `_is_bullish_engulfing()`, `_is_valid_retest_long()`, `_is_valid_retest_short()`
6. Run `pytest tests/test_signals.py -v --cov=engine.signals --cov-report=term-missing`
7. Target: ≥70% line coverage on signals.py

**Required inputs:** engine/signals.py, data/models.py, pytest installed
**End-of-day check:** Do all signal detection tests pass? Is coverage report ≥70% on signals.py?

---

### Day 4 — Dashboard Input Bounds and CSV Sanitization

**Objective:** Address SEC-003 (dashboard validation) and start SEC-002 (CSV sanitization).

**Actions:**
1. Add min/max constraints to all `st.sidebar.number_input` calls in dashboard/app.py:
   - `starting_capital`: 1000–1,000,000
   - `risk_pct`: 0.25–5.0
   - `daily_loss_pct`: 1.0–10.0
   - `commission`: 0.0–10.0
   - `displacement_min_atr_pct`: 0.0–20.0
   - `displacement_min_body_pct`: 0.0–100.0
2. Validate `end_date - start_date <= 365 days`; show error if exceeded
3. Test: enter capital=$999,999,999 — confirm error message displayed
4. In data/fetcher.py: add sanitization to `load_csv()` that rejects cells starting with `=`, `+`, `-`, `@` unless the cell is quoted
5. Create `tests/test_csv_sanitization.py` with formula injection test case: CSV containing `=cmd|'/C calc'!A0`

**Required inputs:** dashboard/app.py, data/fetcher.py
**End-of-day check:** Do out-of-range dashboard inputs produce clear errors? Does CSV with formula injection get rejected?

---

### Day 5 — Review and Commit

**Objective:** Consolidate all Week 1 fixes, run end-to-end validation, and prepare for Week 2.

**Actions:**
1. Run full test suite: `pytest tests/ -v --cov=engine,risk --cov-report=term`
2. Verify pyyaml is pinned in requirements.txt (exact version, not >=)
3. Run a complete backtest with default config — confirm it still works
4. Launch dashboard — confirm it still loads with the new bounds
5. Load a test CSV with formula injection — confirm it's rejected
6. Review all open items from Risk Register
7. Prepare git commit with all changes: ACT-001, ACT-002, ACT-003, SEC-002, SEC-003, pyyaml fix
8. Schedule re-review checkpoint for 2026-04-25

**Required inputs:** All test files, requirements.txt, git repository
**End-of-day check:** Does `pytest` pass? Does pyyaml show 6.0.1+? Does requirements.txt show exact pin? Is the dashboard functional? Is the git commit ready?

---

## 9. Re-Review and Governance Plan

### Checkpoint Cadence

| Checkpoint | Date | Scope | Owner |
|---|---|---|---|
| Re-Review 1 | 2026-04-25 | Verify all 5 mandatory fixes resolved; assess progress on ACT-004, ACT-005, ACT-006 | Technical Lead |
| Re-Review 2 | 2026-05-09 | Verify ACT-004 (backtester tests) merged; assess ACT-007 (signals refactor) readiness | Technical Lead |
| Final Review | 2026-05-23 | Target: Proceed decision; all gates pass | Technical Lead |

### Acceptance Criteria for Conditional Conditions

All five mandatory fixes must be verified at the 2026-04-25 re-review:

| Fix | Verification Method |
|---|---|
| pyyaml pinned to >=6.0.1 | `pip show pyyaml` output in PR or artifact |
| ACT-001 signal tests | pytest output showing ≥70% coverage on signals.py |
| ACT-003 param validation | PR showing ConfigValidationError raised on invalid input |
| SEC-003 dashboard bounds | Manual test evidence with screenshot of error message |
| SEC-002 CSV sanitization | Test case passes; formula injection rejected |

### Trigger Conditions for Returning to Gatekeeper

| Trigger | Action |
|---|---|
| pyyaml CVE confirmed in installed version | Return immediately; halt all runs |
| ACT-001 tests fail after implementation | Return to Gatekeeper; block strategy changes |
| CSV injection confirmed in output files | Return immediately; halt CSV ingestion |
| New Critical or High security finding discovered | Return to Gatekeeper; reassess decision |
| yfinance API changes break core functionality | Return to Gatekeeper; reassess data dependency |

### Governance Owner

**Technical Lead** is responsible for monitoring compliance with conditional controls, scheduling re-review checkpoints, and surfacing `ESCALATION_REQUIRED` if Hold-2 is not resolved.

---

## 10. Open Unknowns and Assumptions

### Consolidated from All Source Artifacts

| Source | Unknown | Impact | Recommended Action |
|---|---|---|---|
| Project Overview | **Real-world DXY filter effectiveness** | Cannot assess what % of trades are filtered; may be removing valid setups | Run `jq '.[] \| select(.dxy_filter_confirmed == false)'` on recent execution_log.json files; analyze filter acceptance rate |
| Project Overview | **signals.py refactor effort** | L vs XL effort unconfirmed; affects sprint planning | 2-hour spike by Technical Lead before committing to ACT-007 |
| Project Overview | **yfinance API stability** | Symbol delist/change could silently break DXY filter and data fetching | Monitor yfinance changelog; subscribe to Yahoo Finance API announcements |
| Project Overview | **Python version compatibility** | requirements.txt lacks upper bounds; 3.11+ assumed | Add `python_requires='>=3.11'` to setup.py or pyproject.toml |
| Security Review | **pyyaml CVE verification** | Requires running `pip show pyyaml` — not verified in artifact review | Run on Day 1; update immediately if < 6.0.1 |
| Security Review | **No SAST scan performed** | No Bandit or equivalent run; security review is static only | Run `bandit -r engine/ risk/ data/` as first security action |
| Security Review | **CSV injection impact scope** | Who is using CSV ingestion? Are any production runs using custom CSV data? | Survey existing results/ folders for CSV-based runs; assess exposure |
| Security Review | **PowerShell script modification risk** | Can scripts be tampered with by local users? | Review filesystem permissions on run_daily.ps1, run_intraday.ps1 |
| Action Planner | **Bandit SAST results** | Not run; potential findings unknown | Run in Week 1 as part of ACT-001 |
| Action Planner | **pip-audit results** | Not run; potential CVE findings unknown | Run `pip-audit -r requirements.txt` in Week 1 |
| Gatekeeper | **Results data directory isolation** | Are results shared across users? What's the exposure if results/ is committed to git? | Verify .gitignore; audit results/ usage patterns |

---

*Package Version: v1.0 | Produced: 2026-04-11 | Gatekeeper Decision: Conditional*
*Source artifacts: scalping-utility_project-overview_20260411.md, scalping-utility_project-action-planner_20260411.md, scalping-utility_security-review_20260411.md, scalping-utility_readiness-gatekeeper_20260411.md*
*Next Re-Review: 2026-04-25 | Owner: Technical Lead*
