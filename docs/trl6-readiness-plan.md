# TRL 6 Readiness Plan

**Status wording (required):**

**TRL 6 Readiness Plan — docs-only; TRL 6 not yet claimed.**

## 1) Purpose

This document defines the path toward TRL 6 validation for QRP.

It is a planning/validation design document and does **not** claim TRL 6 has been achieved.

## 2) Current baseline

QRP has progressed to a TRL 5 candidate baseline with the following implemented evidence tracks:

- Stage 1 core stabilization
- Stage 2 enriched evidence
- Stage 3 risk/planning improvements
- JSON dependency graph projection
- Minimal read-only Graph API over a local JSON snapshot
- Graph Snapshot Loader helper and smoke validation
- Copilot disabled-safe preparation
- Windows/cross-platform evidence contracts
- Evidence Pack Index generation
- repeatable local smoke/test reports

## 3) TRL 6 target wording

Use careful future wording only:

- **"TRL 6 candidate"**: allowed only after the TRL 6 validation package is prepared.
- **"TRL 6 demonstrated in a relevant environment"**: allowed only after successful relevant-environment demo execution.

Do not use wording that implies TRL 6 is currently achieved.

## 4) Relevant environment definition

For QRP, a **relevant environment** means a local/on-prem lab environment that resembles SME infrastructure and includes all of the following:

- at least one Linux host evidence source
- at least one TLS/network endpoint evidence source
- inventory ingest path
- risk scoring path
- planning output path
- graph snapshot projection path
- read-only Graph API access over snapshot
- evidence pack generation
- operator review workflow

## 5) TRL 6 validation scenario

Scenario name:

**Quantum readiness assessment for a small enterprise infrastructure.**

Scenario flow:

1. collect host evidence
2. collect network/TLS evidence
3. ingest evidence
4. produce inventory
5. score risk
6. produce migration/planning waves
7. project graph snapshot
8. inspect graph through read-only API
9. generate evidence pack
10. operator reviews report and checklist

## 6) Acceptance criteria (PASS/FAIL)

A validation run is PASS only when all required checks pass:

- all required services start
- health checks pass
- evidence ingest succeeds
- risk output contains confidence and risk dimensions
- planner output contains waves and priority reasons
- graph snapshot validates
- read-only Graph API endpoints respond
- evidence pack index is generated
- no external LLM required
- no graph DB required
- no production secrets collected
- no autonomous remediation executed

Any failed required check is FAIL.

## 7) Required validation artifacts

The TRL 6 track should produce/maintain these artifacts:

- `reports/trl6/trl6-readiness-report.md`
- `reports/trl6/evidence/`
- `reports/trl6/operator-demo-checklist.md`
- `reports/trl6/known-limitations.md`
- `reports/evidence-pack/evidence-pack-index.md`

## 8) Demo script design (future)

Planned script:

- `scripts/run_trl6_readiness_validation.sh`

Design requirements:

- run from repository root
- perform preflight checks
- run existing service validation/smoke commands
- run graph API smoke
- run evidence pack index generation
- generate one TRL6 readiness report
- not require external internet
- not require external LLM
- not require graph DB
- not perform remediation

This script is intentionally **not implemented** in this task.

## 9) Operator workflow

1. start required services
2. run TRL 6 readiness validation flow
3. inspect generated reports
4. review graph API output
5. review risk/planning output
6. sign/check operator checklist

## 10) Evidence quality requirements

TRL 6 track evidence must be:

- deterministic
- repeatable
- local-first
- free of secrets/private keys
- timestamped in reports
- clear PASS/FAIL at check level
- accompanied by known limitations

## 11) Current gaps before TRL 6 claim

Do not claim TRL 6 until these gaps are addressed via demo evidence:

- no real customer/on-prem pilot executed yet
- no independent operator validation yet
- no production deployment hardening
- no auth/RBAC
- no Windows agent implementation
- no real Copilot provider implementation
- no graph DB/traversal/blast-radius engine
- limited relevant-environment evidence until demo run is completed

## 12) Stop rules

Stop and escalate scope control if any of the following occurs:

- someone claims TRL 6 achieved before demo execution
- production readiness is claimed
- external LLM becomes required
- graph DB becomes required
- remediation/autonomous execution is introduced
- secrets/private keys are collected

## 13) Recommended next steps

A. Add TRL 6 readiness validation script

B. Add operator demo checklist

C. Add TRL 6 report template

D. Run relevant-environment demo in lab

Recommended default:

**A. Add TRL 6 readiness validation script**

## 14) Status wording

Use exactly this line in status contexts for this document:

**TRL 6 Readiness Plan — docs-only; TRL 6 not yet claimed.**
