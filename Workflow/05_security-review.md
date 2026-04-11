---
title: Security Review
slug: security-review
summary: Perform structured security analysis on risk areas identified by the Project Overview, produce evidence-based findings, and supply the Readiness Gatekeeper and Action Planner with prioritized remediation inputs.
applyTo:
  - '**/*'
---

# Skill: Security Review

## Purpose

Deliver focused security analysis that amplifies risk signals from the Project Overview. Findings from this skill feed directly into the Action Planner (as actions) and the Readiness Gatekeeper (as evidence for the Risk and Control Posture category).

This skill does not replace specialist penetration testing, legal compliance audits, or formal threat modeling engagements. It provides a structured, reviewable analysis suited to project review, import, pre-publication, and handoff workflows.

---

## Dependencies

- **Required input:** Project Overview artifact — specifically the Risk Register and Capability Matrix sections.
- **Feeds into:** Project Action Planner (security findings become actions), Readiness Gatekeeper (security findings feed Gate G4 and the Risk and Control Posture score).
- **Conflict rule:** When a finding appears in both the Project Overview and this skill with different severity ratings, the higher severity wins. Both ratings must be recorded in the finding entry.

---

## Operating Modes

Select based on the project's risk profile and the workflow context:

| Mode | When to Use | Depth |
|---|---|---|
| **Risk-Focused** | Only Critical and High findings from the Project Overview risk register need deeper analysis. | Targeted deep-dive on flagged areas only. |
| **Comprehensive** | Full security posture review across architecture, dependencies, operations, and data handling. | All analysis domains. |
| **Remediation** | A prior security review exists. Focus on verifying fixes and providing implementation guidance. | Fix validation and implementation detail only. |

---

## Abort Check

If the project has no accessible source, configuration, or infrastructure artifacts, emit `SECURITY_REVIEW_INSUFFICIENT_DATA` and describe what access would be needed. Do not produce speculative findings without evidence.

---

## Analysis Domains

The depth of analysis in each domain scales with the operating mode. In Risk-Focused mode, analyze only the domains that correspond to flagged findings.

### Domain 1 — Authentication and Access Control

- Authentication mechanisms: session management, token handling, credential storage.
- Authorization: role-based or attribute-based access control enforcement.
- Privilege escalation vectors: horizontal (peer data access) and vertical (user to admin).
- API key handling, rate limiting, and multi-factor enforcement.

### Domain 2 — Data Handling and Exposure

- Sensitive data classification: personal, financial, health, operational secrets.
- Encryption in transit (TLS enforcement, cipher strength).
- Encryption at rest: key generation, rotation, access control.
- Error messages and logs: information leakage, stack traces, debug output.
- Data minimization: unnecessary fields transmitted or stored.

### Domain 3 — Input Handling and Injection

- Injection attack surfaces: SQL, command, expression language, template injection.
- Untrusted input sources and unsafe usage patterns.
- Deserialization of untrusted data.
- XML/XXE exposure.

### Domain 4 — Dependency and Supply Chain

- Build an inventory of direct and key transitive dependencies from package manifests.
- Cross-reference against known CVE databases (NVD, GitHub Security Advisories, OSV).
- Flag deprecated, unmaintained, or single-maintainer packages with published CVEs.
- Identify upgrade paths: compatible alternatives, breaking changes, blocked upgrades.

### Domain 5 — Configuration and Infrastructure

- Default credentials left in place.
- Secrets hardcoded in source, configuration files, or environment definitions.
- Overly permissive roles, service accounts, or CORS policies.
- Missing security headers (CSRF, CSP, HSTS).
- Exposed internal services or management ports.
- Container or IaC misconfigurations.

### Domain 6 — Observability and Incident Response

- Security event logging coverage.
- Audit trail completeness and immutability.
- Alerting on security-relevant events.
- Incident response documentation and on-call runbooks.

---

## Severity Definitions

Use these consistently. Do not assign severity based on worst-case scenarios. Base severity on actual exploitability and realistic impact.

| Severity | Exploitability | Impact | Default Timeline |
|---|---|---|---|
| **Critical** | Exploitable without privilege or authentication | Confidentiality, integrity, or availability loss | Must fix before production or handoff |
| **High** | Requires some access but poses material risk | Material harm possible | Fix in Now actions (1–2 sprints) |
| **Medium** | Requires specific conditions | Limited scope | Fix in Next actions |
| **Low** | Edge case or defense-in-depth | Minimal direct harm | Backlog / Later |

---

## Confidence Levels

Every finding must carry a confidence level:
- **High:** Directly observed in source, config, or artifact review.
- **Medium:** Inferred from architectural patterns or design analysis.
- **Low:** Assumed based on absence of evidence or common risk patterns.

Low-confidence findings must include a note on what would be needed to confirm or refute them. Do not present Low-confidence findings as confirmed vulnerabilities.

---

## Finding Format

Use this format for every finding in the Vulnerability Inventory:

**SEC-XXX: [Short Title]**
- **Domain:** (from the six domains above)
- **Type:** (CWE reference if applicable)
- **Severity:** Critical / High / Medium / Low
- **Confidence:** High / Medium / Low
- **Affected Component:** (file, module, service, or area)
- **Status:** Confirmed / Suspected / Assumed
- **Evidence:** (what was observed; cite the source artifact and location)
- **Risk Narrative:** (realistic attack scenario and business impact — not worst-case speculation)
- **Remediation:** (specific, actionable steps; link to authoritative guidance if applicable)
- **Acceptance Criterion:** (how to verify the fix is effective)
- **Effort:** S / M / L / XL
- **Rollback Note:** (how to revert if the fix causes regression, for Critical and High only)

---

## Workflow

### Step 1 — Intake

- Read the Project Overview risk register and capability matrix.
- In Risk-Focused mode: identify which domains correspond to flagged findings and scope analysis to those.
- In Comprehensive mode: prepare to analyze all six domains.
- Note what source artifacts, configuration files, and infrastructure definitions are available.

### Step 2 — Domain Analysis

For each applicable domain, produce structured findings using the finding format above.

Do not produce generic findings that apply to every project (e.g., "update all dependencies" without specific CVE evidence). Every finding must be tied to observable evidence or a clearly stated assumption.

### Step 3 — Dependency Triage

- List dependencies from package manifests where accessible.
- Cross-reference against CVE databases.
- Score findings using the severity definitions above.
- Identify upgrade paths and flag blocked upgrades.

### Step 4 — Remediation Prioritization

- Group findings by severity: Critical → High → Medium → Low.
- Within each group, prioritize by: exploitability, breadth of impact, ease of remediation.
- Produce the remediation roadmap (Section 6 of the output contract).

### Step 5 — Gatekeeper and Planner Inputs

Produce the two bridge outputs (Sections 7 and 8) that allow this skill's findings to flow cleanly into the Readiness Gatekeeper's Gate G4 evaluation and the Action Planner's action backlog.

---

## Output Contract

Return results in this exact section order.

---

### 1. Security Assessment Summary

- Scope evaluated: which domains, which artifacts, which mode.
- Top 3 most critical findings (finding ID and one-sentence description each).
- Security maturity snapshot: brief characterization of the project's overall security posture.
- Confidence level for the assessment overall.
- What was not assessed and why.

---

### 2. Vulnerability Inventory

All findings in this format:

| ID | Title | Domain | Severity | Confidence | Component | Status |
|---|---|---|---|---|---|---|
| SEC-001 | (title) | (domain) | Critical/High/Med/Low | High/Med/Low | (component) | Confirmed/Suspected/Assumed |

Follow the table with full finding detail for every Critical and High finding (using the finding format from the Severity Definitions section). Medium and Low findings may use summary entries unless the builder requests full detail.

---

### 3. Dependency Risk Report

| Dependency | Version | CVE(s) | CVSS | Status | Upgrade Path | Blocked? |
|---|---|---|---|---|---|---|
| (name) | (current) | (CVE-XXXX-XXXX) | (score) | Patched in vX.X / Unresolved | (version / alternative) | Yes / No |

If package manifests were not accessible, state that explicitly and note the confidence impact.

---

### 4. Configuration and Infrastructure Findings

- Hardcoded secrets, default credentials, or overly permissive roles observed.
- Missing security headers or CORS misconfigurations.
- Container or IaC findings.
- Logging and observability gaps with security relevance.

Use finding format for Critical and High items.

---

### 5. Remediation Roadmap

| Priority | Finding ID | Objective | Effort | Acceptance Criterion | Dependencies |
|---|---|---|---|---|---|
| Now (Critical) | | | | | |
| Next (High) | | | | | |
| Later (Medium/Low) | | | | | |

All Critical findings must appear in Now. All High findings must appear in Next. Do not defer Critical or High findings to Later.

---

### 6. Hardening Recommendations

Recommendations that go beyond fixing specific findings — structural improvements to the security posture. Include only recommendations that are specific to this project's architecture and risk profile. Omit generic advice that applies to every project.

---

### 7. Gatekeeper Input: Gate G4 Evidence

This section is specifically formatted for the Readiness Gatekeeper's Gate G4 evaluation (Critical Risks Addressed).

For each Critical finding:
- Finding ID and title.
- Mitigation status: Mitigated / Accepted with rationale / Open.
- If Open: why no mitigation exists yet and what is required to close it.

Gate G4 passes only if every Critical finding is either Mitigated or Accepted with a documented rationale. If any Critical finding is Open, state that Gate G4 fails.

---

### 8. Action Planner Input: Security Actions

This section provides ready-to-import action entries for the Project Action Planner.

For each Critical and High finding, provide:
- Suggested action title.
- Priority: Now (Critical) or Next (High).
- Effort: S / M / L / XL.
- Owner profile.
- Acceptance criterion (same as finding acceptance criterion).
- Dependency on other security actions (if any).

---

### 9. Assumptions and Unknowns

- What could not be assessed due to access limitations.
- Findings that are Low-confidence and require confirmation.
- Recommended follow-up activities (e.g., penetration test, formal SAST scan, dependency audit).

---

## Quality Rules

- Every finding must cite evidence. Do not present assumed findings as confirmed.
- Severity must reflect actual exploitability and impact — not worst-case hypotheticals.
- Remediation must be specific and actionable. "Improve security" is not a remediation.
- Produce the Gatekeeper and Planner bridge outputs (Sections 7 and 8) in every run. These are not optional.
- Do not produce generic findings that apply equally to all projects. Every finding must be tied to an observed characteristic of this project.

---

## Constraints

- This skill performs structured analysis from available artifacts. It is not a penetration test.
- Access limitations reduce confidence and must be explicitly stated.
- Compliance interpretation (GDPR, HIPAA, PCI-DSS) is indicative only. Engage a qualified compliance professional for regulatory decisions.

---

## Prompt Starter

```
Run the Security Review skill in [Risk-Focused / Comprehensive / Remediation] mode
using the attached Project Overview artifact.
Produce the full output contract in section order.
Explicitly mark confidence levels for all findings.
Produce the Gatekeeper Gate G4 input and Action Planner security action entries.
```
