# Inventory Windows Evidence Acceptance Design

**Status:** Partially implemented (2026-07-06). Windows evidence ingestion and the
Windows collector now exist; this document is retained as the design record. See
"Implementation status" below for what shipped versus what remains future work.

## 1) Purpose

This document defined a future inventory acceptance model for normalized Windows
evidence in `inventory-service`. The runtime ingestion path described here has
since been implemented (see "Implementation status").

## Implementation status (2026-07-06)

Implemented:
- Windows runtime ingestion — `POST /scans/ingest/windows` (inventory-service)
  maps a raw Windows evidence document to the standard ingest contract
  (`source=host`), persists a scan snapshot + asset, and auto-scores it. Adapter:
  `services/inventory-service/app/windows_evidence.py`.
- Aggregate-only normalized signal set carried on the stored scan at
  `crypto_evidence.windows_normalized_signals`.
- Gateway proxy — `POST /api/scans/windows` (api-gateway).
- Windows collector — `agents/windows-host-agent/collect.ps1` (with `-Ingest`),
  wired into `scripts/run_flow.ps1 -WindowsEvidence`.

Also implemented:
- Windows-aware risk shaping in the inventory `risk_mapper` — the persisted
  signals raise `blast_radius`/`dependency_count` (domain role) and
  `migration_difficulty` (certificate volume + weak/expired), bounded to [0,5].

Still future work:
- AD / certificate-estate scanner.
- Windows-specific logic *inside* `risk-engine` / `planner-service` themselves
  (today the shaping happens in the inventory payload builder, not the scoring/
  planning services' internals).

## 2) Current state (original design-time snapshot)

- `inventory-service` already accepts enriched Linux and network evidence patterns used by existing Stage 1/Stage 2 flows.
- A Windows evidence fixture contract exists (`docs/windows-evidence-fixture-contract.md`).
- Windows fixture validation tests exist (`services/inventory-service/tests/test_windows_evidence_fixture_contract.py`).
- Windows runtime ingestion — **now implemented** (see "Implementation status").
- Windows agent — **now implemented** (`agents/windows-host-agent/collect.ps1`).
- AD scanner is not implemented.

## 3) Non-goals

This task explicitly excludes:

- no runtime ingestion implementation
- no Windows agent
- no AD scanner
- no credential collection
- no private key handling
- no production endpoint deployment
- no schema migration in this task
- no risk/planning runtime change

## 4) Acceptance principles

Future Windows evidence acceptance should follow these principles:

- backward compatibility with current Stage 1/2 fixtures
- tolerant optional Windows evidence block
- fail-closed validation for malformed structures
- no required Windows evidence for existing Linux/network assets
- normalized platform-aware fields
- warnings/errors preserved
- sensitive fields rejected or ignored safely

## 5) Proposed input shape

Future input model (conceptual):

- asset metadata includes `platform="windows"`
- optional `windows_evidence` block is accepted when platform is Windows
- optional `warnings` and `errors` arrays are accepted as structured diagnostics
- no raw hostnames/domains/IPs by default
- redaction flags are required when sensitive identifiers are omitted

Illustrative (non-binding) structure:

```json
{
  "asset": {
    "asset_id": "...",
    "platform": "windows",
    "asset_type": "workstation|server"
  },
  "windows_evidence": {
    "evidence_version": "v1",
    "os_metadata": {},
    "software_inventory": {},
    "certificate_store_indicators": {},
    "service_indicators": {},
    "domain_membership_indicators": {},
    "machine_role_indicators": {},
    "redaction": {
      "hostname_redacted": true,
      "package_names_redacted": true,
      "domain_name_redacted": true
    },
    "private_keys_exported": false
  },
  "warnings": [],
  "errors": []
}
```

## 6) Proposed normalized inventory representation

Future internal representation should remain conceptual in this design and not change schema in this task.

Proposed normalized fields:

- `asset_id`
- `platform`
- `asset_type`
- `evidence_version`
- `os_metadata` summary
- `software_inventory_summary`
- `certificate_store_indicators`
- `service_indicators`
- `domain_membership_indicators`
- `machine_role_indicators`
- `warnings`
- `errors`

No actual schema or runtime model changes are introduced by this document.

## 7) Validation rules

Future validation should enforce:

- `asset.platform` must be `windows`
- `hostname_redacted` must be `true` if hostname is omitted
- `package_names_redacted` must be `true` if raw package names are omitted
- `private_keys_exported` must be `false`
- `domain_name_redacted` must be `true` if domain joined
- `warnings`/`errors` must be arrays
- forbidden sensitive fields must be rejected:
  - `password`
  - `secret`
  - `token`
  - `private_key`
  - `credential`
  - `raw_hostname`
  - `raw_domain`
  - `raw_ip`

## 8) Compatibility with existing services

- `inventory-service` should accept future Windows evidence without changing existing Linux evidence behavior.
- `risk-engine` should consume normalized signals only.
- `planner-service` should consume normalized signals only.
- graph projection should not assume Linux-only evidence as Windows acceptance is added later.

## 9) Phased implementation (progress)

- **Phase 0** — keep fixture contract tests passing. ✅ done
- **Phase 1** — add inventory schema/validator tests only. ✅ done
- **Phase 2** — add inventory ingestion acceptance for Windows fixture. ✅ done (`POST /scans/ingest/windows` + adapter + tests)
- **Phase 3** — add Stage 2-style Windows inventory smoke. ✅ done (`scripts/run_windows_evidence_smoke.ps1` — fixture-driven assertions; `run_flow.ps1 -WindowsEvidence` covers the live host)
- **Phase 4** — add risk/planning signal mapping tests. 🟨 signals now shape the risk payload in the inventory `risk_mapper` (with tests); dedicated logic inside risk-engine/planner internals still open
- **Phase 5** — minimal Windows collector. ✅ done (`agents/windows-host-agent/collect.ps1`)

## 10) Stop conditions

Stop implementation work if any of the following occur:

- Windows ingestion breaks existing Linux fixtures
- raw identifiers are required
- secrets/private keys are collected
- AD details require credentials
- risk/planning starts consuming platform-specific raw details
- broad schema migration is required

## 11) Status wording

Inventory Windows Evidence Acceptance Design — partially implemented (2026-07-06):
ingestion + collector shipped; AD scanner and Windows-specific risk/planning
mapping remain future work.
