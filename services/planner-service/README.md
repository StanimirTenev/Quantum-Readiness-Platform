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

## Windows Host Signal Prioritization

- Planner reads the aggregate Windows flags the risk-engine surfaces in `risk.rationale`.
- High-priority signals: `windows_domain_controller`, `windows_expired_certificates`, `windows_weak_signature_certificates` (raise priority and cap the item no later than wave 2).
- Medium-priority signal: `windows_large_certificate_estate`.
- Reasons are surfaced in `planning_reasons`; absent Windows flags leave planning unchanged.

## Stage 3 Priority Score and Wave Rationale

- Planner now returns `priority_score` (0-100) on each plan item, while keeping existing score fields for backward compatibility.
- `priority_score` starts from `normalized_score_100`, falls back to `final_score` or `score`, and defaults to 0 when missing.
- Optional `risk_dimensions` influence priority deterministically:
  - urgency contributes up to +10 (`urgency * 0.10`)
  - exposure contributes up to +5 (`exposure * 0.05`)
  - impact contributes up to +5 (`impact * 0.05`)
- Optional `confidence_score` adjusts priority slightly:
  - `>= 80` adds +5
  - `< 50` subtracts 5
- Stage 2 wave caps are retained: `weak_public_key_detected` and `private_key_files_detected` are never planned later than wave 2.
- `certificate_chain_available` remains informational and does not increase priority by itself.
- Missing `risk_dimensions`, `confidence_score`, or `stage2_signals` fields are non-fatal and preserve compatible planning behavior.
- This is conservative wave-based prioritization and is not dependency graph planning.
