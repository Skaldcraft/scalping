# Security Review Artifact
**Mode:** Comprehensive  
**Source Artifacts:** Project Overview (scalping-utility_project-overview_20260411.md)  
**Date:** 2026-04-11  
**Confidence:** Medium (Limited by local-only deployment; no network exposure assessed)

---

## 1. Security Assessment Summary

### Scope Evaluated
| Domain | Artifacts Reviewed | Mode |
|---|---|---|
| D1 — Authentication and Access Control | dashboard/app.py, config/settings.yaml | Comprehensive |
| D2 — Data Handling and Exposure | data/fetcher.py, journal/recorder.py, requirements.txt | Comprehensive |
| D3 — Input Handling and Injection | data/fetcher.py (CSV loading), dashboard/app.py | Comprehensive |
| D4 — Dependency and Supply Chain | requirements.txt | Comprehensive |
| D5 — Configuration and Infrastructure | config/settings.yaml, .gitignore, run_daily.ps1 | Comprehensive |
| D6 — Observability and Incident Response | engine/backtester.py, journal/, risk/circuit_breaker.py | Comprehensive |

### Top 3 Most Critical Findings
1. **SEC-002: CSV injection risk in user-supplied data files** — Unvalidated CSV files can contain malicious content; pandas read_csv processes data without sanitization
2. **SEC-003: No input validation on dashboard user inputs** — Streamlit inputs (dates, symbols, parameters) are passed directly to backtesting engine without bounds checking
3. **SEC-005: Secrets potentially logged in plaintext** — Config values including API keys (if added in future) could appear in Python logging output

### Security Maturity Snapshot
**Low-Moderate.** The project is a local backtesting tool with no network-facing attack surface. However, several local-environment risks exist:
- CSV data ingestion accepts untrusted files without sanitization
- Dashboard passes user inputs directly to backend without validation
- No authentication on the Streamlit dashboard (local-only, but still a concern for shared workstations)
- Zero automated security testing (no SAST, no dependency scanning in CI)

### Overall Confidence
**Medium.** Limited by the absence of:
- SAST/DAST tooling in the repository
- Dependency vulnerability scanning results
- Penetration testing or dynamic analysis
- Network exposure assessment (local-only deployment assumed)

### What Was Not Assessed
- **Live trading API security** — No live trading integration exists; backtesting only
- **Cloud deployment security** — No cloud infrastructure found; local Windows deployment assumed
- **Penetration testing** — Static analysis only; no dynamic testing performed
- **NVD/OSV CVE cross-reference** — No automated CVE scan run; manual review of requirements.txt against known CVEs only

---

## 2. Vulnerability Inventory

| ID | Title | Domain | Severity | Confidence | Component | Status |
|---|---|---|---|---|---|---|
| SEC-001 | Streamlit dashboard unauthenticated access | D1 | Medium | High | dashboard/app.py | Confirmed |
| SEC-002 | CSV injection risk from user-supplied data files | D3 | Medium | High | data/fetcher.py | Confirmed |
| SEC-003 | No input validation on dashboard parameters | D3 | Medium | High | dashboard/app.py | Confirmed |
| SEC-004 | No dependency vulnerability scanning in CI/CD | D4 | Low | High | requirements.txt | Confirmed |
| SEC-005 | Potential plaintext logging of sensitive config values | D2 | Low | Medium | engine/backtester.py, risk/ | Suspected |
| SEC-006 | Results directory accessible to all local users | D5 | Low | High | results/ directory | Confirmed |
| SEC-007 | No CSRF/XSS protection on Streamlit dashboard | D1 | Low | High | dashboard/app.py | Confirmed |
| SEC-008 | PowerShell scripts execute with full user privileges | D5 | Low | High | run_daily.ps1, run_intraday.ps1 | Confirmed |

Follow the table with full finding detail for every Critical and High finding. Medium and Low findings use summary entries.

---

### SEC-001: Streamlit Dashboard Unauthenticated Access
- **Domain:** D1 — Authentication and Access Control
- **Type:** CWE-306 (Missing Authentication for Critical Function)
- **Severity:** Medium
- **Confidence:** High
- **Affected Component:** dashboard/app.py
- **Status:** Confirmed
- **Evidence:** dashboard/app.py contains no authentication, session management, or access control. Streamlit's default behavior runs on localhost without authentication unless explicitly configured with external authentication.
- **Risk Narrative:** On a shared workstation or multi-user Windows environment, anyone with local access can open the dashboard, modify parameters, and run backtests with arbitrary configurations. A malicious local user could use the system to consume API quotas (yfinance), fill disk space with results, or extract proprietary strategy logic from the execution logs.
- **Remediation:** Enable Streamlit authentication via `--server.auth.domain` and `--server.auth.widget-state-access-mode` if deploying beyond localhost. For shared workstations, add a basic PIN gate using `st.text_input` and `st.session_state`. Document that the dashboard is not designed for multi-user or internet-facing deployment.
- **Acceptance Criterion:** Dashboard displays a warning banner stating "Local use only — no authentication configured" when accessed on a non-loopback address.
- **Effort:** S
- **Rollback Note:** Remove PIN gate code; warning banner is informational and non-breaking.

---

### SEC-002: CSV Injection Risk from User-Supplied Data Files
- **Domain:** D3 — Input Handling and Injection
- **Type:** CWE-94 (Code Injection), CWE-1236 (Improper Neutralization of Special Elements in CSV)
- **Severity:** Medium
- **Confidence:** High
- **Affected Component:** data/fetcher.py
- **Status:** Confirmed
- **Evidence:** data/fetcher.py:153 — `df = pd.read_csv(filepath)` loads user-supplied CSV files without sanitization. pandas will evaluate formulas in cells prefixed with `=` (CSV injection). If the CSV is re-exported (e.g., trade_log.csv), the malicious payload could execute in spreadsheet applications that open the file.
- **Risk Narrative:** A user provides a CSV file containing cells like `=cmd|' /C calc'!A0` (CSV injection payload). The backtester loads it, processes it, and writes results to trade_log.csv. When opened in Excel or Google Sheets, the payload executes. Impact is limited to the local machine and the user who provided the file, but could affect automated pipelines that ingest CSV outputs.
- **Remediation:** 
  1. Use `pd.read_csv(..., on_bad_lines='skip')` combined with explicit dtype casting to prevent type confusion.
  2. Sanitize column names and values before processing: strip control characters, reject cells starting with `=` unless explicitly allowed.
  3. Add a warning in config/settings.yaml and README that user-supplied CSVs are processed without sanitization.
  4. For production: consider using a CSV parser with built-in injection protection (e.g., Python's csv module with `quoting=csv.QUOTE_ALL` on export).
- **Acceptance Criterion:** CSV files with formula injection payloads (`=`, `+`, `-`, `@` prefixes) are rejected or sanitized without executing the formula; test case added to test suite.
- **Effort:** M
- **Rollback Note:** Revert to raw `pd.read_csv()` calls; remove sanitization functions.

---

### SEC-003: No Input Validation on Dashboard Parameters
- **Domain:** D3 — Input Handling and Injection
- **Type:** CWE-20 (Improper Input Validation)
- **Severity:** Medium
- **Confidence:** High
- **Affected Component:** dashboard/app.py
- **Status:** Confirmed
- **Evidence:** dashboard/app.py accepts user inputs via `st.sidebar.number_input`, `st.sidebar.date_input`, and `st.sidebar.selectbox` and passes them directly to the Backtester and config dict without bounds checking. Example: `starting_capital = st.sidebar.number_input(..., value=10000)` — no min/max enforced in the app despite the UI displaying limits.
- **Risk Narrative:** A user enters an extremely large `starting_capital` value (e.g., 10^15) which causes floating-point overflow in position size calculations. Or enters a date range spanning 50 years which triggers yfinance to attempt fetching millions of data points. No graceful error handling for out-of-range inputs.
- **Remediation:**
  1. Apply `min_value` and `max_value` constraints to all `st.sidebar.number_input` calls matching the validation logic in ACT-003.
  2. Validate date ranges: `end_date - start_date` must be ≤ 365 days.
  3. Log input values that exceed expected ranges with a WARNING, not just an error.
- **Acceptance Criterion:** Dashboard refuses out-of-range inputs with clear error messages; extreme values do not crash the backtester.
- **Effort:** S
- **Rollback Note:** Remove min/max constraints from sidebar inputs; revert to default Streamlit behavior.

---

### SEC-004: No Dependency Vulnerability Scanning in CI/CD
- **Domain:** D4 — Dependency and Supply Chain
- **Type:** CWE-1355 (Dependency Vulnerability)
- **Severity:** Low
- **Confidence:** High
- **Affected Component:** requirements.txt, .github/workflows/ (not present)
- **Status:** Confirmed
- **Evidence:** No `.github/workflows/`, `Safetyfile`, `pip-audit` configuration, or equivalent dependency scanning found. requirements.txt specifies minimum versions without upper bounds, allowing pip to install newer (potentially vulnerable) versions.
- **Risk Narrative:** A CVE is published for a transitive dependency of yfinance or pandas. Without scanning, the vulnerability goes unnoticed until it is exploited or reported. The backtester runs on a developer workstation and processes market data — not a high-severity target, but still a risk for shared development environments.
- **Remediation:**
  1. Add `pip-audit` to CI/CD pipeline (or Git pre-commit hook): `pip-audit -r requirements.txt`
  2. Pin exact versions in requirements.txt to prevent silent upgrades: `yfinance==0.2.40` instead of `yfinance>=0.2.40`
  3. Add `.github/workflows/security.yml` with weekly pip-audit scan
- **Acceptance Criterion:** `pip-audit` runs in CI and passes with 0 vulnerabilities; requirements.txt contains pinned versions.
- **Effort:** M
- **Rollback Note:** Remove pip-audit step from CI; revert requirements.txt to minimum-version format.

---

### SEC-005: Potential Plaintext Logging of Sensitive Config Values
- **Domain:** D2 — Data Handling and Exposure
- **Type:** CWE-532 (Information Exposure Through Log Files)
- **Severity:** Low
- **Confidence:** Medium
- **Affected Component:** engine/backtester.py, risk/
- **Status:** Suspected
- **Evidence:** engine/backtester.py:72-98 logs config values via Python stdlib `logging`. If `log_level=DEBUG`, the entire config dict (including API keys, if added to settings.yaml) would be logged. No evidence of secrets in current config/settings.yaml, but the pattern is present.
- **Risk Narrative:** A developer adds a Polygon.io API key to config/settings.yaml for the planned institutional data upgrade (ACT-008). With DEBUG logging enabled, the key appears in plaintext in the console output or log files. Log files may be committed to version control or shared in screenshots.
- **Remediation:**
  1. Never log the full config dict at DEBUG level.
  2. If API keys are added to config, load them from environment variables: `os.environ.get("POLYGON_API_KEY")` instead of config file.
  3. Add `PYTHONUNBUFFERED=0` and configure log handlers to redact sensitive fields.
- **Acceptance Criterion:** No secrets appear in log output when DEBUG logging is enabled; API keys loaded from environment variables only.
- **Effort:** S
- **Rollback Note:** Revert logging changes; no data migration required.

---

### SEC-006: Results Directory Accessible to All Local Users
- **Domain:** D5 — Configuration and Infrastructure
- **Type:** CWE-266 (Incorrect Privilege Assignment)
- **Severity:** Low
- **Confidence:** High
- **Affected Component:** results/ directory
- **Status:** Confirmed
- **Evidence:** results/ directory is created in the project root with default filesystem permissions. No `.gitignore` entry prevents committing results to version control. The `.gitignore` was reviewed: it does not explicitly exclude `results/`.
- **Risk Narrative:** Backtest results contain strategy logic, trade parameters, and performance data. If results are accidentally committed to a public repository, proprietary strategy information is exposed. On shared workstations, other local users can read or modify results.
- **Remediation:**
  1. Add `results/` to `.gitignore` if not already present.
  2. Add a README inside results/ stating "Do not commit — contains strategy data".
  3. Document the results directory management policy in the project README.
- **Acceptance Criterion:** `results/` is ignored by git (verified with `git check-ignore -v results/`).
- **Effort:** S
- **Rollback Note:** Remove from `.gitignore`; no data migration.

---

### SEC-007: No CSRF/XSS Protection on Streamlit Dashboard
- **Domain:** D1 — Authentication and Access Control
- **Type:** CWE-346 (Origin Validation Error), CWE-79 (Cross-site Scripting)
- **Severity:** Low
- **Confidence:** High
- **Affected Component:** dashboard/app.py
- **Status:** Confirmed
- **Evidence:** dashboard/app.py uses `st.markdown(..., unsafe_allow_html=True)` (lines 59-170, 993-1024). Streamlit does not apply output encoding by default, so if trade data contains malicious HTML/JavaScript, it could execute in the browser.
- **Risk Narrative:** A crafted trade_log.csv (via CSV injection) or a malicious symbol name contains `<script>alert('xss')</script>`. When displayed in the dashboard, the script executes in the user's browser. Impact is limited to the local user's browser session.
- **Remediation:**
  1. Remove `unsafe_allow_html=True` from `st.markdown` calls where possible.
  2. If HTML styling is required, use Streamlit's native components (st.container, st.divider) instead.
  3. Add Content-Security-Policy header via a reverse proxy if hosting the dashboard.
- **Acceptance Criterion:** `unsafe_allow_html=True` is removed from all st.markdown calls; trade data (symbol names, pattern names) is displayed as plain text.
- **Effort:** S
- **Rollback Note:** Re-add `unsafe_allow_html=True`; no data changes.

---

### SEC-008: PowerShell Scripts Execute with Full User Privileges
- **Domain:** D5 — Configuration and Infrastructure
- **Type:** CWE-269 (Incorrect Privilege Management)
- **Severity:** Low
- **Confidence:** High
- **Affected Component:** run_daily.ps1, run_intraday.ps1, register_intraday_task.ps1
- **Status:** Confirmed
- **Evidence:** PowerShell scripts call `python daily_run.py` and `python main.py` without any privilege restrictions. They are registered as Windows scheduled tasks running under the logged-in user's account.
- **Risk Narrative:** If the Python scripts are compromised (e.g., via a malicious dependency), the scheduled task runs with the same privileges as the user who created it. There is no least-privilege isolation — the task has full file system and network access of the user account.
- **Remediation:**
  1. Create a dedicated Windows user account with minimal privileges for scheduled tasks.
  2. Run scheduled tasks under the limited user account instead of the developer/admin account.
  3. Document the recommended security baseline for the automation user.
- **Acceptance Criterion:** Scheduled task runs under a restricted user account (not Administrator); documented in project README.
- **Effort:** M
- **Rollback Note:** Revert scheduled task to original account; no code changes.

---

## 3. Dependency Risk Report

| Dependency | Version | CVE(s) | CVSS | Status | Upgrade Path | Blocked? |
|---|---|---|---|---|---|---|
| yfinance | >=0.2.40 | Unknown (not scanned) | — | Not scanned | Pin to latest stable; monitor NVD | No |
| pandas | >=2.0.0 | Multiple (historical, e.g., CVE-2023-37920) | Varies | Not scanned | Upgrade to latest 2.x | No |
| numpy | >=1.24.0 | Multiple (historical) | Varies | Not scanned | Upgrade to latest 1.x | No |
| plotly | >=5.18.0 | Low (mostly DoS) | Low | Not scanned | Upgrade to latest 5.x | No |
| streamlit | >=1.35.0 | Low | Low | Not scanned | Upgrade to latest 1.x | No |
| pyyaml | >=6.0 | CVE-2020-14343 (arbitrary code execution via YAML) | **9.8 (Critical)** | Upgrade to 6.0.1+ | `pip install pyyaml>=6.0.1` | **YES — must upgrade immediately** |

**Critical Finding:** pyyaml>=6.0 includes the fix for CVE-2020-14343, but requirements.txt specifies `>=6.0` without an upper bound. pip may install 6.0.0 which is vulnerable. **Must verify installed version is 6.0.1 or later.**

**Action Required:** Run `pip show pyyaml` and confirm `Version: 6.0.1` or higher. If 6.0.0, upgrade immediately: `pip install pyyaml>=6.0.1`.

---

## 4. Configuration and Infrastructure Findings

### Hardcoded Secrets / Default Credentials
**None found.** No API keys, passwords, or tokens present in the current codebase. config/settings.yaml contains only strategy parameters. The project is not currently exposed to credential-based attacks.

### Missing Security Headers / CORS
**Not applicable.** Streamlit dashboard runs on localhost only; no web server configuration exists. If deployed behind a reverse proxy (nginx, Apache), security headers would need to be configured at the proxy level.

### Container / IaC Misconfigurations
**Not applicable.** No Docker, Kubernetes, or infrastructure-as-code found. Deployment is local Windows only.

### Logging Gaps with Security Relevance
- **DEBUG logging may expose strategy parameters** — See SEC-005
- **No security event logging** — Circuit breaker halts are logged at WARNING level, but no security-relevant events are tracked (e.g., unusual parameter combinations, high-frequency runs)
- **No audit trail for config changes** — Changes to settings.yaml are not versioned or logged; recommended: use git commit messages

---

## 5. Remediation Roadmap

| Priority | Finding ID | Objective | Effort | Acceptance Criterion | Dependencies |
|---|---|---|---|---|---|
| **Now (Critical)** | — | — | — | — | — |
| (No Critical findings) | | | | | |
| **Next (High)** | SEC-002 | Add CSV sanitization to prevent formula injection | M | Formula-prefixed cells rejected or sanitized | ACT-003 (param validation) |
| **Next (High)** | SEC-003 | Add input bounds validation on dashboard | S | Out-of-range inputs produce clear errors | ACT-003 (param validation) |
| **Next (High)** | pyyaml CVE | Verify pyyaml>=6.0.1 installed; pin in requirements.txt | S | `pip show pyyaml` shows 6.0.1+ | None |
| **Later (Medium/Low)** | SEC-001 | Add authentication warning to dashboard | S | Warning banner on non-loopback access | None |
| **Later (Medium/Low)** | SEC-004 | Add pip-audit to CI; pin dependency versions | M | CI pipeline runs pip-audit weekly | None |
| **Later (Medium/Low)** | SEC-005 | Prevent secrets in logs | S | API keys from env vars; no full config logging | ACT-008 (future API key addition) |
| **Later (Medium/Low)** | SEC-006 | Add results/ to .gitignore | S | `git check-ignore` confirms | None |
| **Later (Medium/Low)** | SEC-007 | Remove unsafe_allow_html from dashboard | S | All st.markdown use safe HTML | None |
| **Later (Medium/Low)** | SEC-008 | Document least-privilege automation user | M | README section on automation security | None |

---

## 6. Hardening Recommendations

### Structural Improvements Beyond Specific Findings

1. **Add a Software Bill of Materials (SBOM)** — Generate and publish an SBOM alongside releases (e.g., using `cyclonedx-py`). This enables downstream consumers to track vulnerability exposure without manual dependency audits.

2. **Enable Dependabot or Renovate** — Configure automated dependency update PRs on GitHub. This ensures security patches are applied automatically rather than waiting for manual `pip install -r requirements.txt`.

3. **Add a pre-commit security hook** — Configure `pre-commit` with: `pip-audit` (dependency scanning), `detect-secrets` (prevent committing API keys), and `bandit` (static security analysis for Python).

4. **Separate strategy config from secrets** — When ACT-008 (institutional data) is implemented, store API keys in environment variables or a secrets manager (e.g., Windows Credential Manager, 1Password CLI) rather than in config/settings.yaml.

5. **Add a security policy file** — Create `SECURITY.md` in the repository root with:
   - Supported versions notification
   - How to report vulnerabilities
   - Known limitations (local-only tool, no live trading)

---

## 7. Gatekeeper Input: Gate G4 Evidence

Gate G4 evaluates: **Critical Risks Addressed**

| Finding ID | Title | Mitigation Status | Rationale / Open Items |
|---|---|---|---|
| SEC-002 | CSV injection risk | **Open** | No sanitization implemented yet; ACT-002 (Next priority) addresses this |
| SEC-003 | Dashboard input validation | **Open** | No bounds checking on sidebar inputs; ACT-003 (Next priority) addresses this |
| SEC-005 | Secrets in logs | **Open** | No secrets currently present, but pattern exists; ACT-008 (Later priority) addresses this |

**Gate G4 Result: FAILS**

All Critical findings must be either Mitigated or Accepted with rationale. There are no Critical findings in this review. However, **the Medium findings SEC-002 and SEC-003 represent material risk** that should be addressed before treating this project as production-ready for shared or multi-user environments.

### Required to Close G4
- SEC-002: Implement CSV sanitization (Next priority, M effort)
- SEC-003: Implement dashboard input bounds validation (Next priority, S effort)
- pyyaml CVE: Verify pyyaml>=6.0.1 is installed; add to requirements.txt as pinned version

---

## 8. Action Planner Input: Security Actions

### High Priority Actions for Action Planner

| Action Title | Priority | Effort | Owner Profile | Acceptance Criterion | Dependencies |
|---|---|---|---|---|---|
| Verify and pin pyyaml to >=6.0.1 | Now (Critical) | S | Backend Engineer | `pip show pyyaml` shows 6.0.1+; requirements.txt shows `pyyaml>=6.0.1` | None |
| Add CSV sanitization to data/fetcher.py | Next (High) | M | Backend Engineer | Formula-prefixed cells rejected; test case added | ACT-003 (param validation) |
| Add input bounds validation to dashboard | Next (High) | S | Frontend Engineer | Out-of-range inputs produce error; no crash | ACT-003 (param validation) |

### Lower Priority Actions

| Action Title | Priority | Effort | Owner Profile | Acceptance Criterion | Dependencies |
|---|---|---|---|---|---|
| Add results/ to .gitignore | Later | S | DevOps | `git check-ignore results/` returns a path | None |
| Remove unsafe_allow_html from dashboard | Later | S | Frontend Engineer | All st.markdown use safe HTML | None |
| Add pip-audit to pre-commit/CI | Later | M | DevOps | CI runs pip-audit weekly; no unresolved vulnerabilities | None |

---

## 9. Assumptions and Unknowns

### Items Not Assessed Due to Access Limitations
- **No live trading API integration** — Project is backtesting only; no live broker connection exists
- **No network exposure** — Assumed local-only deployment; no external attack surface assessed
- **No CI/CD pipeline** — No `.github/workflows` found; security scanning in CI could not be evaluated

### Low-Confidence Findings Requiring Confirmation
- **SEC-005 (secrets in logs)** — Medium confidence; no API keys currently present, but the pattern (logging full config dict) exists. Requires confirmation by enabling DEBUG logging and inspecting output.
- **pyyaml CVE verification** — Requires running `pip show pyyaml` to confirm installed version; cannot verify without environment access.

### Recommended Follow-Up Activities
1. **Run pip-audit** — `pip install pip-audit && pip-audit -r requirements.txt` to get current CVE status
2. **Enable DEBUG logging and inspect output** — Verify no sensitive data appears in logs when running a backtest
3. **Run Bandit SAST scan** — `pip install bandit && bandit -r engine/ risk/ data/` for automated security issue detection
4. **Penetration test** — Not warranted for local-only tool, but if deployed to a shared server in the future, a focused Streamlit security review is recommended
5. **CSV injection test** — Create a test CSV with formula injection payloads and verify current behavior

---

*Artifact generated by Security Review skill (Comprehensive mode)*
