---
title: Project Action Planner
slug: project-action-planner
summary: Convert Project Overview findings into a sequenced, execution-ready action plan with calibrated effort, defined ownership profiles, and measurable acceptance criteria.
applyTo:
  - '**/*'
---

# Skill: Project Action Planner

## Purpose

Transform findings from the Project Overview (and optionally, Security Review) into a concrete, prioritized plan that a builder or team can execute immediately. Every action must have a clear scope, defined owner profile, acceptance criterion, and honest effort estimate.

---

## Dependencies

- **Required input:** Project Overview artifact (full output contract).
- **Optional input:** Security Review artifact. If present, its findings must be merged using the conflict resolution rules defined in the Implementation Guide (Section 7). Security severity always takes precedence for the same finding.
- **Feeds into:** Readiness Gatekeeper, Handoff Packager.

---

## Operating Modes

| Mode | When to Use |
|---|---|
| **Fast Planning** | Quick wins and top-risk actions only. Produces a short, prioritized list without full dependency sequencing. |
| **Delivery** | Full sprint-oriented plan with sequenced dependency chains, ownership, and quality gates. |
| **Transition** | Handoff-grade plan structured for a receiving team or builder with no prior context. |
| **Re-Entry** | Use after a Gatekeeper Hold. Consumes the Hold report and produces a targeted revision plan addressing only the mandatory fixes. Do not re-plan the entire backlog. |

---

## Workflow

### Step 1 — Ingest and Normalize

- Parse all findings, recommendations, assumptions, and unknowns from upstream artifacts.
- Deduplicate overlapping items. When the same issue appears in both Overview and Security Review, merge into one action and note both sources.
- Apply conflict resolution: the higher severity rating wins. Record both ratings in the action entry.
- Convert each finding into an action candidate. Discard candidates that have no clear acceptance criterion — mark them as unknowns instead.

### Step 2 — Score and Prioritize

Score each action candidate on two dimensions:

**Impact** (1–5):
- 5: Unblocks multiple downstream actions or removes a Critical/High risk.
- 3: Meaningful improvement, limited downstream effect.
- 1: Optimization or nice-to-have.

**Effort** (using calibrated scale):
- S: ≤ 1 day, single contributor, no external dependency.
- M: 2–5 days, 1–2 contributors, minor coordination.
- L: 1–2 sprints, team coordination required, some dependencies.
- XL: Multi-sprint, architectural or organizational change.

Priority grouping:
- **Now (Quick wins):** High impact, S or M effort, no blocking dependencies.
- **Next (Near-term):** High-to-medium impact, M or L effort, prerequisites met or achievable within one sprint.
- **Later (Strategic):** Lower urgency or XL effort, multi-sprint coordination required.

Mandatory remediation (Critical/High findings from risk register or security review) must appear in Now or Next regardless of effort. Do not defer mandatory remediation to Later.

### Step 3 — Sequence by Dependencies

- Build prerequisite chains: identify which actions must complete before others can begin.
- Identify blockers (actions that prevent others from starting) and enablers (actions that unlock parallel tracks).
- Identify actions that can run in parallel and mark them explicitly.
- Produce an execution order that minimizes rework.

### Step 4 — Define Action Packages

For every action in the Now and Next groups, produce a full action package (see Output Section 4). For Later actions, a summary entry is sufficient unless they are mandatory remediations.

### Step 5 — Add Quality Gates

For actions rated Critical or High, define:
- A quality gate: what must be true before the action is considered done.
- A rollback note: how to revert if the change breaks something in production or staging.

### Step 6 — Re-Entry Mode (After Hold)

When running in Re-Entry mode:
- Consume the Gatekeeper Hold report as the primary input, not the full Project Overview.
- Produce actions only for mandatory fixes listed in the Hold report.
- Mark each action with the Hold cycle number it belongs to (e.g., Hold-1, Hold-2).
- If a mandatory fix was also present in a previous plan, note that it was not resolved and escalate its priority.

---

## Output Contract

Return results in this exact section order.

---

### 1. Planning Summary

- Mode used.
- Source artifacts consumed and their dates.
- Total actions identified (by priority group).
- Top 3 expected outcomes if the Now actions are completed.
- Any conflicts resolved between upstream artifacts, and how.

---

### 2. Action Backlog

| ID | Title | Priority | Source Finding | Severity | Impact | Effort | Owner Profile |
|---|---|---|---|---|---|---|---|
| ACT-001 | (title) | Now / Next / Later | (finding ID or description) | Critical / High / Med / Low | 1–5 | S / M / L / XL | (profile) |

---

### 3. Dependency Map

- Prerequisite chains: which actions must complete before others.
- Blockers: actions that hold up the most downstream work.
- Parallel tracks: actions that can run simultaneously.
- Expressed as a plain-text ordered list or table. No external tooling required to read it.

Example format:
```
ACT-001 → ACT-003 → ACT-007
ACT-002 (parallel with ACT-001) → ACT-005
ACT-004 (no dependencies)
```

---

### 4. Action Packages (Now and Next)

For each action:

**ACT-XXX: [Title]**
- **Objective:** What this action achieves and why it matters.
- **Scope:** What is included and what is explicitly excluded.
- **Owner Profile:** (from standard profiles in Implementation Guide Section 5)
- **Required Inputs:** What the owner needs before starting.
- **Dependencies:** Prerequisite action IDs.
- **Parallel with:** Action IDs that can run at the same time (if any).
- **Effort:** S / M / L / XL with brief rationale.
- **Risks and Mitigations:** What could go wrong and how to reduce that risk.
- **Quality Gate:** The condition that must be true for this action to be complete.
- **Rollback Note:** How to revert this change if it causes regression (for High/Critical actions).
- **Acceptance Criteria:** One or more testable, measurable conditions confirming success.

---

### 5. Later Roadmap

| ID | Title | Rationale for Deferral | Prerequisite Actions | Effort |
|---|---|---|---|---|

---

### 6. Risk and Control Plan

- Risks introduced by executing this plan (not risks from the project itself).
- Mitigations for each new risk.
- Quality gates attached to high-risk changes.

---

### 7. Success Metrics

- Leading indicators: signals visible within 1–2 weeks of execution.
- Lagging indicators: outcomes measurable after 1–2 sprints.
- Measurement approach for each metric.

---

### 8. Open Unknowns

- Action candidates that were dropped because no acceptance criterion could be defined.
- Findings that require clarification before an action can be formed.
- These feed directly into the Gatekeeper's assumptions and unknowns section.

---

## Quality Rules

- Every action in Now and Next must have at least one measurable acceptance criterion.
- Effort estimates must use the calibrated scale from the Implementation Guide. Do not invent alternative scales.
- Owner profiles must come from the standard list in the Implementation Guide. Do not assign named individuals.
- Do not defer mandatory remediations (Critical/High severity) to Later.
- Clearly mark any action whose feasibility depends on an unresolved unknown.
- In Re-Entry mode, scope strictly to mandatory fixes. Do not expand the plan.

---

## Constraints

- Plan quality depends on completeness of upstream artifacts. Reduced input must reduce confidence, not hide gaps.
- Effort estimates are directional. The receiving team is responsible for validating them.
- This skill plans execution. It does not make readiness decisions — that is the Gatekeeper's role.

---

## Prompt Starter

```
Run the Project Action Planner skill in [Fast Planning / Delivery / Transition / Re-Entry] mode
using the attached Project Overview artifact [and Security Review artifact if available].
Return the full output contract in section order.
Apply conflict resolution where findings overlap.
```
