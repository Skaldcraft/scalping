# Workflow Implementation Guide
**Version:** 1.0  
**Scope:** Project Review, Import, Pre-Publication, and Handoff Workflows  
**Compatible with:** Antigravity, Cursor, Windsurf, Claude, and any agent-capable tool

---

## 1. What This Workflow Is

This is a structured, multi-skill workflow for reviewing, auditing, and handing off projects of any type — software, content, design systems, data pipelines, documentation, or mixed-format work. It is designed to run as a chain of specialist skills, each producing a structured artifact that feeds the next.

The workflow produces:
- A grounded analysis of the project as it actually is
- A sequenced, actionable plan for improvement or transition
- A readiness decision that gates forward movement
- A transfer-ready package for any receiving team or builder
- Optional: security depth analysis and SEO/discoverability recommendations

---

## 2. Shared Glossary

These terms carry specific meaning throughout all skill files. Use them consistently.

| Term | Definition |
|---|---|
| **Builder** | Any agent, AI assistant, developer, or automated system executing a skill. Not a named person. |
| **Skill** | A single executable workflow unit with a defined input, process, and output contract. |
| **Artifact** | A structured output produced by a skill. Artifacts are the inputs to downstream skills. |
| **Finding** | An observed, evidence-based conclusion about the current state of the project. Distinguished from assumptions. |
| **Action** | A discrete unit of work derived from one or more findings. Has a defined scope, effort, and acceptance criterion. |
| **Package** | The consolidated set of artifacts assembled for transfer to a receiving team or builder. |
| **Owner Profile** | A role-based responsibility assignment. Never a named individual. See Section 5. |
| **Confidence** | A three-level signal — High (verified), Medium (inferred), Low (assumed) — attached to findings and scores. |
| **Hold** | A gatekeeper decision that blocks forward movement and triggers a targeted revision loop. |
| **Proceed** | A gatekeeper decision allowing full forward movement. |
| **Conditional** | A gatekeeper decision allowing limited forward movement under defined controls. |
| **Abort** | A workflow stop issued when minimum input quality is not met. Distinct from Hold. |

---

## 3. Skill Inventory

| # | File | Role | Required |
|---|---|---|---|
| 1 | `01_project-overview.md` | Discovery and structural analysis | Always |
| 2 | `02_project-action-planner.md` | Planning and sequencing | Always |
| 3 | `03_readiness-gatekeeper.md` | Readiness evaluation and gate decision | Always |
| 4 | `04_handoff-packager.md` | Transfer package assembly | When handing off |
| 5 | `05_security-review.md` | Security and vulnerability analysis | When risk is present |
| 6 | `06_post-delivery-seo-optimizer.md` | SEO and discoverability | When web or documentation output exists |

---

## 4. Execution Paths

### 4.1 Full Workflow (Recommended Default)

```
[01 Project Overview]
        |
   ┌────┴────┐
   |         |
[05 Security] [02 Action Planner]   ← run in parallel; both consume Overview artifact
   |         |
   └────┬────┘
        |
[03 Readiness Gatekeeper]
        |
   ┌────┴─────────────────────┐
   |                          |
[Proceed / Conditional]      [Hold]
   |                          |
[04 Handoff Packager]    [Revision Loop] → back to 02 with gatekeeper report
   |
[06 SEO Optimizer]   ← only if web/documentation output exists
```

### 4.2 Fast Review Path

Use when time is constrained or a quick signal is needed.

```
[01 Project Overview — Fast Mode]
        |
[02 Action Planner — Fast Planning Mode]
        |
[03 Readiness Gatekeeper]
```

Skip skills 04, 05, and 06. Document that full analysis is deferred.

### 4.3 Security-Only Path

Use when a project has already been reviewed but a specific security concern has surfaced.

```
[05 Security Review — Risk-Focused Mode]
        |
[03 Readiness Gatekeeper — partial input, marked reduced confidence]
```

### 4.4 Re-Entry Path (After Hold)

Use when a project was previously issued a Hold and revisions have been made.

```
[03 Readiness Gatekeeper — re-review mode]
    Input: previous gatekeeper report + revised artifacts
```

Maximum re-entry cycles: **2**. If a project reaches a third Hold without resolution, the workflow must emit an `ESCALATION_REQUIRED` signal and halt. A human decision authority must review before any further cycles.

---

## 5. Owner Profiles

Use these role labels across all skill outputs. Do not assign named individuals.

| Profile | Scope |
|---|---|
| **Technical Lead** | Architecture decisions, cross-cutting concerns, final technical sign-off |
| **Backend Engineer** | Server logic, APIs, data layer, integrations |
| **Frontend Engineer** | UI components, client-side logic, accessibility |
| **DevOps / Platform Engineer** | Infrastructure, CI/CD, deployment, environment configuration |
| **Security Engineer** | Vulnerabilities, compliance mapping, secrets management |
| **QA Engineer** | Testing, validation, acceptance criteria verification |
| **Product Owner** | Scope, priority decisions, stakeholder communication |
| **Documentation Lead** | Content structure, internal discoverability, knowledge base |
| **Receiving Builder** | The agent or team accepting the handoff package |

---

## 6. Effort Calibration

Use these definitions consistently when sizing actions. Validate with the receiving team.

| Size | Duration | Coordination |
|---|---|---|
| **S** | ≤ 1 day | Single contributor, no external dependency |
| **M** | 2–5 days | 1–2 contributors, minor coordination |
| **L** | 1–2 sprints | Team coordination required, some dependencies |
| **XL** | Multi-sprint | Architectural or organizational change, significant risk |

---

## 7. Conflict Resolution Rules

When the same finding is assessed differently by two skills (e.g., action planner rates it Medium, security review rates it Critical):

1. **The higher severity always wins** for risk register and gatekeeper inputs.
2. **The finding must be flagged as conflicting** with both assessments recorded.
3. **The gatekeeper is the final arbitrator.** It must acknowledge the conflict and explain its decision.
4. No skill output may silently override another's finding. Merge, don't replace.

---

## 8. Abort Conditions

A builder must stop and emit `WORKFLOW_ABORTED` — not a Hold — when:

- No project source files, configuration, or documentation are accessible.
- The available input is insufficient to produce even Low-confidence findings across more than half the required output sections.
- The project type cannot be determined from available context.

An Abort is not a readiness failure. It means the workflow cannot run, not that the project is unready. Document what is missing and what would be needed to re-start.

---

## 9. Parallelization Rules

Skills 02 (Action Planner) and 05 (Security Review) may run in parallel after Skill 01 (Project Overview) completes.

Rules:
- Both skills consume the Project Overview artifact independently.
- Neither may begin without a complete Project Overview artifact.
- Results must be merged before Skill 03 (Readiness Gatekeeper) begins.
- Conflict resolution (Section 7) applies at the merge step.

All other skills must run sequentially as shown in Section 4.

---

## 10. Mode Selection Guide

Each skill supports multiple operating modes. Use this table to select the right mode based on context.

| Context | Overview Mode | Planner Mode | Security Mode |
|---|---|---|---|
| New project, full audit | Deep | Delivery | Comprehensive |
| Existing project, quick check | Fast | Fast Planning | Risk-Focused |
| Importing from another platform | Transition | Transition | Risk-Focused |
| Pre-publication check | Fast | Fast Planning | Comprehensive |
| Post-incident review | Deep | Delivery | Comprehensive |
| No security concern flagged | Any | Any | Skip |

---

## 11. Integrating with Antigravity

### Invoking the workflow

Antigravity should invoke each skill sequentially using the prompt starters defined in each skill file. Pass the artifact from each skill as context input to the next.

**Recommended invocation pattern:**

```
Step 1: "Run the Project Overview skill in [mode] for this repository."
Step 2: [In parallel] "Run the Project Action Planner skill using the Project Overview artifact."
         [In parallel] "Run the Security Review skill in [mode] using the Project Overview artifact."
Step 3: "Run the Readiness Gatekeeper skill using the Project Overview, Action Planner, and Security Review artifacts."
Step 4a (Proceed/Conditional): "Run the Handoff Packager skill using all upstream artifacts."
Step 4b (Hold): "Run the Project Action Planner in re-entry mode using the Gatekeeper Hold report."
Step 5 (if applicable): "Run the Post-Delivery SEO Optimizer using the Handoff Package artifact."
```

### Context passing

Pass the full artifact from the previous skill as context. Do not summarize or truncate upstream artifacts before passing — the downstream skill requires the full output contract.

### Hold loop enforcement

Antigravity must track the hold cycle count per project. Expose this count in the workflow state. Block further execution on the third Hold and surface the `ESCALATION_REQUIRED` signal to the user.

### Artifact naming convention

Name artifacts using the pattern: `{project-slug}_{skill-slug}_{YYYYMMDD}.md`

Example: `my-app_project-overview_20250310.md`

---

## 12. Integrating with Other Tools

This workflow is tool-agnostic. Any system that can:
- Accept a markdown skill file as a prompt or instruction set
- Pass structured text between steps as context
- Track state across a multi-step chain

...can run this workflow. The prompt starters in each skill file are the integration points.

For single-turn tools (tools that cannot maintain multi-step state), run each skill file independently and pass the output manually as context to the next step.

---

## 13. Output File Conventions

| Artifact | Suggested Format |
|---|---|
| Skill outputs | Markdown (`.md`) |
| Handoff package | Markdown or structured JSON |
| SEO optimizer output | Markdown |
| Escalation signal | Plain text flag in workflow state |

All artifacts should be dated and versioned. Use semantic versioning (`v1.0`, `v1.1`) when an artifact is revised after a Hold cycle.

---

## 14. Workflow Quality Checklist

Before closing a workflow run, confirm:

- [ ] All required skills for the selected execution path have produced artifacts.
- [ ] Conflicts between skill outputs have been resolved and documented.
- [ ] The gatekeeper has issued an explicit decision (Proceed, Conditional, or Hold).
- [ ] If Conditional or Hold: mandatory fixes are documented with owner profiles and acceptance criteria.
- [ ] If Proceed: the handoff package is complete and includes a first-week start guide.
- [ ] Hold cycle count is within the two-cycle limit.
- [ ] All assumptions are surfaced, not hidden.
- [ ] Abort conditions were checked at workflow start.
