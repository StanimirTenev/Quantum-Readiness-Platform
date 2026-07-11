# Inventory Service

## What this service does
- Stores assets, ingested scan events, related risk records, and (see below) a lightweight
  workspace/report model tying them together.

## Workspace model (lightweight, not multi-tenancy)
- A workspace groups "this is scan run X" (its scans), "these are findings from it" (their
  risk records), and "this is a report tied to it" (persisted reports) -- just logical
  grouping, no auth/tenancy semantics.
- Hybrid creation: `POST /workspaces` (optional `{"source": "..."}`) creates one explicitly --
  pass its `id` as `?workspace_id=` on subsequent `/scans/ingest` calls to group multiple scans
  under it. If a caller omits `workspace_id`, a new single-scan workspace is auto-created
  transparently (`source` = the scan's own source) -- every scan always belongs to some
  workspace, and no existing caller needs to change.
- `GET /workspaces/{id}` returns a rollup: `{workspace, scans, risks, reports}`.
- `POST /workspaces/{id}/reports` (optional `{"report_type": "..."}`, defaults to `"operator"`)
  builds an operator report (`tools/report/build_operator_report`, the same logic
  `scripts/run_product_demo.sh` and `run_report.sh` use) from the workspace's own scans/risks
  -- one highest-scoring risk record per asset name -- and persists it. Includes an executive
  summary, migration wave table, vendor blocker table, evidence table, per-asset change
  checklist, findings/attribution tables, a technical appendix (raw risk-engine rationale
  flags per asset), and methodology/boundaries -- see `tools/report/build_operator_report.py`.
  `GET /reports/{report_id}` fetches it back; `GET /reports?workspace_id=` lists/filters.
- An asset's `workspace_id` records which workspace *first discovered* it (set once, at
  creation, like `created_at`); reusing an existing asset (matched by name+type) in a later
  workspace's scan does not move it -- an asset can legitimately be touched by scans in
  multiple workspaces over time.
- Wired end to end: `scripts/run_product_demo.sh` creates one workspace and groups all three
  of its agent scans under it, then persists its operator report via
  `POST /workspaces/{id}/reports` instead of building one ad hoc; the linux-host-agent,
  network-scanner, and repo-ci-scanner CLIs all take a `-workspace-id`/`--workspace-id` flag;
  the web-ui's "Load Demo" creates a workspace (only when there's actually something new to
  ingest, so idempotent re-clicks don't leave empty ones behind) and the Dashboard/Reports tabs
  show it and can generate its persisted report. Every existing caller that doesn't pass
  `workspace_id` still works unchanged via the auto-workspace fallback.

## Stage 2 enriched evidence ingest
- `POST /scans/ingest` now accepts optional Stage 2 enriched evidence blocks while remaining backward compatible with existing Stage 1 payloads.
- Optional blocks accepted:
  - `crypto_evidence.package_metadata`
  - `crypto_evidence.cert_indicators.certificate_file_indicators`
  - `crypto_evidence.cert_indicators.config_file_indicators`
  - `tls_metadata` (accepted as alias of `tls_evidence`)
  - `tls_metadata.certificate_chain`
- Minimal validation behavior:
  - missing optional Stage 2 blocks do not fail ingest
  - obvious invalid shapes are rejected (for example non-numeric `tls_metadata.port`, non-array `package_metadata.packages`, non-array `certificate_chain.certificates`)
  - safe defaults are applied when practical (`packages/files/errors/searched_paths/certificates -> []`)
- `tls_metadata.certificate.key.size_bits` (Stage 2 structured form) normalizes into the flat
  `public_key_size` field risk-engine reads (fixed 2026-07-08 — was silently dropped before,
  so `weak_public_key_detected` could never fire from a real Stage-2-shaped network scan).
- `tls_metadata.collected` is inferred `true` when a `certificate` block is present but no
  explicit `collected` flag was sent (fixed 2026-07-08, same date/reason as above).
- `ssh_metadata` (alias `ssh_evidence`) is also accepted and persisted, as emitted by
  `network-scanner`'s SSH scan mode (`-protocol ssh`) -- server banner, offered
  kex/host-key/encryption/MAC algorithm lists. Deliberately permissive (`extra="allow"`, no
  rigid schema). Forwarded to risk-engine on ingest (`risk_mapper.py`), which derives
  `weak_ssh_kex_detected`/`legacy_ssh_host_key_detected`/`weak_ssh_cipher_detected`/
  `weak_ssh_mac_detected` from it -- see `services/risk-engine/README.md`.
- `crypto_evidence.repo_scan.embedded_key_findings` (repo-ci-scanner's IaC embedded-key
  detection) is likewise forwarded as part of `crypto_evidence` and drives risk-engine's
  `embedded_private_key_in_repo_detected` signal.
- `ipsec_metadata` (alias `ipsec_evidence`) is also accepted and persisted, as emitted by
  `network-scanner`'s IKEv2 scan mode (`-protocol ipsec`) -- selected encryption/PRF/
  integrity/DH-group, or the rejection reason. Deliberately permissive (`extra="allow"`, no
  rigid schema), same as `ssh_metadata`. Forwarded to risk-engine on ingest
  (`risk_mapper.py`), which derives `legacy_ipsec_dh_group_detected`/
  `weak_ipsec_encryption_detected`/`weak_ipsec_integrity_detected`/`weak_ipsec_prf_detected`
  from it -- see `services/risk-engine/README.md`.
- `crypto_evidence.ad_evidence` (AD/Certificate Services estate evidence -- see
  `docs/ad-certificate-estate-design.md`; fixture-only for now, no live collector) is likewise
  forwarded as part of `crypto_evidence` and drives risk-engine's
  `ad_weak_certificate_template_detected`/`ad_ca_certificate_expiring_detected`/
  `ad_large_certificate_estate_detected` signals. Sample ingest payload:
  `services/inventory-service/tests/fixtures/stage2_evidence/ad_certificate_estate_ingest.json`.

### Sample ingest payload snippet
```json
{
  "source": "network",
  "assets": [{"asset_type": "endpoint", "name": "example.com:443"}],
  "tls_metadata": {
    "target": "example.com",
    "port": 443,
    "protocol_version": "TLS 1.3",
    "certificate_chain": {
      "available": true,
      "certificates": []
    }
  }
}
```

## Windows host evidence ingest
- `POST /scans/ingest/windows` accepts a raw Windows host evidence document (as
  emitted by `agents/windows-host-agent/collect.ps1`) and persists it as durable
  inventory. The redacted/aggregate document is mapped to the standard ingest
  contract (`source` is fixed to `host`), a representative quantum-vulnerable
  certificate is chosen from the safe crypto surface to drive scoring, and the
  scan is persisted and auto-scored like any other ingest.
- The aggregate-only normalized signals are carried on the stored scan at
  `crypto_evidence.windows_normalized_signals` (no raw identifiers or secrets).
- The mapping adapter lives in `app/windows_evidence.py`.

## Database location
- Defaults to the service-local `inventory.db`. Set `INVENTORY_DB_PATH` to point
  the store at another file (used by `scripts/run_flow.ps1` for an isolated,
  repeatable demo database).
- Set `DATABASE_URL` (a `postgresql://` connection string) to use PostgreSQL instead --
  takes priority over `INVENTORY_DB_PATH` when both are set. Used by
  `infra/docker/docker-compose.yml` so the deployed product runs on Postgres (concurrent
  writes, not SQLite's single-writer file lock); bare-metal dev/tests/CI stay on SQLite by
  default (no `DATABASE_URL`, no Postgres server needed). Both backends run the exact same
  queries via `tools/db_compat.py` -- no ORM, no ongoing dual-query maintenance.

## Asset risk history
- `GET /assets/{asset_id}/history` returns the asset's risk trend across all
  persisted scans (one point per risk result, oldest first), with `first_score`,
  `latest_score`, and a `trend` of `improving` / `worsening` / `flat` /
  `insufficient_data`. Lower normalized score means lower risk, so a host whose
  posture improves between collections reports `improving`. This is the payoff of
  persistence: a repeated host collection (e.g. `collect.ps1 -Ingest`) accumulates
  scans while the asset stays single, so the trend reflects change over time.

## Main endpoints or functions
- `GET /health`
- `GET/POST/PUT/DELETE /assets` and `/assets/{asset_id}`
- `GET /assets/{asset_id}/history`
- `POST /scans/ingest` (accepts `?workspace_id=`), `POST /scans/ingest/windows`, `GET /scans`, `GET /scans/{scan_id}`
- `GET /risks`, `POST /admin/cleanup-assets`
- `POST /workspaces`, `GET /workspaces`, `GET /workspaces/{workspace_id}`
- `POST /workspaces/{workspace_id}/reports`, `GET /reports/{report_id}`, `GET /reports`

## How to run tests
- `pytest services/inventory-service/tests`


## Stage 2 Evidence Fixtures
- `minimal_ingest.json`: smallest Stage 1-compatible ingest payload used as the baseline success case.
- `host_enriched_ingest.json`: host ingest payload with Stage 2 `crypto_evidence.package_metadata` plus certificate/config file indicator blocks.
- `network_enriched_ingest.json`: network ingest payload with Stage 2 `tls_metadata`, including `certificate` and `certificate_chain.certificates`.
- `invalid_tls_metadata.json`: negative-test fixture with intentionally invalid `tls_metadata.port` shape.
- `invalid_package_metadata.json`: negative-test fixture with intentionally invalid `crypto_evidence.package_metadata.packages` shape.


## Stage 2 Inventory Smoke Validation

Run:

```bash
bash scripts/run_stage2_inventory_smoke.sh
```

Precondition:
- inventory-service is running locally on port 8001.

Output:
- `reports/stage2-inventory-smoke-report.md`
