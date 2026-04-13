# Core Flow Contract (Stage 1)

Canonical version: `stage1-v1`.

This document freezes the active Stage 1 contract for the deterministic core flow:

`evidence -> inventory -> risk -> planning -> workflow -> dashboard`

## Real logic vs placeholder (explicit)

| Stage | Canonical entity | Status in Stage 1 | Notes |
|---|---|---|---|
| evidence | `ScanIngestRequest` evidence blocks (`host_inventory`, `crypto_evidence`, `tls_evidence`) | `real_logic` | Ingested and persisted by inventory-service scans table. |
| inventory | `Asset`, `ScanRecord` | `real_logic` | CRUD + scan ingestion + dedup behavior are running. |
| risk | `RiskEngine /score` with `contract_version`, `asset_name`, `dependency_count`, `vendor_blocked` | `real_logic` | Deterministic weighted scoring is active and returned to inventory-service. |
| planning | `build_plan` wave output | `real_logic` | Risk-driven wave grouping and priority boost are active. |
| workflow | `/export-tasks` integration | `placeholder` | Planner forwards tasks but lifecycle semantics are still basic. |
| dashboard | planner/inventory derived outputs | `placeholder` | Data is consumable but deep UX/semantic mapping remains partial. |

## Contract boundaries frozen in this increment

1. `inventory-service -> risk-engine` sends `stage1-v1` request payload with deterministic fields.
2. `risk-engine -> inventory-service` returns `stage1-v1` response including dependency/vendor blocker context.
3. `inventory-service /risks -> planner-service` exposes stable risk records with contract metadata and planning fields.

## Source of truth

Machine-readable schema for this contract lives in:

- `shared/schemas/core-flow.contract.json`
