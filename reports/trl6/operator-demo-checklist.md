# Operator Demo Checklist (TRL 6 Readiness Package)

Use this checklist to perform a structured operator review of the TRL 6 readiness evidence package.

> This checklist supports TRL 6 readiness package review only. It does not, by itself, claim TRL 6 achieved.

## 1) Demo Environment Details

- [ ] Environment name: `______________________________`
- [ ] Date/time (UTC): `______________________________`
- [ ] Operator name: `______________________________`
- [ ] Organization: `______________________________`
- [ ] Repository commit (SHA): `______________________________`
- [ ] Validation command run: `bash scripts/run_trl6_readiness_validation.sh`

## 2) Preflight Confirmation

- [ ] Services were started through `scripts/start_all.sh`
- [ ] Service status was checked through `scripts/status_all.sh`
- [ ] No external LLM is required for this validation package
- [ ] No graph DB is required for this validation package
- [ ] No autonomous remediation was executed during this review

## 3) Validation Evidence Reviewed

- [ ] `reports/trl6/trl6-readiness-report.md`
- [ ] `reports/evidence-pack/evidence-pack-index.md`
- [ ] `reports/trl-validation-report.md`
- [ ] `reports/stage2-inventory-smoke-report.md`
- [ ] `reports/stage2-e2e-smoke-report.md`
- [ ] `reports/stage3-risk-planning-smoke-report.md`
- [ ] `reports/graph/latest/graph-api-readonly-smoke-report.md`
- [ ] `reports/copilot/safety-contract-smoke-report.md`

## 4) Functional Review Checklist

- [ ] Evidence ingest behavior reviewed
- [ ] Risk scoring outputs reviewed
- [ ] Planning wave outputs reviewed
- [ ] Graph snapshot outputs reviewed
- [ ] Read-only Graph API behavior reviewed
- [ ] Copilot disabled-safe behavior reviewed
- [ ] Known limitations reviewed (`reports/trl6/known-limitations.md`)

## 5) Safety Boundary Review

- [ ] No production readiness claim is made
- [ ] No TRL 6 achieved claim is made without operator sign-off
- [ ] No external LLM dependency is required
- [ ] No graph DB/Neo4j implementation is required
- [ ] No Windows agent implementation is required
- [ ] No autonomous remediation is executed

## 6) Operator Decision

Select one:

- [ ] Accepted for TRL6 readiness evidence package
- [ ] Accepted with limitations (document below)
- [ ] Rejected / requires rework

Decision notes:

```
________________________________________________________________________
________________________________________________________________________
________________________________________________________________________
```

## 7) Sign-off Block

- Operator name: `______________________________`
- Role: `______________________________`
- Date: `______________________________`
- Signature / initials: `______________________________`
- Notes:

```
________________________________________________________________________
________________________________________________________________________
________________________________________________________________________
```
