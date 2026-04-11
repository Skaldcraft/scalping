---
title: Readiness Gatekeeper
slug: readiness-gatekeeper
summary: Evaluate upstream workflow artifacts against a standardized readiness rubric and issue an explicit proceed, conditional, or hold decision with documented rationale, mandatory fixes, and a re-review plan.
applyTo:
  - '**/*'
---

# Skill: Readiness Gatekeeper

## Purpose

Issue a single, auditable readiness decision — Proceed, Conditional, or Hold — based on structured evaluation of upstream artifacts. This skill does not generate implementation plans. It evaluates evidence and gates forward movement.

---

## Dependencies

- **Required inputs:** Project Overview artifact, Project Action Planner artifact.
- **Optional inputs:** Security Review artifact. If present, its findings must be incorporated into the scoring and gate evaluation. Omitting it when it exists is not permitted.
- **Re-review input:** Previous Gatekeeper report plus revised artifacts.

If any required input is missing, reduce confidence accordingly and note the gap explicitly. Do not inflate scores to compensate for incomplete inputs.

---

## Hold Cycle Limit

This skill tracks the hold cycle count per project.

- **Hold-1 and Hold-2:** Normal revision cycles. Issue targeted mandatory fixes and a re-review plan.
- **Hold-3:** Do not issue another Hold. Emit `ESCALATION_REQUIRED` and halt the workflow. A human decision authority must intervene before any further review cycles.

Record the current hold cycle number in the Evaluation Summary.

---

## Decision States

| Decision | Meaning |
|---|---|
| **Proceed** | All gates pass and weighted score is 80–100. Forward movement is approved without conditions. |
| **Conditional** | All gates pass but weighted score is 65–79, or one non-critical gate condition is partially met. Forward movement is approved under defined controls. |
| **Hold** | One or more hard-stop gates fail, or weighted score is below 65. Forward movement is blocked until mandatory fixes are resolved. |

---

## Scoring Framework

Score each category from 1 to 5. Compute the weighted total out of 100.

| Category | Weight | What It Measures |
|---|---|---|
| **Clarity and Completeness** | 25 | Are findings well-documented? Are assumptions explicit? Is scope defined? |
| **Operational Readiness** | 25 | Can the project be built, deployed, and maintained? Are critical processes documented? |
| **Risk and Control Posture** | 25 | Are risks identified with mitigations? Are Critical and High findings addressed or accepted with rationale? |
| **Execution Readiness** | 15 | Is the action plan sequenced, owned, and measurable? Are acceptance criteria defined? |
| **Transition Quality** | 10 | Is the handoff package or transition plan complete enough for a receiving team to start? |

### Score Anchors

Use these to calibrate scores consistently across projects of all types:

**1 — Not present or entirely unclear.** No usable evidence.  
**2 — Partially present with significant gaps.** Major areas undocumented or unaddressed.  
**3 — Present with notable gaps.** Core areas covered; secondary areas missing.  
**4 — Present and complete with minor gaps.** Gaps are low-risk and do not block forward movement.  
**5 — Complete, clear, and verified.** No meaningful gaps.

### Threshold Table

| Score | Decision |
|---|---|
| 80–100 | Proceed |
| 65–79 | Conditional |
| 0–64 | Hold |

---

## Hard-Stop Gates

Gates are evaluated independently from the numeric score. A gate failure always blocks Proceed, regardless of the weighted score. A project with a score of 95 that fails a gate receives a Hold or Conditional, not a Proceed.

| Gate | Pass Condition |
|---|---|
| **G1: Workflow Defined** | The end-to-end workflow for at least one primary use case is explicitly described. |
| **G2: Output Criteria Testable** | At least one acceptance criterion per priority action is measurable and specific. |
| **G3: Constraints Documented** | Scope limits, non-goals, and known constraints are explicitly stated. |
| **G4: Critical Risks Addressed** | Every Critical-severity finding has at least one mitigation path or a documented risk acceptance decision. |
| **G5: Handoff Actionable** | The transition or handoff plan contains enough information for a receiving builder to take a first action without verbal clarification. |

### Partial Gate Conditions

A gate is Pass or Fail. However, if a gate would fail due to a single minor gap in an otherwise complete section, the gatekeeper may issue a **Conditional Pass** on that gate — but only if:

- The gap does not affect Critical or High severity items.
- The conditional path explicitly names the gap and the action required to close it.
- The Conditional Pass converts to a full Fail if not resolved before the next review.

Document every Conditional Pass with the same detail as a Fail.

---

## Workflow

### Step 1 — Intake and Evidence Check

- Verify all required input artifacts are present and contain the expected sections.
- If an optional artifact (Security Review) exists, confirm it is included.
- List any missing or incomplete sections before scoring. Do not begin scoring until this list is complete.

### Step 2 — Score Each Category

For each category:
- Record the score (1–5).
- Write a concise evidence note (2–4 sentences) citing specific sections of the upstream artifacts.
- Mark confidence: High (score is directly evidenced), Medium (score is inferred), Low (score is assumed).

### Step 3 — Evaluate All Gates

Evaluate each gate independently. Do not let the numeric score influence gate evaluation. Record:
- Pass / Fail / Conditional Pass.
- Specific evidence or absence of evidence.
- If Fail or Conditional Pass: the exact condition that must be met to convert to Pass.

### Step 4 — Compute Weighted Score

Multiply each category score by its weight. Sum the results. Compare to the threshold table.

### Step 5 — Issue Decision

Apply this decision logic:
1. If any gate is a hard Fail → **Hold** (regardless of numeric score).
2. If numeric score is below 65 → **Hold** (even if all gates pass).
3. If numeric score is 65–79, or any gate is Conditional Pass → **Conditional**.
4. If numeric score is 80+ and all gates pass → **Proceed**.

### Step 6 — Define Conditions and Mandatory Fixes (if Hold or Conditional)

For each blocking issue:
- State the mandatory fix clearly.
- Assign an owner profile.
- Define the acceptance criterion for the fix.
- Estimate effort (S/M/L/XL).

For Conditional decisions, also state:
- What can proceed now.
- Under what controls.
- What triggers escalation if conditions are not met.

---

## Output Contract

Return results in this exact section order.

---

### 1. Evaluation Summary

- Scope evaluated (which artifacts, their dates, hold cycle number if applicable).
- Final decision: **Proceed / Conditional / Hold / ESCALATION_REQUIRED**.
- Final weighted score (e.g., 74/100).
- Hold cycle count.
- One-paragraph plain-language rationale for the decision.

---

### 2. Category Scores

| Category | Score | Weight | Weighted | Evidence Summary | Confidence |
|---|---|---|---|---|---|
| Clarity and Completeness | /5 | 25 | /25 | (2–4 sentences) | High / Med / Low |
| Operational Readiness | /5 | 25 | /25 | | |
| Risk and Control Posture | /5 | 25 | /25 | | |
| Execution Readiness | /5 | 15 | /15 | | |
| Transition Quality | /5 | 10 | /10 | | |
| **Total** | | | **/100** | | |

---

### 3. Hard-Stop Gate Status

| Gate | Status | Rationale |
|---|---|---|
| G1: Workflow Defined | Pass / Fail / Conditional Pass | (specific evidence) |
| G2: Output Criteria Testable | | |
| G3: Constraints Documented | | |
| G4: Critical Risks Addressed | | |
| G5: Handoff Actionable | | |

---

### 4. Top Blockers

The highest-impact issues preventing full readiness, stated in priority order. For Hold decisions: these are the items that must be resolved before re-review. For Conditional decisions: these are the items that must be resolved during execution.

---

### 5. Mandatory Fixes

| Fix | Rationale | Owner Profile | Acceptance Criterion | Effort |
|---|---|---|---|---|
| (description) | (why this blocks) | (profile) | (testable condition) | S/M/L/XL |

---

### 6. Conditional Path (if applicable)

- What is permitted to proceed now and under which controls.
- What triggers a mandatory pause if conditions are not met during execution.
- Who is responsible for monitoring compliance with conditions.

---

### 7. Re-Review Plan

- Target re-review date or trigger condition.
- Owner profile responsible for presenting revised artifacts.
- Acceptance criteria for each mandatory fix.
- Current hold cycle number and maximum remaining cycles before escalation.

---

### 8. Decision Traceability

- Key assumptions made during scoring.
- Evidence limits: what could not be assessed and why.
- Confidence level for the overall decision (High / Medium / Low).
- If Security Review was not available: note its absence and the resulting confidence reduction.

---

## Quality Rules

- Scores must be based on evidence from upstream artifacts, not general impressions.
- Gate evaluation is independent from numeric scoring. Never override a gate failure with a high score.
- Do not inflate scores for incomplete inputs. Missing evidence reduces confidence and score.
- Distinguish mandatory fixes from recommended improvements. Only mandatory fixes block re-review.
- Mark all low-confidence judgments explicitly.
- In Re-Entry mode: re-score only the categories affected by the mandatory fixes. Do not re-score the entire rubric unless new artifacts substantially change the evidence base.

---

## Constraints

- This skill evaluates readiness. It does not generate implementation plans or designs.
- Final authority over organizational or legal decisions may rest outside this workflow.
- Incomplete input artifacts increase uncertainty and must visibly reduce confidence in the decision.
- The three-hold limit is enforced. Do not waive it without an explicit escalation.

---

## Prompt Starter

```
Run the Readiness Gatekeeper skill on the attached Project Overview and Project Action Planner artifacts
[and Security Review artifact if present].
This is hold cycle [1 / 2 / re-entry review].
Score all categories with evidence notes, evaluate all hard-stop gates,
and return a final decision with mandatory fixes and a re-review plan.
```
