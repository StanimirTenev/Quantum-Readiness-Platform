# Windows Risk/Planning Signal Mapping Design

## Status

Partially implemented (2026-07-06). The normalized aggregate signal set is now
produced and persisted; dedicated Windows mapping *inside* risk-engine/
planner-service is still future work. See "Current state" below.

## 1. Purpose

This document defines the mapping from normalized Windows evidence into safe,
aggregate risk/planning signals for downstream consumers. The signal-production
half is now implemented (see "Current state"); consumption inside
risk-engine/planner-service remains future work.

## 2. Current state

- Windows fixture contract exists.
- Windows inventory acceptance contract tests exist.
- Runtime Windows ingestion — **now implemented** (`POST /scans/ingest/windows`;
  adapter `services/inventory-service/app/windows_evidence.py`).
- The canonical aggregate signal set (`build_windows_normalized_signals`) is
  produced and persisted on the stored scan at
  `crypto_evidence.windows_normalized_signals`.
- Scoring currently reuses the generic `risk_mapper` path via a representative
  certificate; **dedicated Windows mapping inside risk-engine/planner-service is
  not yet implemented** — the persisted signals are not yet consumed as Windows
  risk/planning inputs.
- Downstream services should consume normalized aggregate signals only.

## 3. Non-goals

This design explicitly does **not** include:

- no risk-engine runtime change
- no planner-service runtime change
- no inventory runtime change
- no Windows agent
- no AD scanner
- no credential collection
- no private key handling
- no raw Windows identifiers in risk/planning inputs

## 4. Mapping principles

Future Windows mapping should follow these principles:

- aggregate-only signals
- no raw hostnames/domains/IPs
- no raw package names by default
- no certificate private material
- platform-aware but schema-stable signals
- conservative scoring
- backward compatibility with existing Linux/network evidence

## 5. Proposed normalized signal groups

Future normalized Windows evidence should be reduced into these logical groups:

- `windows_software_summary`
- `windows_certificate_store_summary`
- `windows_service_summary`
- `windows_domain_membership_summary`
- `windows_machine_role_summary`
- `windows_crypto_posture_summary`
- `windows_collection_quality_summary`

## 6. Example safe `normalized_signals` object

Fake aggregate example values only:

```json
{
  "platform": "windows",
  "asset_type": "endpoint",
  "software_total_observed": 42,
  "crypto_relevant_software_count": 3,
  "certificates_observed_count": 12,
  "expired_certificates_count": 1,
  "weak_signature_indicators_count": 0,
  "crypto_relevant_services_count": 2,
  "domain_joined": true,
  "ad_details_collected": false,
  "domain_controller_role_observed": false,
  "private_keys_exported": false,
  "warnings_count": 0,
  "errors_count": 0
}
```

## 7. Risk-engine future interpretation

Future risk interpretation should remain conservative and aggregate-driven:

- expired certificates increase exposure/urgency modestly
- weak signature indicators increase exposure
- domain controller role increases impact if observed
- `ad_details_collected=false` limits confidence rather than inflating risk
- `private_keys_exported` must remain false; if ever true, treat as critical safety violation
- missing/partial evidence lowers confidence

## 8. Planner-service future interpretation

Future planner interpretation should remain operator-safe:

- domain controller assets should be prioritized carefully
- expired certificate indicators may require earlier wave
- weak crypto indicators may require earlier wave
- partial evidence should trigger review task, not aggressive remediation
- no autonomous remediation

## 9. Compatibility requirements

- existing Linux/network Stage 2 signals must remain supported
- Windows signals must be optional
- absence of Windows evidence must not break existing scoring/planning
- risk/planning should not depend on raw Windows-specific details

## 10. Validation approach (progress)

- **Phase 0 — docs-only design** ✅ done
- **Phase 1 — tests-only normalized signal builder contract** ✅ done (now backed by the production `build_windows_normalized_signals` adapter + tests)
- **Phase 2 — risk-engine tests for aggregate Windows signals** 🔲 open
- **Phase 3 — planner-service tests for aggregate Windows signals** 🔲 open
- **Phase 4 — implementation behind conservative feature path** 🟨 ingestion/persistence shipped; dedicated risk/planner consumption still open
- **Phase 5 — smoke validation using fixture only** 🟨 live persist + read-back via `run_flow.ps1 -WindowsEvidence`

## 11. Stop conditions

Stop future implementation work if any of the following becomes required:

- raw identifiers are required
- private keys/secrets are requested
- AD credentials are required
- risk scoring depends on raw hostnames/domains/IPs
- planner triggers autonomous remediation
- Linux/network behavior breaks

## 12. Design status wording

Windows Risk/Planning Signal Mapping Design — partially implemented (2026-07-06):
normalized signal production/persistence shipped; dedicated risk-engine/
planner-service consumption of Windows signals remains future work.
