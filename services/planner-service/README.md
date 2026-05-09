# Planner Service

## What this service does
- Builds wave-based remediation plans from inventory and risk data.

## Current role in the prototype
- Working prototype planning service with task export into workflow.

## Main endpoints or functions
- `GET /health`, `GET /plan`, `GET /waves`
- `POST /export-tasks`

## Inputs / outputs
- Input: inventory/risk data from upstream services and export options (`waves`, `auto_submit`).
- Output: JSON plan summaries and created workflow task payloads.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/planner-service/tests`

## Known limitations
- Planning logic is deterministic and rule-based; scenario customization is limited.


## Stage 2 Risk Signal Prioritization

- Planner reads optional `stage2_signals.evidence_signals` from risk items.
- High-priority signals: `private_key_files_detected`, `weak_public_key_detected`, `expiring_certificate_detected`.
- Medium-priority signals: `certificate_files_detected`, `tls_config_detected`, `ssh_config_detected`, `tls_detected`, `crypto_packages_detected`.
- Informational signal: `certificate_chain_available` (does not increase priority by itself).
- Missing or partial Stage 2 signals are non-fatal and preserve backward-compatible planning behavior for old inputs.
- This is conservative wave prioritization only and is not dependency graph planning.
