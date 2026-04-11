---
title: Project Overview
slug: project-overview
summary: Analyze any project and produce a grounded, structured overview of architecture, workflows, capabilities, risks, and prioritized recommendations. Compatible with software, content, design, data, and documentation projects.
applyTo:
  - '**/*'
---

# Skill: Project Overview

## Purpose

Generate an objective, evidence-based overview that explains what a project is, how it works, where it carries risk, and what should be addressed first. This artifact is the required input for the Project Action Planner and Readiness Gatekeeper skills, and the optional input for Security Review.

---

## Abort Check (Run First)

Before beginning analysis, verify that minimum input quality is met:

- At least one project source file, configuration file, or documentation artifact is accessible.
- The project type can be determined from available context.
- At least Low-confidence findings can be produced for more than half of the required output sections.

If these conditions are not met, emit `WORKFLOW_ABORTED` with a description of what is missing and what would be required to re-start. Do not produce a partial overview artifact.

---

## Operating Modes

Select the mode that matches the workflow context. If unsure, use the table in the Implementation Guide Section 10.

| Mode | When to Use | Depth |
|---|---|---|
| **Fast** | Quick signal, time-constrained review, pre-flight check | High-signal only: architecture, critical risks, top dependencies |
| **Deep** | Full audit, new project onboarding, post-incident review | Complete analysis across all sections |
| **Transition** | Importing from another platform, ownership transfer, migration | Emphasis on portability, handoff quality, and gap identification |

---

## Workflow

### Step 1 — Project Discovery

- Identify the project type: software, content, design system, data pipeline, documentation, or mixed.
- Identify language(s), framework(s), package managers, runtimes, and tooling.
- Locate key files: manifests, build scripts, CI/CD configuration, infrastructure definitions, and documentation.
- Determine system boundaries, entry points, and external integrations.
- Note what is missing and what confidence that absence creates.

### Step 2 — Structural Mapping

- Build a map of major directories, modules, or content sections.
- Identify architectural style (monolith, microservices, static site, pipeline, etc.) or document type (knowledge base, spec, runbook, etc.).
- Distinguish core logic, infrastructure concerns, interface layers, and content layers.
- Mark coupling points and shared dependencies.

### Step 3 — Capability Analysis

- List the core capabilities the project implements or is intended to implement.
- For each capability: describe the input, processing path, and output.
- Flag capabilities that are missing, unclear, partially implemented, or undocumented.

### Step 4 — Workflow and Runtime Analysis

- Describe end-to-end flow for the main use cases.
- Capture control flow, data flow, and dependency flow.
- Identify decision points, failure paths, and fallback behavior.
- For content or documentation projects: describe the publishing pipeline, review process, and versioning approach.

### Step 5 — Dependency and Operations Review

- Summarize internal and external dependencies.
- Evaluate the build, test, release, deployment, and observability posture where applicable.
- For non-software projects: evaluate maintenance processes, ownership, review cadence, and sustainability.
- Flag stale dependencies, fragile pipelines, undocumented processes, and single points of failure.

### Step 6 — Risk and Gap Assessment

Classify each issue using the following scale:

| Severity | Definition |
|---|---|
| **Critical** | Blocks function, exposes active harm, or prevents safe handoff. Must be resolved before proceeding. |
| **High** | Material risk to operations, quality, or continuity. Requires a plan before handoff. |
| **Medium** | Meaningful gap but does not block immediate progress. Address in near-term. |
| **Low** | Optimization or hardening. Backlog candidate. |

Separate confirmed findings from assumptions. Mark confidence for each: High, Medium, or Low.

### Step 7 — Recommendations

Provide recommendations grouped by timeline:

- **Quick wins:** 1–3 days, minimal risk, high signal.
- **Near-term:** 1–2 sprints, requires planning and coordination.
- **Strategic:** Multi-sprint, architectural or organizational change.

Do not prescribe implementation details unless required for immediate action. Keep current-state description separate from future-state proposals.

---

## Output Contract

Return results in this exact section order. In Fast mode, Sections 4, 5, and 8 may be abbreviated. In all modes, Sections 1, 6, 7, and 9 are required in full.

---

### 1. Executive Summary

- What the project is and what it does.
- Current maturity and operational state.
- Top 3 issues or opportunities, stated plainly.
- Analysis mode used and confidence level.

---

### 2. Project Map

- Major modules, directories, or content sections and their responsibilities.
- High-level architecture shape or document structure.
- External integrations and system boundaries.

---

### 3. How the System Works

- Primary workflows and the data or control flow through them.
- Key integrations, handoffs, and boundaries.
- Failure paths and fallback behavior where known.

---

### 4. Capability Matrix

| Capability | Status | Confidence | Key Dependencies | Notes |
|---|---|---|---|---|
| (name) | Implemented / Partial / Missing / Unclear | High / Med / Low | (list) | (observations) |

---

### 5. Dependency and Operations Posture

- Build, test, and deployment model (or equivalent for non-software projects).
- Observability, monitoring, and alerting posture.
- Maintenance sustainability signals: stale dependencies, missing owners, undocumented processes.

---

### 6. Risk Register

| Severity | Finding | Operational Impact | Evidence | Confidence |
|---|---|---|---|---|
| Critical / High / Med / Low | (description) | (impact if unresolved) | (source or observation) | High / Med / Low |

---

### 7. Prioritized Recommendations

| Timeline | Recommendation | Expected Impact | Direction | Effort |
|---|---|---|---|---|
| Quick win / Near-term / Strategic | (action) | (outcome) | (approach) | S / M / L / XL |

---

### 8. Transition Readiness

- Components or artifacts that are reusable and well-documented.
- Gaps that must be closed before safe migration or handoff.
- Minimum next steps for the receiving builder or team.

---

### 9. Assumptions and Unknowns

- Explicit assumptions made where evidence was missing.
- Items that could not be assessed and why.
- What additional access or context would improve confidence.

---

## Quality Rules

- Be objective and evidence-based. Distinguish findings from assumptions in every section.
- Prefer project-specific conclusions over generic advice.
- Mark confidence level for all uncertain conclusions.
- Do not conflate current state with desired state in the same statement.
- Avoid generic security or quality advice that applies to every project equally.
- Fast mode must still complete the Risk Register and Recommendations sections in full.

---

## Constraints

- Analysis depth depends on available context. Reduced access must reduce stated confidence — not inflate findings.
- This skill supports review. It does not replace domain-specific audits (legal, compliance, accessibility, etc.).
- If project type is ambiguous, state the assumption made and proceed under that assumption.

---

## Prompt Starter

```
Run the Project Overview skill in [Fast / Deep / Transition] mode for this project.
Return the full output contract in section order.
Mark all assumptions explicitly. Include severity-ranked risks with confidence levels.
```
