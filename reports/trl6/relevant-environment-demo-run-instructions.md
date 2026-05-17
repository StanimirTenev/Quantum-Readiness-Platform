# Relevant-Environment Demo Run Instructions

UTC timestamp: 2026-05-17T00:00:00Z

## Purpose

This instruction sheet defines how to run and record the real relevant-environment demo for TRL6 review evidence.

## Safety and claim boundaries

- TRL 6 achieved: not claimed
- Production readiness: not claimed
- Do not fabricate reviewer name/signature
- Do not fabricate demo execution evidence
- This instruction sheet does not claim TRL 6 achieved or production readiness

## Preconditions

- A named operator/reviewer is assigned.
- A relevant environment is selected (local lab / on-prem SME-like lab / customer pilot).
- Required artifacts are available for review.

## Required artifacts

- `reports/trl6/trl6-readiness-report.md`
- `reports/trl6/operator-review-execution-record.md`
- `reports/trl6/relevant-environment-demo-evidence.md`
- `reports/trl6/relevant-environment-demo-execution-summary.md`
- `reports/trl6/operator-demo-checklist.md`
- `reports/trl6/known-limitations.md`
- `reports/trl6/demo-bundle/trl6-demo-bundle-index.md`
- `reports/trl6/demo-bundle/trl6-demo-bundle-smoke-report.md`
- `reports/external-review/partner-handoff-pack.md`

## Run procedure

1. Record demo metadata (date/time, environment name/type, commit SHA, named operator/reviewer).
2. Execute the local TRL6 readiness validation command and capture output.
3. Review known limitations with the operator/reviewer.
4. Review demo bundle index and smoke report.
5. Complete the operator checklist and evidence record.
6. Record outcome as PASS / PASS WITH LIMITATIONS / FAIL in evidence artifacts.
7. Attach named sign-off only after real observed execution.

## Completion gate

Demo status remains pending until real execution evidence and named sign-off are attached.

## Next step

After completion, run a separate claim review using `reports/trl6/trl6-claim-review-readiness-checklist.md`.
