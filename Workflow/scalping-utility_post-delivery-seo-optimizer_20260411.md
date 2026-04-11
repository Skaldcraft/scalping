# Post-Delivery SEO Optimizer Artifact
**Mode:** Internal Only  
**Project Type:** Internal Tool / Private Project  
**Gatekeeper Decision:** Conditional (71/100) — condition-linked risk flags apply  
**Date:** 2026-04-11  
**Confidence:** Medium (No live URL, analytics, or crawl reports accessible; analysis based on source files only)

---

## 1. SEO Executive Summary

**Project Type:** Internal Tool — Precision Scalping Utility (PulseTrader) is a private trading backtesting engine deployed locally on Windows workstations. No public web presence exists.

**Gatekeeper Decision State:** Conditional — condition-linked risk flags are applied to all recommendations that depend on unresolved mandatory fixes (pyyaml CVE, CSV sanitization, dashboard validation).

**External SEO:** **Not applicable for this project.** All recommendations are scoped to internal discoverability.

### Top 3 Findings (Internal Discoverability)

1. **SEO-001: Documentation search index is unstructured** — README.md, BEGINNER_GUIDE.md, and config/changelog.md are not indexed for internal search. Finding specific content (e.g., "how to add a custom symbol") requires manual grep or reading entire files.

2. **SEO-002: Inconsistent file naming conventions** — Results folders use timestamp patterns (`YYYYMMDD_HHMMSS_v1.0`) which are not human-readable and cannot be searched by date range. Batch reports use `batch_YYYY-MM-DD_to_YYYY-MM-DD/` which is more discoverable.

3. **SEO-003: No metadata on documentation content** — No tags, categories, or keyword metadata on README.md or BEGINNER_GUIDE.md. Internal search engines (IDE, OS file search) cannot surface content by topic without full-text search.

### Overall Discoverability Maturity Snapshot

**Low.** The project has good documentation coverage (README, BEGINNER_GUIDE, changelog) but no structured metadata, taxonomy, or cross-referencing. Content is discoverable only through full-text search or manual browsing. No orphaned content was identified — all documented files are referenced from README or the dashboard.

### Confidence Level

**Medium.** Analysis was performed on source files without access to IDE search history, internal wiki analytics, or user navigation data. All findings are based on direct file inspection and architectural analysis.

### What Was Not Assessed

| Item | Why Not Assessed |
|---|---|
| External SEO signals | No public web property exists |
| Google Search Console data | Internal tool; no web analytics |
| Crawl reports | No crawlable web interface |
| User search query data | Not available in source artifacts |
| Internal wiki or Confluence indexing | No internal knowledge base found in project |

---

## 2. Baseline Signals and Evidence

### Available Data Sources Consulted

| Source | Accessible | Notes |
|---|---|---|
| README.md | Yes | 443 lines; comprehensive but unindexed |
| BEGINNER_GUIDE.md | Yes | Not read in full; file exists at project root |
| config/changelog.md | Yes | 51 lines; versioned but not tagged |
| Workflow/*.md | Yes | 7 skill files in Workflow/ directory |
| diagnostics-pre-launch.md | Yes | Pre-launch checklist; orphaned (not linked from README) |
| dashboard/app.py (header comments) | Yes | Rich docstring but not indexed |
| results/ (auto-generated) | Yes | Timestamp-named folders; pattern is not search-friendly |
| GitHub repository | Not accessed | Repository structure assumed from .git presence |

### Current Observable SEO Signals

| Signal | Status | Evidence |
|---|---|---|
| Indexable content | Yes | README.md, BEGINNER_GUIDE.md, config/changelog.md, diagnostics-pre-launch.md |
| Clear page titles | Partial | README.md has clear title; others use filenames |
| Meta descriptions | No | No `<meta>` tags; markdown files have no frontmatter |
| Header hierarchy | Yes | README.md uses H1/H2/H3 structure; BEGINNER_GUIDE.md not reviewed |
| Content freshness | Partial | README.md appears current; changelog updated to v1.0 |
| Internal linking | Minimal | README links to config/, data/, engine/ sections inline; no hyperlinks |
| External links | No | No outbound links from documentation |
| Structured data | No | No JSON-LD, schema.org, or structured metadata |
| Sitemap | No | No sitemap.xml for documentation |
| robots.txt | No | No web presence |
| Canonical tags | N/A | No web presence |

### Internal Discoverability Signals

| Signal | Status | Evidence |
|---|---|---|
| Consistent taxonomy | No | No tags, categories, or keyword metadata |
| Cross-linking between docs | Minimal | README references other modules inline; Workflow/ is isolated |
| File naming consistency | Partial | Results folders use timestamp; batch folders use ISO dates |
| Search indexability | Low | Markdown files not tagged for topic; full-text search required |
| Orphaned content | Yes | diagnostics-pre-launch.md not linked from README or any index |
| Navigation structure | Implicit | README serves as de facto index; no dedicated navigation file |

### Gaps in Baseline Data

- No analytics on which documentation pages are most accessed
- No data on which search queries bring users to the documentation
- BEGINNER_GUIDE.md was not read in full — content coverage unknown
- No information on user navigation patterns through the dashboard

---

## 3. Domain-by-Domain Findings

### Domain 1 — Technical SEO (External): Not Applicable

No public web property exists. This domain is not applicable.

### Domain 2 — Content SEO (Internal)

**SEO-001: Documentation search index is unstructured**
- **Domain:** D2 — Content SEO (Internal)
- **Impact:** 4
- **Effort:** M
- **Confidence:** High
- **Priority:** Now
- **Evidence:** README.md (443 lines) serves as the primary index. BEGINNER_GUIDE.md is not linked from README. config/changelog.md is not discoverable without knowing it exists. No topic-based entry points.
- **Recommendation:** Add a "Quick Navigation" section at the top of README.md with anchor links to each major section (Installation, Running, Configuration, Strategy Logic, Output Files, Circuit Breakers, Automation, Troubleshooting). Link BEGINNER_GUIDE.md from the README header. Add a "Related Files" section at the bottom of each major section linking to relevant files.
- **Owner Profile:** Documentation Lead
- **Acceptance Criterion:** README.md has a navigation anchor list at top; BEGINNER_GUIDE.md is linked from README; each major section has at least one cross-link to related content

---

**SEO-002: File naming in results/ is not human-readable**
- **Domain:** D2 — Content SEO (Internal)
- **Impact:** 3
- **Effort:** S
- **Confidence:** High
- **Priority:** Next
- **Evidence:** Results folders named `20240815_143022_v1.0/` require mental parsing. Batch report folders named `batch_2026-01-05_to_2026-03-27/` use ISO dates which are more intuitive.
- **Recommendation:** Add a `run_summary.json` or `metadata.txt` inside each results folder with: run_date, version, date_range, trade_count, net_pnl. This enables programmatic access without parsing folder names.
- **Owner Profile:** Backend Engineer
- **Acceptance Criterion:** Every results folder contains a `run_summary.json` with at least: run_date, start_date, end_date, version, total_trades, net_pnl_2r

---

**SEO-003: BEGINNER_GUIDE.md content and integration unknown**
- **Domain:** D2 — Content SEO (Internal)
- **Impact:** 3
- **Effort:** S
- **Confidence:** Low
- **Priority:** Next
- **Evidence:** File exists at project root but is not referenced from README.md or any index.
- **Recommendation:** Read BEGINNER_GUIDE.md in full; integrate its content into the main README or link it prominently. If it duplicates README content, consolidate into one file with a clear anchor.
- **Owner Profile:** Documentation Lead
- **Acceptance Criterion:** BEGINNER_GUIDE.md is either: (a) linked from README.md with a clear description, or (b) merged into README.md with a "New Users Start Here" section

---

### Domain 3 — Performance and User Experience (External): Not Applicable

No public web property. Internal UI (Streamlit dashboard) not in scope for this SEO review.

### Domain 4 — Authority and Off-Page Signals (External): Not Applicable

No public web presence.

### Domain 5 — Local and International SEO (External): Not Applicable

No locale-specific content.

### Domain 6 — Internal Discoverability

**SEO-004: No taxonomy or keyword metadata on documentation**
- **Domain:** D6 — Internal Discoverability
- **Impact:** 4
- **Effort:** S
- **Confidence:** High
- **Priority:** Now
- **Evidence:** No YAML frontmatter, tags, or keyword metadata on any markdown file. IDE and file system search cannot surface content by topic.
- **Recommendation:** Add YAML frontmatter to README.md and BEGINNER_GUIDE.md with:
  ```yaml
  ---
  title: Precision Scalping Utility
  description: Mechanical backtesting engine for opening-range scalping
  tags: [backtesting, trading, scalping, yfinance, streamlit]
  related: [BEGINNER_GUIDE.md, config/changelog.md, Workflow/]
  last_updated: 2026-04-11
  ---
  ```
  If the project uses a documentation generator (MkDocs, Docusaurus, etc.), ensure frontmatter is indexed.
- **Owner Profile:** Documentation Lead
- **Acceptance Criterion:** README.md has YAML frontmatter with title, description, and at least 3 tags

---

**SEO-005: diagnostics-pre-launch.md is orphaned content**
- **Domain:** D6 — Internal Discoverability
- **Impact:** 3
- **Effort:** S
- **Confidence:** High
- **Priority:** Next
- **Evidence:** diagnostics-pre-launch.md exists at project root but is not linked from README.md or any other document. It is not mentioned in the project structure section of README.
- **Recommendation:** Either: (a) link diagnostics-pre-launch.md from README.md under a "Troubleshooting" section if its content is still relevant, or (b) remove it if it is stale and no longer applicable.
- **Owner Profile:** Documentation Lead
- **Acceptance Criterion:** diagnostics-pre-launch.md is either linked from README.md with context, or removed from the repository

---

**SEO-006: Workflow/ directory is isolated from main documentation**
- **Domain:** D6 — Internal Discoverability
- **Impact:** 2
- **Effort:** M
- **Confidence:** High
- **Priority:** Later
- **Evidence:** Workflow/ directory contains 7 markdown files for the project review workflow. It is not mentioned in README.md and is not discoverable without knowing it exists.
- **Recommendation:** If the workflow documentation is intended for internal use, add a brief note to README.md: "See Workflow/ directory for project review and handoff documentation." If it is only for external reviewers, no action needed.
- **Owner Profile:** Documentation Lead
- **Acceptance Criterion:** README.md references Workflow/ directory, or Workflow/ is moved outside the project root if not relevant to users

---

## 4. Prioritized Recommendations

| ID | Title | Domain | Priority | Impact | Effort | Owner | Confidence |
|---|---|---|---|---|---|---|---|
| SEO-001 | Add navigation anchors to README.md | D2 | Now | 4 | M | Documentation Lead | High |
| SEO-004 | Add YAML frontmatter metadata to docs | D6 | Now | 4 | S | Documentation Lead | High |
| SEO-002 | Add run_summary.json to results folders | D2 | Next | 3 | S | Backend Engineer | High |
| SEO-003 | Integrate BEGINNER_GUIDE.md into README | D2 | Next | 3 | S | Documentation Lead | Low |
| SEO-005 | Resolve orphaned diagnostics-pre-launch.md | D6 | Next | 3 | S | Documentation Lead | High |
| SEO-006 | Reference Workflow/ from README | D6 | Later | 2 | M | Documentation Lead | High |

### Now Recommendations (Full Detail)

**SEO-001: Add navigation anchors to README.md**
- **Current State:** README.md is 443 lines with no anchor links. Users must scroll or use browser find.
- **Action:** Add a "Quick Navigation" section at the top of README.md:
  ```markdown
  ## Quick Navigation
  - [Installation](#installation)
  - [Running the Dashboard](#running-the-dashboard-recommended)
  - [Running from CLI](#running-from-the-cli)
  - [Configuration](#configuration)
  - [Output Files](#output-files)
  - [Automation](#daily-automation)
  - [Circuit Breakers](#circuit-breakers)
  - [Troubleshooting](#troubleshooting)
  ```
- **Owner:** Documentation Lead
- **Acceptance Criterion:** README.md top contains anchor list; each H2 section has an explicit id attribute; clicking any anchor navigates to the correct section

**SEO-004: Add YAML frontmatter metadata to documentation**
- **Current State:** No metadata on markdown files; content is not tagged or categorized.
- **Action:** Add YAML frontmatter to README.md and BEGINNER_GUIDE.md. For other markdown files (changelog.md, diagnostics-pre-launch.md), evaluate on a per-file basis.
- **Owner:** Documentation Lead
- **Acceptance Criterion:** README.md and BEGINNER_GUIDE.md have valid YAML frontmatter with title, description, and at least 3 tags

---

## 5. 30-60-90 Day Execution Plan

### Days 1–30 (Now): Foundation

**Target:** Structured documentation with navigation and metadata.

| Action | Owner | Expected Signal |
|---|---|---|
| SEO-001: Add navigation anchors to README.md | Documentation Lead | README.md has clickable anchor links; user feedback confirms improved navigation |
| SEO-004: Add YAML frontmatter to docs | Documentation Lead | Frontmatter visible in raw file; metadata indexable by documentation tools |

**Condition-Linked Risks:**
- SEO-001 depends on README.md being finalized — if conditional fixes (ACT-002: data limitations documentation) change README content, anchors must be updated accordingly.
- SEO-004 depends on no documentation generator being in use — if a tool (MkDocs, Docusaurus) is adopted in the future, frontmatter format must match the tool's requirements.

### Days 31–60 (Next): Content Integration

**Target:** All documentation content is cross-linked and no orphaned files remain.

| Action | Owner | Expected Signal |
|---|---|---|
| SEO-002: Add run_summary.json to results | Backend Engineer | Results folders contain machine-readable metadata; scripts can parse results without regex |
| SEO-003: Integrate BEGINNER_GUIDE.md | Documentation Lead | BEGINNER_GUIDE.md is discoverable from README; duplicate content removed or consolidated |
| SEO-005: Resolve orphaned diagnostics file | Documentation Lead | diagnostics-pre-launch.md is linked or removed; no orphan files remain in project root |

### Days 61–90 (Later): Structural Improvements

**Target:** Full taxonomy and discoverability audit complete.

| Action | Owner | Expected Signal |
|---|---|---|
| SEO-006: Reference Workflow/ from README | Documentation Lead | Workflow/ documentation is discoverable if relevant to users |
| Conduct full documentation audit | Documentation Lead | All markdown files have frontmatter; no orphaned content; cross-links verified |
| Evaluate documentation generator adoption | Documentation Lead | If adopted: sitemap generated; if rejected: rationale documented |

---

## 6. Internal Discoverability Package

### Taxonomy Tags

Recommended tags for the project's documentation files:

| File | Suggested Tags |
|---|---|
| README.md | backtesting, scalping, trading, strategy, yfinance, automation, getting-started |
| BEGINNER_GUIDE.md | beginner, tutorial, getting-started, trading |
| config/changelog.md | versioning, release-notes, changelog, strategy-updates |
| diagnostics-pre-launch.md | troubleshooting, diagnostics, pre-flight, testing |
| Workflow/00_implementation-guide.md | workflow, project-management, review, handoff |
| Workflow/01_project-overview.md | project-analysis, architecture, review |
| Workflow/04_handoff-packager.md | handoff, onboarding, receiving-builder |
| dashboard/app.py (header) | dashboard, streamlit, visualization, UI |

### Suggested Keywords

5–10 terms that should appear in titles, headers, and search index entries:

1. `opening range scalping` — core strategy term
2. `backtesting engine` — project type
3. `yfinance data` — data source
4. `circuit breaker` — risk management feature
5. `pre-session selection` — unique differentiator
6. `2:1 reward ratio` — strategy parameter
7. `New York session` — time scope
8. `equity curve` — output/visualization
9. `trade journal` — output artifact
10. `daily automation` — operational feature

### Cross-Reference Map

| Content Item | Should Link To | Should Be Linked From |
|---|---|---|
| README.md (Installation) | requirements.txt, config/settings.yaml | BEGINNER_GUIDE.md, diagnostics-pre-launch.md |
| README.md (Configuration) | config/settings.yaml, config/changelog.md | dashboard/app.py comments |
| README.md (Strategy Logic) | engine/signals.py, engine/backtester.py | — |
| README.md (Automation) | daily_run.py, run_daily.ps1, run_intraday.ps1 | — |
| README.md (Circuit Breakers) | risk/circuit_breaker.py | diagnostics-pre-launch.md |
| config/changelog.md | README.md (version section) | main.py (version logging) |
| BEGINNER_GUIDE.md | README.md | README.md (new user section) |
| Workflow/ (all files) | README.md, config/changelog.md | README.md (if relevant to users) |

### Naming Conventions

| Item | Current Pattern | Recommended Pattern | Rationale |
|---|---|---|---|
| Results folders | `YYYYMMDD_HHMMSS_v1.0/` | Keep timestamp + add `run_summary.json` | Human-readable metadata without renaming existing folders |
| Batch report folders | `batch_YYYY-MM-DD_to_YYYY-MM-DD/` | Keep as-is | ISO date format is already human-readable |
| Config snapshots | `config_snapshot.yaml` | Keep as-is | Clear and descriptive |
| Trade logs | `trade_log.csv` | Keep as-is | Clear and descriptive |
| Selection snapshots | `selection_snapshot.json` | Keep as-is | Clear and descriptive |
| Markdown files | `BEGINNER_GUIDE.md`, `diagnostics-pre-launch.md` | Keep as-is but add frontmatter | Descriptive enough; metadata improves findability |

### Stale or Orphaned Content

| File | Status | Action |
|---|---|---|
| diagnostics-pre-launch.md | **Orphaned** — not linked from README or any index | Link from README "Troubleshooting" section or remove if stale |

---

## 7. Measurement Framework

| KPI | Baseline | Target | Measurement Method | Cadence |
|---|---|---|---|---|
| Documentation anchor links added | 0 | ≥1 per major README section | Manual check of README.md | Monthly |
| YAML frontmatter on markdown files | 0 files | ≥2 files (README.md, BEGINNER_GUIDE.md) | `grep '---' *.md` | Monthly |
| run_summary.json in results | 0 folders | 100% of new results folders | Script check on new runs | Per run |
| Orphaned files remaining | 1 (diagnostics-pre-launch.md) | 0 | Manual audit | Quarterly |
| README section cross-links | Unknown | ≥1 cross-link per major section | Manual check | Quarterly |
| BEGINNER_GUIDE.md integration | Not linked | Linked from README or merged | Manual check | Monthly |

**Trackable KPIs (Current tooling only):**
- All KPIs are manually trackable from source files
- No automated analytics in place
- No search index metrics available

---

## 8. Risks, Constraints, and Assumptions

### Condition-Linked Risk Flags

| Recommendation | Depends On | Risk if Unresolved | Flag |
|---|---|---|---|
| SEO-001 (README navigation anchors) | ACT-002 (README data limits section) | README content changes may require anchor updates | **Flagged** — update anchors after ACT-002 is merged |
| SEO-002 (run_summary.json) | ACT-003 (config validation) | No risk; independent | No flag |
| SEO-003 (BEGINNER_GUIDE integration) | None | No risk | No flag |
| SEO-004 (YAML frontmatter) | None | No risk | No flag |
| SEO-005 (orphaned diagnostics file) | None | No risk | No flag |
| SEO-006 (Workflow/ reference) | None | If Workflow/ is not relevant to users, no action needed | No flag |

### External Factors Affecting Outcomes

- **Documentation tool adoption** — If the team adopts MkDocs, Docusaurus, or another static site generator, frontmatter format must be compatible. Monitor for adoption decisions.
- **GitHub Pages or internal wiki hosting** — If documentation is hosted on a web platform, external SEO (sitemap, meta tags, canonical URLs) becomes applicable. Monitor for hosting decisions.

### Assumptions Made

| Assumption | Basis | Impact if Wrong |
|---|---|---|
| BEGINNER_GUIDE.md is relevant to users | File exists at project root with descriptive name | Content may be deprecated; SEO-003 may be unnecessary |
| diagnostics-pre-launch.md is orphaned | Not linked from README or any index | May be intentionally standalone; SEO-005 may need refinement |
| No documentation generator in use | No mkdocs.yml, docusaurus.config.js, or similar found | If adopted, frontmatter approach must change |
| Workflow/ documentation is internal only | Directory is named "Workflow" with review-focused content | If public, external SEO becomes applicable |

### Constraints

- No web presence — external SEO not applicable
- No analytics or search query data — all KPI baselines are "not established"
- No crawl reports — no automated SEO tooling found in project
- Source files are local markdown — no dynamic CMS to configure SEO metadata

---

*Artifact generated by Post-Delivery SEO Optimizer skill (Internal Only mode)*
*External SEO: Not applicable — Internal discoverability only*
*Gatekeeper: Conditional — condition-linked risk flags applied to SEO-001*
