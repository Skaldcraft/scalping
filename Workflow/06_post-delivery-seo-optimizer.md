---
title: Post-Delivery SEO Optimizer
slug: post-delivery-seo-optimizer
summary: Analyze a delivered project's SEO and discoverability posture, produce prioritized recommendations for external search visibility and internal findability, and generate a measurement framework with a 30-60-90 day execution plan.
applyTo:
  - '**/*'
---

# Skill: Post-Delivery SEO Optimizer

## Purpose

Produce actionable, evidence-based SEO and discoverability recommendations after a project has been reviewed, packaged, and handed off. This skill runs after the Handoff Packager and is gated by the Readiness Gatekeeper decision. It serves two complementary goals:

1. **External SEO:** Improve visibility in search engines for web-facing or publicly accessible projects.
2. **Internal Discoverability:** Improve findability within knowledge bases, documentation systems, or internal tooling.

Every project has at least one of these needs. This skill applies to all project types.

---

## Dependencies

- **Required input:** Handoff Package artifact.
- **Trigger condition:** Gatekeeper decision must be Proceed or Conditional. Do not produce publication-oriented recommendations for a Hold decision.
- **Feeds into:** The receiving team's execution plan (SEO recommendations slot into the Later roadmap or the post-delivery workstream).

---

## Trigger Behavior by Decision State

| Gatekeeper Decision | Skill Behavior |
|---|---|
| **Proceed** | Full SEO recommendation package. All domains analyzed. Publication actions permitted. |
| **Conditional** | Full package with condition-linked risk flags on any recommendation that depends on an unresolved mandatory condition. |
| **Hold** | Do not invoke this skill. If invoked in error, emit: `SEO_OPTIMIZER_BLOCKED: Gatekeeper decision is Hold. SEO recommendations should not be produced until readiness is confirmed.` |

---

## Project Type Detection

Before beginning analysis, determine which mode applies:

| Project Type | Primary Mode | Secondary Mode |
|---|---|---|
| Public website, web app, or SaaS product | External SEO | Internal Discoverability (if documentation exists) |
| Documentation site, knowledge base, or wiki | External SEO + Internal Discoverability | Equal priority |
| Internal tool, private API, or confidential project | Internal Discoverability | External SEO not applicable — state this explicitly |
| Mixed (public-facing with internal docs) | Both modes, full analysis | |

If no public web property exists, skip all publication-oriented recommendations and state: *External SEO is not applicable for this project. All recommendations are scoped to internal discoverability.*

---

## Operating Modes

| Mode | When to Use |
|---|---|
| **Full** | Web-facing project with indexable content. Both external and internal domains analyzed. |
| **Internal Only** | No public web presence. Focus entirely on internal discoverability. |
| **Audit** | Project has existing SEO work. Focus on gap analysis and improvement over the current baseline. |

---

## Analysis Domains

### Domain 1 — Technical SEO (External only)
- Crawlability and indexability: robots.txt, meta robots, noindex directives.
- Canonical tags and duplicate content management.
- Sitemap presence, structure, and submission.
- Redirect chains and broken links.
- Structured data and schema markup coverage.
- HTTPS enforcement and certificate validity.

### Domain 2 — Content SEO (External and Internal)
- Intent mapping: does the content match the search intent of the target audience?
- Topical coverage: are core topics fully addressed or are there significant gaps?
- Information architecture: is content organized in a way that supports discovery?
- Title and meta description quality: descriptive, unique, within character limits.
- Header structure: logical hierarchy, keyword presence without stuffing.
- Content freshness signals: last-updated dates, stale content inventory.

### Domain 3 — Performance and User Experience (External)
- Core Web Vitals readiness: Largest Contentful Paint, Interaction to Next Paint, Cumulative Layout Shift.
- Mobile-first readiness: viewport configuration, tap targets, text legibility.
- Accessibility factors with SEO relevance: alt text, link labels, language attributes.
- Page load signals: image optimization, render-blocking resources, caching headers.

### Domain 4 — Authority and Off-Page Signals (External)
- Backlink profile readiness: is the project positioned to earn or attract links?
- Digital PR and citation opportunities relevant to the project's domain.
- Brand consistency: name, URL, and description consistent across key surfaces.

### Domain 5 — Local and International SEO (External, if applicable)
- Locale targeting: hreflang configuration, language tags.
- Regional content alignment.
- Local business signals if applicable (name, address, phone consistency).

### Domain 6 — Internal Discoverability (Internal and mixed projects)
- Metadata taxonomy: are tags, categories, and labels consistent and meaningful?
- Keyword and search indexing: are documents discoverable via internal search?
- Cross-linking: are related content pieces linked to each other?
- Navigation and structure: can a user find key content within 2–3 clicks or queries?
- Content naming conventions: are file names, page titles, and slugs descriptive?
- Stale or orphaned content: pages with no inbound links or no recent views.

---

## Scoring and Prioritization

Score each finding using two dimensions:

**Impact** (1–5):
- 5: Blocks indexing, prevents discovery, or affects all content.
- 3: Meaningful gap affecting a subset of content or users.
- 1: Optimization with marginal expected gain.

**Effort** (S / M / L / XL — same calibration as other skills in this workflow).

**Priority Lane:**
- **Now:** High impact (4–5), S or M effort. Resolve before or immediately after launch.
- **Next:** High-to-medium impact (3–4), M or L effort. First 60 days.
- **Later:** Lower urgency or XL effort. 60–90 day roadmap.

Confidence is required for every recommendation: High (directly evidenced), Medium (inferred from available signals), Low (assumed or extrapolated).

---

## Workflow

### Step 1 — Intake

- Read the Handoff Package artifact.
- Determine project type and applicable mode.
- Confirm the Gatekeeper decision permits execution.
- List what assets are accessible: live URL, source files, sitemaps, analytics reports, CMS access.
- Note what is not accessible and the resulting confidence impact.

### Step 2 — Baseline Assessment

- Identify existing SEO signals visible in the project artifacts (robots.txt, sitemap, meta tags, schema, internal link structure).
- Note what baseline data is available (analytics, search console data, crawl reports) and what is assumed.
- Do not fabricate metrics. If no baseline data exists, state that all impact estimates are directional only.

### Step 3 — Domain Analysis

For each applicable domain, analyze the available evidence and produce findings using the finding format below.

**Finding Format:**
```
SEO-XXX: [Short Title]
  Domain: (from the six domains)
  Impact: 1–5
  Effort: S / M / L / XL
  Confidence: High / Med / Low
  Priority: Now / Next / Later
  Evidence: (what was observed and where)
  Recommendation: (specific, actionable steps)
  Owner Profile: (from standard profiles)
  Acceptance Criterion: (measurable condition confirming the fix)
```

### Step 4 — Internal Discoverability Package

For all projects regardless of type, produce a set of internal discoverability artifacts (see Output Section 6).

### Step 5 — Measurement Framework

Define how SEO progress will be measured. Use only metrics that are realistically trackable given the project's tools and resources. Do not recommend instrumentation that requires tools the project does not have.

---

## Output Contract

Return results in this exact section order.

---

### 1. SEO Executive Summary

- Project type and applicable mode.
- Gatekeeper decision state and any condition-linked risk flags.
- Top 3 findings with the highest expected impact.
- Overall SEO and discoverability maturity snapshot.
- Confidence level for the assessment.
- What was not assessed and why.

---

### 2. Baseline Signals and Evidence

- Available data sources consulted (live URL, source files, analytics, crawl reports).
- Current observable SEO signals: indexability status, sitemap presence, schema coverage, meta quality.
- Internal discoverability signals: taxonomy consistency, cross-linking density, search index coverage.
- Gaps in baseline data and the resulting confidence impact.

---

### 3. Domain-by-Domain Findings

For each domain analyzed:
- Domain name and applicability note (if a domain is not applicable, state why).
- Findings in priority order (Critical issues first, then Now, Next, Later).
- Each finding using the finding format from Step 3 of the Workflow.

---

### 4. Prioritized Recommendations

| ID | Title | Domain | Priority | Impact | Effort | Owner Profile | Confidence |
|---|---|---|---|---|---|---|---|
| SEO-001 | | | Now/Next/Later | 1–5 | S/M/L/XL | | High/Med/Low |

Full finding detail (from finding format) for every Now recommendation. Summary entries for Next and Later.

---

### 5. 30-60-90 Day Execution Plan

**Days 1–30 (Now):**
Technical and quick-win actions. Target: foundations in place.

**Days 31–60 (Next):**
Content and structural improvements. Target: coverage gaps addressed.

**Days 61–90 (Later):**
Authority, performance, and strategic improvements. Target: measurable ranking or discoverability gains.

For each phase: list action IDs, owner profiles, and expected signals that indicate progress.

---

### 6. Internal Discoverability Package

Applicable to all projects:

- **Taxonomy Tags:** Recommended tags or categories for this project's primary content items. Consistent with any existing taxonomy system.
- **Suggested Keywords:** 5–10 terms or phrases that should appear in titles, headers, and search index entries for primary content.
- **Cross-Reference Map:** Key content items and which other items they should link to or be linked from.
- **Naming Conventions:** Recommended patterns for file names, page slugs, and section headers.
- **Stale or Orphaned Content:** Items identified as having no inbound links, low search index weight, or outdated metadata.

If no content artifacts were accessible, state this and provide template recommendations based on the project type.

---

### 7. Measurement Framework

| KPI | Baseline (if known) | Target | Measurement Method | Cadence |
|---|---|---|---|---|
| (metric) | (current value or "not established") | (goal) | (tool or method) | Weekly / Monthly |

Include only KPIs that are trackable with the project's current tooling. Flag KPIs that require instrumentation not yet in place.

---

### 8. Risks, Constraints, and Assumptions

- Recommendations that depend on unresolved Gatekeeper Conditional conditions — flag these explicitly.
- External factors that could affect SEO outcomes (algorithm changes, platform dependencies, content ownership).
- Assumptions made due to missing access or data.
- Constraints that limit what can be recommended (confidentiality requirements, platform restrictions, resource limits).

---

## Quality Rules

- Every recommendation must cite evidence from the project artifacts or a clearly stated assumption.
- Do not fabricate baseline metrics. If no data exists, say so and provide directional estimates only.
- Recommendations must be specific to this project. Generic advice that applies to every site is not acceptable.
- Every recommendation must have an acceptance criterion.
- Internal discoverability section is required even when external SEO is not applicable.
- Condition-linked risk flags must appear in any recommendation that depends on an unresolved Gatekeeper condition.

---

## Constraints

- This skill analyzes and recommends. It does not modify live sites, content management systems, or search index configurations.
- SEO outcomes depend on many external factors outside the project's control. Impact estimates are directional, not guaranteed.
- If the project is under confidentiality restrictions, all recommendations must be scoped to private readiness actions. No publication-oriented actions should be recommended for confidential projects.

---

## Prompt Starter

```
Run the Post-Delivery SEO Optimizer skill in [Full / Internal Only / Audit] mode
using the attached Handoff Package artifact.
The Gatekeeper decision is [Proceed / Conditional].
Return the full output contract in section order.
Mark confidence levels for all findings and flag any condition-linked risks.
```
