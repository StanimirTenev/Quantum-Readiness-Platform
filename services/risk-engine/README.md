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

Network SSH evidence-derived signals (`ssh_metadata`, from network-scanner's `-protocol ssh`
handshake -- see `agents/network-scanner/README.md`). The scanner reports offered algorithms
as neutral facts; the weak/legacy judgment happens here:
- `weak_ssh_kex_detected` when `kex_algorithms` includes a SHA-1-based Diffie-Hellman group (`+6`)
- `legacy_ssh_host_key_detected` when `server_host_key_algorithms` includes `ssh-rsa` or `ssh-dss` (`+8`)
- `weak_ssh_cipher_detected` when either encryption algorithm direction includes a legacy cipher
  (3DES, RC4/arcfour, Blowfish, CAST128, DES) (`+4`)
- `weak_ssh_mac_detected` when either MAC algorithm direction includes `hmac-md5*` or `hmac-sha1*` (`+3`)

Network IPsec/IKEv2 evidence-derived signals (`ipsec_metadata`, from network-scanner's
`-protocol ipsec` IKE_SA_INIT probe -- see `agents/network-scanner/README.md`). Same
judge-here-not-in-the-collector split as SSH:
- `legacy_ipsec_dh_group_detected` when `selected_dh_group` is `768-bit MODP` or `1024-bit MODP` (`+8`)
- `weak_ipsec_encryption_detected` when `selected_encryption` is `DES-IV64`, `DES`, `3DES`, or `NULL` (`+6`)
- `weak_ipsec_prf_detected` when `selected_prf` is `HMAC-MD5` or `HMAC-SHA1` (`+4`)
- `weak_ipsec_integrity_detected` when `selected_integrity` is `HMAC-MD5-96`, `DES-MAC`, `KPDK-MD5`, or `HMAC-SHA1-96` (`+3`)

Repo evidence-derived signals (`crypto_evidence.repo_scan`, from repo-ci-scanner's IaC/CI
scanning -- see `agents/repo-ci-scanner/README.md`):
- `embedded_private_key_in_repo_detected` when `repo_scan.embedded_key_findings` is non-empty (`+12`)
- `ci_signing_command_detected` when `repo_scan.ci_pipeline_findings` is non-empty (`+3`) -- a
  detected signing command (`gpg --sign`, `cosign sign`, etc.); the signing key's algorithm
  isn't visible from the pipeline config alone, so this flags the pipeline for manual review
  rather than judging the key itself weak.

AD/CA certificate estate evidence-derived signals (`crypto_evidence.ad_evidence` -- see
`docs/ad-certificate-estate-design.md`; fixture-only for now, no live collector implemented):
- `ad_weak_certificate_template_detected` when `certificate_template_indicators
  .templates_with_weak_key_algorithm_count` or `...templates_with_weak_signature_algorithm_count`
  is `> 0` (`+10`) -- weighted higher than a single weak leaf certificate because every
  certificate issued from a weak template inherits the weakness going forward.
- `ad_ca_certificate_expiring_detected` when `ca_presence_indicators
  .root_ca_certificates_expiring_count` is `> 0` (`+8`)
- `ad_large_certificate_estate_detected` when `certificate_template_indicators
  .templates_observed_count >= 20` (`+3`)

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
- `risk_dimensions.exposure` (`0..100`) captures quantum exposure with additive TLS/config/SSH/IPsec evidence hints (`weak_ssh_kex_detected`, `legacy_ssh_host_key_detected`, `legacy_ipsec_dh_group_detected`, `ad_weak_certificate_template_detected`).
- `risk_dimensions.impact` (`0..100`) is primarily driven by criticality, with production environment lift.
- `risk_dimensions.urgency` (`0..100`) reflects immediate certificate/key urgency signals (expiring certs, weak keys, private key indicators, `embedded_private_key_in_repo_detected`, `ad_weak_certificate_template_detected`, `ad_ca_certificate_expiring_detected`).
- `risk_dimensions.migration_complexity` (`0..100`) reflects dependencies plus migration blockers (certificate/private key artifacts, `embedded_private_key_in_repo_detected`, `ci_signing_command_detected`, `ad_weak_certificate_template_detected`, `ad_large_certificate_estate_detected`, vendor blocked).
- This stage is not dependency graph scoring yet; dimension logic is deterministic and local to risk-engine.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/risk-engine/tests`

## Known limitations
- Weighting and thresholds are static constants in this phase.
