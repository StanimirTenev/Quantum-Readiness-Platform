# Risk Engine

## What this service does
- Calculates weighted risk scores and ratings for assets under defined scenarios.

## Current role in the prototype
- Working prototype scoring engine used by inventory and gateway flows.

## Main endpoints or functions
- `GET /health`, `GET /scenarios`
- `POST /score`

## Inputs / outputs
- Input: bounded numeric factors (`0..5`) plus scenario name and asset metadata.
- Output: JSON with base/final score, normalized score, rating, stage2 signals/adjustment, and rationale fields.

## Stage 2 Evidence Signals
- Primary Stage 2 path: deterministic evidence-derived signals from optional enriched evidence blocks.
- `stage2_notes` remains supported as optional contextual hints; it is not the primary Stage 2 evidence path.

Host evidence-derived signals (`crypto_evidence`):
- `crypto_packages_detected` from `package_metadata.packages` length > 0 (`+3`)
- `certificate_files_detected` from `cert_indicators.certificate_file_indicators.counts.certificate > 0` (`+5`)
- `private_key_files_detected` from `cert_indicators.certificate_file_indicators.counts.key > 0` (`+10`)
- `tls_config_detected` from `cert_indicators.config_file_indicators.counts.tls_server_config > 0` (`+4`)
- `ssh_config_detected` from `cert_indicators.config_file_indicators.counts.ssh_server_config > 0` (`+3`)

Network TLS evidence-derived signals (`tls_metadata`):
- `tls_detected` from `tls_metadata.collected == true` (`+4`)
- `weak_public_key_detected` when RSA and key size < 2048 (`+15`)
- `expiring_certificate_detected` when `certificate.not_after` is within 90 days (`+8`)
- `certificate_chain_available` when `certificate_chain.available == true` and `length > 0` (`+2`)

Additional existing deterministic hints:
- `vendor_blocked` (`+0.20`)
- `high_dependency_pressure` for `dependency_count >= 10` (`+0.15`)
- `stage2_notes` hints: HNDL (`+0.10`) and migration plan (`-0.10`, floor at `0.0`)

Safety behavior:
- Missing optional evidence blocks are non-fatal and do not reduce score.
- Invalid certificate dates are ignored safely (no failure).
- Unknown public key algorithms are not treated as weak.
- Final normalized score is capped at `100`.

## Stage 3 Risk Dimensions and Confidence
- Stage 3 is additive and backward-compatible: existing score fields, normalized score, rating, rationale, `stage2_signals`, and `stage2_adjustment` remain available.
- `confidence_score` (`0..100`) is always returned and represents deterministic confidence based on evidence completeness (criticality/environment/evidence presence).
- `risk_dimensions.exposure` (`0..100`) captures quantum exposure with additive TLS/config evidence hints.
- `risk_dimensions.impact` (`0..100`) is primarily driven by criticality, with production environment lift.
- `risk_dimensions.urgency` (`0..100`) reflects immediate certificate/key urgency signals (expiring certs, weak keys, private key indicators).
- `risk_dimensions.migration_complexity` (`0..100`) reflects dependencies plus migration blockers (certificate/private key artifacts, vendor blocked).
- This stage is not dependency graph scoring yet; dimension logic is deterministic and local to risk-engine.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/risk-engine/tests`

## Known limitations
- Weighting and thresholds are static constants in this phase.
