---
title: Handoff Packager
slug: handoff-packager
summary: Consolidate all upstream workflow artifacts into a single, versioned, builder-neutral handoff package that a receiving team can act on immediately without verbal clarification.
applyTo:
  - '**/*'
---

# Skill: Handoff Packager

## Purpose

Produce a complete, self-contained transfer package from the outputs of all upstream skills. The receiving builder or team must be able to start work using this package alone, without needing to read the individual upstream artifacts or ask clarifying questions.

This skill consolidates and prepares. It does not generate new analysis, redesign the action plan, or override the gatekeeper's decision.

---

## Dependencies

- **Required inputs:** Project Overview artifact, Project Action Planner artifact, Readiness Gatekeeper artifact.
- **Optional inputs:** Security Review artifact.
- **Trigger condition:** Gatekeeper decision must be Proceed or Conditional. Do not produce a handoff package for a Hold decision. Instead, surface the Hold state and direct the upstream team to the Re-Review Plan.

---

## Versioning

Each handoff package is versioned. Use semantic versioning: `v1.0` for the initial package, `v1.1`, `v1.2`, etc. for revisions after Hold cycles.

When producing a revised package after a Hold:
- Increment the version number.
- Add a changelog entry describing what changed from the previous version.
- Do not overwrite or delete the previous version's record.

---

## Workflow

### Step 1 — Intake and Validation

- Confirm all required artifacts are present and dated.
- Confirm the Gatekeeper decision is Proceed or Conditional. If not, stop and emit: `HANDOFF_BLOCKED: Gatekeeper decision is [Hold / ESCALATION_REQUIRED]. Handoff package cannot be produced until readiness is confirmed.`
- List any optional artifacts that are absent and note the confidence impact.

### Step 2 — Normalize and Merge

- Align terminology across all artifacts. Use the standard glossary from the Implementation Guide.
- Merge overlapping findings. Record the source artifact for each merged item.
- Resolve any remaining conflicts between artifacts using the Implementation Guide conflict resolution rules (Section 7).
- Do not silently drop any finding, mandatory fix, or open unknown.

### Step 3 — Build the Executive Transfer Summary

- Write a narrative (not a bullet list) that explains what is being handed off, why now, and what the receiving team needs to know first.
- State the gatekeeper decision and what it means for the receiving team in plain language.

### Step 4 — Assemble the Execution Starter Kit

- Pull the full Now and Next action lists from the Action Planner.
- If the gatekeeper issued a Conditional decision, prepend the mandatory conditions as a pre-execution checklist. These must be resolved before or during the first week.
- Provide a first-week start guide in a concrete day-by-day format (see Section 7 of the output contract).
- List all inputs the receiving builder needs to have on hand before starting Day 1.

### Step 5 — Finalize Package

- Assign a package version number.
- Record all source artifacts with their dates.
- Add a changelog if this is a revised package.

---

## Output Contract

Return results in this exact section order.

---

### 1. Package Metadata

| Field | Value |
|---|---|
| Project | (name or slug) |
| Date | (YYYY-MM-DD) |
| Package Version | v1.0 |
| Gatekeeper Decision | Proceed / Conditional |
| Producing Builder Role | (profile) |
| Receiving Builder Role | (profile) |
| Changelog | (blank for v1.0; list changes for subsequent versions) |

---

### 2. Executive Transfer Summary

A written narrative covering:
- What is being handed off and why now.
- The current readiness state in plain language.
- The most important thing the receiving team needs to know before opening anything else.
- What this package does and does not include.

Keep this to 150–250 words. It is the first thing the receiving builder reads.

---

### 3. Source Traceability

| Artifact | Date | Coverage Status | Confidence |
|---|---|---|---|
| Project Overview | | Complete / Partial | High / Med / Low |
| Action Planner | | | |
| Readiness Gatekeeper | | | |
| Security Review | | Present / Absent | |

---

### 4. Current-State Snapshot

- Architecture and capability highlights from the Project Overview.
- Dependency and operational posture summary.
- The top 3 risks currently active, with their severity and mitigation status.

This section should be readable in under 5 minutes. Reference the Project Overview artifact for full detail.

---

### 5. Prioritized Execution Plan

**Now (Quick wins):**
Pull directly from the Action Planner. Include action ID, title, owner profile, effort, and first action to take.

**Next (Near-term):**
Include action ID, title, owner profile, effort, and prerequisite actions.

**Later (Strategic roadmap):**
Summary only. Include action ID, title, and rationale for deferral.

**Dependency sequence:**
Reproduce the dependency map from the Action Planner verbatim.

---

### 6. Risk and Control Register

| ID | Risk | Severity | Mitigation Status | Quality Gate | Rollback Note |
|---|---|---|---|---|---|
| (finding ID) | (description) | Critical / High / Med / Low | Mitigated / Accepted / Open | (gate condition) | (revert approach if applicable) |

Flag any risk that is Open (no mitigation) and Critical or High. These require explicit risk acceptance from the receiving team before proceeding.

---

### 7. Mandatory Conditions

Pull directly from the Gatekeeper artifact. Do not paraphrase — reproduce the mandatory fix list verbatim and add the acceptance criterion for each.

If the gatekeeper issued Proceed (no conditions), state that explicitly: *No mandatory conditions. Package is clear for full execution.*

---

### 8. First-Week Start Guide

A day-by-day plan for the receiving builder's first five working days. Each day entry includes:
- **Objective:** What the day is for.
- **Actions:** 2–4 concrete tasks drawn from the Now list and mandatory conditions.
- **Required inputs:** What the builder must have available to complete that day's work.
- **End-of-day check:** A simple yes/no question confirming the day's objective was met.

Example structure:
```
Day 1 — Orient and Verify
  Objective: Confirm environment access and validate top 3 assumptions from the Overview.
  Actions:
    1. Access project repository and confirm branch permissions.
    2. Run build process and document any failures.
    3. Review the Risk Register and confirm severity ratings match observed state.
  Required inputs: Repository access, build toolchain documentation.
  End-of-day check: Can you build and run the project locally or in a staging environment?
```

Adapt the day-by-day structure to the project type. For non-software projects: replace build/run steps with equivalent orientation tasks (e.g., review editorial calendar, audit content inventory, map data schema).

---

### 9. Re-Review and Governance Plan

- Checkpoint cadence recommended during execution.
- Acceptance criteria for the Conditional conditions (if applicable).
- Trigger conditions that should prompt a return to the Gatekeeper.
- Owner profile responsible for governance oversight during execution.

---

### 10. Open Unknowns and Assumptions

Reproduce all open unknowns from upstream artifacts in a single consolidated list. For each:
- Source artifact.
- Description of the unknown.
- Impact if it remains unresolved.
- Recommended action for the receiving team.

---

## Quality Rules

- The package must be self-contained. A new builder with no prior context must be able to start Day 1 using only this document.
- Never summarize mandatory conditions — reproduce them verbatim from the Gatekeeper.
- Maintain explicit source traceability for every critical decision.
- Open risks marked as Critical or High must appear in both Section 6 and the First-Week Start Guide.
- Every section must be present. If a section has no content, state why (e.g., "Security Review was not performed for this project.").

---

## Constraints

- This skill requires a Gatekeeper Proceed or Conditional decision. It cannot produce a package for a Hold.
- This skill consolidates and prepares. It does not redesign the action plan or override upstream decisions.
- Package quality depends on completeness of upstream artifacts. Gaps must be visible, not hidden.

---

## Prompt Starter

```
Run the Handoff Packager skill using the attached Project Overview, Action Planner,
Readiness Gatekeeper artifacts [and Security Review if available].
The Gatekeeper decision is [Proceed / Conditional].
Build a complete v[X.X] transfer package with source traceability,
prioritized execution plan, mandatory conditions, and a first-week start guide.
```
