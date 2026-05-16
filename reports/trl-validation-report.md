# TRL Validation Report

## Validation Date
2026-05-16T03:59:54.699382+00:00

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
- scan_id: 26b8f837-ade9-4afd-a17a-097ae1f5dd68
- created assets: 1
- asset_ids: fd139177-2868-48f5-bcab-14c9cdf20070

## Risk Result
- total risk records: 2
- sample asset: api.example.internal:443
- normalized score: 73.0
- rating: high

## Policy Decision
- asset: api.example.internal:443
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

## API Gateway Policy Forwarding
- endpoint: http://127.0.0.1:8000/api/policies/evaluate
- decision: deny
- rule_id: pqc-readiness-gate-v1
- result: PASS

## Evidence Artifacts
| Artifact | Path |
|---|---|
| Host evidence | reports/evidence/latest/host-evidence.json |
| Network evidence | reports/evidence/latest/network-evidence.json |
| Inventory ingest response | reports/evidence/latest/inventory-ingest-response.json |
| Assets | reports/evidence/latest/assets.json |
| Risks | reports/evidence/latest/risks.json |
| Policy decision | reports/evidence/latest/policy-decision.json |
| API Gateway policy decision | reports/evidence/latest/api-gateway-policy-decision.json |
| Plan | reports/evidence/latest/plan.json |
| Waves | reports/evidence/latest/waves.json |
| Workflow export | reports/evidence/latest/workflow-export.json |

## TRL Assessment
Current technical maturity:
TRL 4 -> TRL 5 candidate

Reason:
The system demonstrates a repeatable local validation flow across discovery evidence, inventory, risk, policy, planning and workflow.

Remaining gaps before claiming stronger TRL 5:
- run against real infrastructure sample
- preserve evidence artifacts across timestamped runs
- add failure/retry handling
- external evaluator review

## Result
Result: PASS
