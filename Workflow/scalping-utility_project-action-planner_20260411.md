# Project Action Planner Artifact
**Mode:** Delivery  
**Source Artifacts:** Project Overview (scalping-utility_project-overview_20260411.md, 2026-04-11)  
**Date:** 2026-04-11  
**Confidence:** High  

---

## 1. Planning Summary

### Mode Used
Delivery — Full sprint-oriented plan with sequenced dependency chains, ownership, and quality gates.

### Source Artifacts Consumed
| Artifact | Date | Sections Used |
|---|---|---|
| Project Overview | 2026-04-11 | Risk Register, Recommendations, Capability Matrix, Transition Readiness |

### Total Actions Identified
- **Now (Quick wins):** 3
- **Next (Near-term):** 3
- **Later (Strategic):** 2

### Top 3 Expected Outcomes if Now Actions Are Completed
1. **Regression risk reduced** — Automated tests for signal detection prevent unintended breakage when modifying the most complex module (signals.py)
2. **User expectations managed** — Data limitations documented in README reduces support burden and prevents user frustration
3. **Configuration integrity improved** — Parameter validation at load time prevents silent misbehavior from invalid configs

### Conflicts Resolved
No conflicts between upstream artifacts. The Project Overview identified the following overlapping concerns that were merged into single actions:
- Test coverage gap and signals.py complexity were identified in both Risk Register and Recommendations → consolidated into ACT-002 (test suite for backtester core)
- yfinance dependency was flagged in both Risk Register and Capability Matrix → single action (ACT-003, near-term)

---

## 2. Action Backlog

| ID | Title | Priority | Source Finding | Severity | Impact | Effort | Owner Profile |
|---|---|---|---|---|---|---|---|
| ACT-001 | Add basic pytest tests for signal detection | Now | No automated test suite | High | 5 | S | QA Engineer |
| ACT-002 | Document yfinance data limitations in README | Now | User-facing documentation gap | Low | 3 | S | Documentation Lead |
| ACT-003 | Add parameter validation at config load time | Now | Config allows risky overrides | Medium | 4 | S | Backend Engineer |
| ACT-004 | Implement test suite for backtester core | Next | Test coverage is zero | High | 5 | M | QA Engineer |
| ACT-005 | Add retry/backoff logic to yfinance fetcher | Next | No rate limiting or retry | Medium | 3 | M | Backend Engineer |
| ACT-006 | Review and document DXY symbol dependency | Next | DXY filter relies on Yahoo symbol | Medium | 3 | S | Technical Lead |
| ACT-007 | Refactor signals.py into mode classes | Later | 900+ lines with nested conditions | Medium | 4 | L | Backend Engineer |
| ACT-008 | Plan institutional data source upgrade | Later | yfinance limits backtest scope | Medium | 3 | XL | Technical Lead |

---

## 3. Dependency Map

### Prerequisite Chains
```
ACT-001 (basic signal tests)
    ↓
ACT-004 (full backtester test suite) [requires ACT-001 foundation]

ACT-003 (parameter validation)
    ↓
ACT-005 (retry/backoff logic) [validation must be stable before retry logic]

ACT-006 (DXY documentation)
    ↓
ACT-008 (institutional data upgrade) [documents current dependency before replacing it]
```

### Blockers
- **ACT-004 is blocked by ACT-001** — Basic test infrastructure must exist before expanding to full backtester coverage
- **ACT-008 is blocked by ACT-006** — Current DXY dependency must be documented before planning replacement

### Parallel Tracks
- **ACT-001, ACT-002, ACT-003 can run in parallel** — Independent modules; no shared state or dependencies
- **ACT-005 and ACT-006 can run in parallel** — Independent; data fetcher retry logic does not depend on DXY documentation
- **ACT-007 (signals.py refactor) has no dependencies** — Can start any time, but should follow ACT-004 (tests in place first)

### Suggested Execution Order
```
Week 1 (Parallel):
  - ACT-001: Basic signal detection tests
  - ACT-002: Document yfinance limitations
  - ACT-003: Parameter validation

Week 2-3:
  - ACT-004: Expand to full backtester test suite

Week 2 (Parallel with ACT-004):
  - ACT-005: Retry/backoff for yfinance
  - ACT-006: DXY dependency documentation

Week 4+:
  - ACT-007: signals.py refactor (if tests pass)

Later (Strategic):
  - ACT-008: Institutional data source upgrade
```

---

## 4. Action Packages (Now and Next)

### ACT-001: Add basic pytest tests for signal detection
- **Objective:** Establish automated test coverage for the signal detection module to reduce regression risk when modifying strategy logic.
- **Scope:** Test engine/signals.py pattern detection functions (hammer, engulfing, retest, breakout) in isolation with synthetic OHLCV data.
- **Owner Profile:** QA Engineer
- **Required Inputs:** engine/signals.py, data/models.py
- **Dependencies:** None
- **Parallel with:** ACT-002, ACT-003
- **Effort:** S (~1 day) — Pytest fixture setup for synthetic OHLCV; 5-8 test cases covering pattern functions
- **Risks and Mitigations:**
  - Risk: Tests may be too tightly coupled to implementation details
  - Mitigation: Test behavior (pattern detection pass/fail) not implementation (function signatures)
  - Risk: Synthetic data may not represent real market conditions
  - Mitigation: Add a comment that real-world validation is needed; tests cover logic, not data quality
- **Quality Gate:** `pytest` passes with 0 failures; coverage report shows ≥70% line coverage on signals.py
- **Rollback Note:** Revert to no test files; no migration or data changes involved
- **Acceptance Criteria:**
  - [ ] `pytest tests/test_signals.py -v` passes
  - [ ] Hammer detection returns True for valid hammer pattern, False otherwise
  - [ ] Engulfing detection handles bullish/bearish variants correctly
  - [ ] Retest detection handles boundary conditions (wick touch, body close outside)
  - [ ] Breakout detection distinguishes full-body vs. wick-only breaks

---

### ACT-002: Document yfinance data limitations in README
- **Objective:** Prevent user frustration by setting accurate expectations about data availability before they encounter gaps.
- **Scope:** Add a "Data Availability" section to README.md covering yfinance limits, CSV fallback path, and institutional data upgrade recommendation.
- **Owner Profile:** Documentation Lead
- **Required Inputs:** README.md, data/fetcher.py, config/settings.yaml
- **Dependencies:** None
- **Parallel with:** ACT-001, ACT-003
- **Effort:** S (~half day) — Writing section, reviewing with Technical Lead
- **Risks and Mitigations:**
  - Risk: Documentation becomes outdated if yfinance changes limits
  - Mitigation: Add version date to section; include "check yfinance documentation for current limits"
  - Risk: Users may ignore documentation
  - Mitigation: Add prominent warning at top of "Running from CLI" section
- **Quality Gate:** Section added to README.md with accurate data about yfinance limits (1m = ~30 days, 5m = ~60 days)
- **Rollback Note:** Remove the added section from README.md
- **Acceptance Criteria:**
  - [ ] README.md contains a "Data Availability" or "Data Limitations" section
  - [ ] Section explicitly states 1m and 5m history limits
  - [ ] Section includes CSV fallback instructions with a link to the relevant config section
  - [ ] Section mentions Polygon.io as an upgrade path

---

### ACT-003: Add parameter validation at config load time
- **Objective:** Prevent silent misbehavior from invalid configuration values that the current system accepts without error.
- **Scope:** Validate config values in backtest_job.py (or Backtester.__init__) before they are used. Validate: displacement_min_atr_pct (0-100), displacement_min_body_pct (0-100), risk_pct (0-5), daily_loss_limit_pct (0-20).
- **Owner Profile:** Backend Engineer
- **Required Inputs:** config/settings.yaml, backtest_job.py, engine/backtester.py
- **Dependencies:** None
- **Parallel with:** ACT-001, ACT-002
- **Effort:** S (~1 day) — Write validator function, integrate at config load, add unit tests for validation
- **Risks and Mitigations:**
  - Risk: Validation may break existing configs that use edge values
  - Mitigation: Log a warning for out-of-range values, don't hard-fail; allow override with --force flag
  - Risk: Hard-coded thresholds may be too restrictive
  - Mitigation: Define thresholds as constants at top of validator; document rationale for each
- **Quality Gate:** Invalid config raises a clear error with the offending field and acceptable range; valid config runs without errors
- **Rollback Note:** Comment out validation function calls in backtest_job.py; revert to original behavior
- **Acceptance Criteria:**
  - [ ] Config with displacement_min_atr_pct=150 raises ConfigValidationError
  - [ ] Config with displacement_min_body_pct=-5 raises ConfigValidationError
  - [ ] Valid config with all parameters in range loads without error
  - [ ] Warning logged (not error) for displacement_min_atr_pct=0 with explanation of risk

---

### ACT-004: Implement test suite for backtester core
- **Objective:** Comprehensive test coverage for Backtester, CircuitBreaker, and PositionSizer to enable confident modification of strategy logic.
- **Scope:** Test engine/backtester.py (session loop, signal orchestration), risk/circuit_breaker.py (daily loss halt, PF floor), risk/position_sizer.py (1% equity calculation). Use fixture-based synthetic data.
- **Owner Profile:** QA Engineer
- **Required Inputs:** engine/backtester.py, risk/circuit_breaker.py, risk/position_sizer.py, data/models.py
- **Dependencies:** ACT-001 (basic test infrastructure must exist)
- **Parallel with:** ACT-005, ACT-006
- **Effort:** M (~3-4 days) — Complex mocking of yfinance; fixture setup for session-level scenarios; edge case coverage
- **Risks and Mitigations:**
  - Risk: yfinance mocking is brittle and may break on library updates
  - Mitigation: Mock at the fetcher level (fetch_intraday, fetch_daily) not the network level; use responses library or monkeypatch
  - Risk: Test execution time may be long with many instruments/sessions
  - Mitigation: Use minimal synthetic datasets (2 instruments, 5 sessions) for logic tests; performance tests separate
- **Quality Gate:** `pytest tests/ -v` passes; CircuitBreaker test coverage ≥80%; Backtester session orchestration covered
- **Rollback Note:** Revert to empty tests/ directory; no production code changes
- **Acceptance Criteria:**
  - [ ] CircuitBreaker daily loss halt triggers at exactly -5% equity
  - [ ] CircuitBreaker PF floor activates after 10 trades
  - [ ] CircuitBreaker PF floor does NOT activate before 10 trades
  - [ ] PositionSizer returns correct size for $10,000 equity, 1% risk, $1.00 stop distance = 100 shares
  - [ ] Backtester skips session with no opening range bars
  - [ ] Backtester returns NO_TRADE for session with no signal
  - [ ] Backtester executes trade when valid signal detected

---

### ACT-005: Add retry/backoff logic to yfinance fetcher
- **Objective:** Improve reliability for long batch runs across many symbols by handling transient yfinance API failures gracefully.
- **Scope:** Wrap fetch_intraday and fetch_intraday_chunked in backoff/retry logic (exponential backoff, 3 retries, timeout per request). Log each retry attempt.
- **Owner Profile:** Backend Engineer
- **Required Inputs:** data/fetcher.py
- **Dependencies:** ACT-003 (parameter validation should be stable first)
- **Parallel with:** ACT-004, ACT-006
- **Effort:** M (~2-3 days) — Choose library (tenacity or manual); implement; test with injected failures
- **Risks and Mitigations:**
  - Risk: Backoff delays may make long batch runs significantly slower
  - Mitigation: Start with 2 retries, 1s initial backoff; adjust based on observed behavior
  - Risk: yfinance may return partial data that looks successful
  - Mitigation: Keep existing chunking logic; retry only on explicit errors, not empty results
- **Quality Gate:** Injected network failure triggers retry; after max retries, raises clear error with symbol and date range
- **Rollback Note:** Revert to original fetch functions without retry; remove tenacity import
- **Acceptance Criteria:**
  - [ ] Single yfinance failure triggers retry (log entry: "Retrying fetch for {symbol}...")
  - [ ] After 3 failures, raises FetchError with symbol and retry count
  - [ ] Successful fetch on retry does not raise error
  - [ ] Chunked fetches retry individual chunks independently

---

### ACT-006: Review and document DXY symbol dependency
- **Objective:** Clarify the role of the DXY (US Dollar Index) filter and its dependency on Yahoo Finance, so that users and builders understand the external dependency.
- **Scope:** Audit engine/backtester.py and config/settings.yaml for DXY usage. Document: which symbols are affected, what happens if DXY data is unavailable, and what the filter's historical accuracy has been. Recommend upgrade path if DXY symbol is unreliable.
- **Owner Profile:** Technical Lead
- **Required Inputs:** engine/backtester.py (DXY section), config/settings.yaml, any historical run data showing DXY filter acceptance/rejection rates
- **Dependencies:** None
- **Parallel with:** ACT-004, ACT-005
- **Effort:** S (~1 day) — Audit, documentation update, changelog entry
- **Risks and Mitigations:**
  - Risk: DXY symbol (DX-Y.NYB) delists or changes ticker
  - Mitigation: Document the risk; provide config option to disable DXY filter; recommend institutional data source
  - Risk: Users don't understand why some trades are filtered
  - Mitigation: Add DXY filter result to execution_log.json so users can see why trades were rejected
- **Quality Gate:** DXY symbol dependency documented in README with risk assessment; execution_log includes DXY filter field
- **Rollback Note:** Revert README changes; remove DXY filter from execution_log if added
- **Acceptance Criteria:**
  - [ ] README.md contains a section explaining the DXY external bias filter
  - [ ] Section states the Yahoo Finance symbol used (DX-Y.NYB)
  - [ ] Section explains which symbols are affected (EURUSD, GBPUSD pairs)
  - [ ] Section documents fallback behavior when DXY data is unavailable
  - [ ] config/settings.yaml comment clarifies that DX-Y.NYB is a Yahoo Finance dependency

---

## 5. Later Roadmap

| ID | Title | Rationale for Deferral | Prerequisite Actions | Effort |
|---|---|---|---|---|
| ACT-007 | Refactor signals.py into mode classes | XL refactoring should wait until test coverage (ACT-004) is in place; current complexity is manageable | ACT-004 (tests must pass first) | L |
| ACT-008 | Plan institutional data source upgrade (Polygon.io) | Requires ACT-006 documentation first; significant cost/contract implications; not urgent for strategy development | ACT-006 (DXY dependency documented) | XL |

---

## 6. Risk and Control Plan

### Risks Introduced by This Plan

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tests written for current implementation lock in current behavior, blocking legitimate refactoring | Medium | Medium | ACT-001 tests should test behavior, not implementation; review test design with Technical Lead |
| Retry logic adds latency to batch runs | Low | Low | 3 retries with exponential backoff is reasonable; monitor actual batch run times |
| Parameter validation breaks existing configs using edge values | Low | Medium | Warn (don't error) for borderline values; provide --force override |
| signals.py refactor introduces new bugs | Medium | High | ACT-007 must wait for ACT-004 (test suite); all existing tests must pass after refactor |

### Quality Gates for High-Risk Changes
- ACT-001, ACT-004: All pytest tests must pass; no regressions in manual dashboard runs
- ACT-003: Integration test with existing valid configs must succeed; invalid configs must produce clear errors
- ACT-005: Retry behavior tested with simulated failures; successful fetches must not be affected
- ACT-007: Full test suite passes; equity curve and metrics match pre-refactor runs within tolerance

---

## 7. Success Metrics

### Leading Indicators (Visible Within 1-2 Weeks)
| Metric | Current State | Target | Measurement |
|---|---|---|---|
| Test coverage of signals.py | 0% | ≥70% | pytest --cov with coverage report |
| Parameter validation failures logged | 0 (no validation) | Any attempt with invalid config produces error/warning | Log grep for "ConfigValidationError" |
| Retry attempts logged | 0 | Any yfinance failure triggers retry | Log grep for "Retrying fetch" |

### Lagging Indicators (Measurable After 1-2 Sprints)
| Metric | Current State | Target | Measurement |
|---|---|---|---|
| Test coverage of backtester core (Backtester, CircuitBreaker, PositionSizer) | 0% | ≥80% | pytest --cov on tests/ directory |
| README data limitations section | Missing | Present with accurate limits | Manual check |
| DXY filter documented | No | Yes | Manual check |

### Measurement Approach
- Run `pytest tests/ --cov=engine,risk --cov-report=term-missing` after ACT-001 and ACT-004
- Manual log review after first production batch run following ACT-003 and ACT-005
- PR review checklist includes README updates before merge

---

## 8. Open Unknowns

### Action Candidates Dropped (No Acceptance Criterion)
- **Institutional data source evaluation** — Cannot define action without first understanding budget, data quality requirements, and team capacity. Dropped from backlog; revisit after ACT-006 (DXY documentation) clarifies the scope of the yfinance dependency.

### Findings Requiring Clarification
- **Real-world DXY filter effectiveness** — Would require analyzing historical execution_log.json data to determine what percentage of potential trades were filtered by DXY bias. Cannot assess without access to run data. Recommend: run `jq '.[] | select(.dxy_filter_confirmed == false)' execution_log.json` on recent runs.
- **signals.py refactor scope** — Cannot finalize effort estimate (L vs XL) without first analyzing the full extent of cross-mode shared state. Recommend: Technical Lead does a 2-hour spike before committing to ACT-007.

---

*Artifact generated by Project Action Planner skill (Delivery mode)*
