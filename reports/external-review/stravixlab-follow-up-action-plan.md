# StravixLab External Review Follow-up Action Plan

UTC timestamp: 2026-05-17T00:00:00Z

## Purpose

Record and track follow-up actions from the 2026-05-17 StravixLab external review result.

## Review Result Summary

- Reviewing organization: StravixLab
- Reviewer: Dimitar Parashkevov, Founder
- Decision: ACCEPTED WITH LIMITATIONS
- TRL6 readiness validation: PASS
- Demo bundle smoke: PASS
- Relevant-environment demo observed: yes
- TRL 6 achieved: not claimed
- Production readiness: not claimed

## Action Items

| action_id | issue | category | priority | recommended fix | target file(s) | status |
| --- | --- | --- | --- | --- | --- | --- |
| SRX-001 | Ubuntu 24.04 environment had `python3` but no `python` symlink | Documentation / Environment prerequisites | High | Document `python-is-python3` or explicit `python3` prerequisite and command usage expectations for review and demo scripts | `reports/trl6/relevant-environment-demo-run-instructions.md`, `README.md` | OPEN |
| SRX-002 | `pytest` prerequisite was missing or not explicit | Documentation / Validation prerequisites | High | Add explicit `pytest` setup requirement for operator/review and validation flows | `reports/trl6/relevant-environment-demo-run-instructions.md`, `README.md`, `docs/operator-validation-checklist.md` | OPEN |
| SRX-003 | `known-limitations.md` quality/scope partitioning issue | Documentation quality / Evidence clarity | Medium | Split and expand limitations into operational limitations vs broader scope limitations with clear ownership and evidence context | `reports/trl6/known-limitations.md` (and any new limitations companion file if introduced) | OPEN |
| SRX-004 | Demo bundle `status_hint` false positive marks known limitations as FAIL due to keyword matching | Reporting logic / Demo bundle interpretation | High | Refine known-limitations status_hint logic to avoid keyword-only FAIL misclassification | `scripts/run_trl6_demo_bundle.sh`, `reports/trl6/demo-bundle/trl6-demo-bundle-index.md` generation logic | OPEN |
| SRX-005 | Operator/review records did not explicitly reference StravixLab accepted-with-limitations outcome | Review traceability / Governance records | Medium | Update operator review and relevant-environment summary records with external review reference and conservative claim language | `reports/trl6/operator-review-execution-record.md`, `reports/trl6/relevant-environment-demo-execution-summary.md`, `reports/trl6/trl6-claim-review-readiness-checklist.md` | OPEN |

## Required Follow-up Actions

A. Document `python-is-python3` / `python3` prerequisite.
B. Document `pytest` prerequisite.
C. Split/expand known limitations into operational vs scope limitations.
D. Fix known-limitations `status_hint` false positive in TRL6 demo bundle logic.
E. Update operator/review records to reference StravixLab accepted-with-limitations result.

## Boundary

This action plan records external review follow-up only and does not claim TRL 6 achieved or production readiness.
