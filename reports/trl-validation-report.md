# TRL Validation Report

## Validation Date
2026-05-08T10:06:39.913164+00:00

## Validation Scope
- inventory ingest
- risk scoring
- policy evaluation
- planning
- workflow task export

## Services Checked
| Service | Endpoint | Status |
|---|---|---|
| inventory-service | http://127.0.0.1:8001/health | UP |
| risk-engine | http://127.0.0.1:8002/health | UP |
| planner-service | http://127.0.0.1:8004/health | UP |
| workflow-service | http://127.0.0.1:8005/health | UP |
| policy-engine | http://127.0.0.1:8007/health | UP |
| api-gateway | http://127.0.0.1:8000/health | UP |

## Evidence Ingest Result
- scan_id: 05e167e9-4618-44c8-ac87-567c0defeb45
- created assets: 1
- asset_ids: aa59df7f-e23f-472d-8f6a-f05b1734e074

## Risk Result
- total risk records: 2
- sample asset: payments.example.com:443
- normalized score: 74.0
- rating: high

## Policy Decision
- asset: payments.example.com:443
- decision: deny
- reasons: vendor_blocked
- rule_id: pqc-readiness-gate-v1
- rule_version: 1.0.0

## Planning Result
- wave_1 count: 2
- wave_2 count: 0
- wave_3 count: 0

## Workflow Result
- created task count: 2

## TRL Assessment
Current technical maturity:
TRL 4 -> TRL 5 candidate

Reason:
The system demonstrates a repeatable local validation flow across discovery evidence, inventory, risk, policy, planning and workflow.

Remaining gaps before claiming stronger TRL 5:
- run against real infrastructure sample
- preserve evidence artifacts
- add failure/retry handling
- add operator-facing validation checklist
- document environment assumptions

## Result
PASS
