# Windows Evidence Fixture Contract

## Purpose

This document defines the fixture/contract expectations for Windows evidence.
The collector and ingestion described here are now implemented (see "Current
State"); this contract remains the shape reference.

## Current State

- Linux-first collection exists.
- Windows collection is **implemented** (`agents/windows-host-agent/collect.ps1`)
  and its evidence persists via `POST /scans/ingest/windows`.
- inventory-service supports enriched Linux/network/Windows evidence patterns.
- This document defines safe normalized Windows fixture examples matching the
  live collector output.

## Non-Goals

- no Windows agent implementation
- no AD scanner implementation
- no remote execution
- no credential collection
- no private key export
- no registry crawler implementation
- no production endpoint deployment

## Windows Evidence Categories

Intended fixture categories:

- os_metadata
- installed_software_summary
- crypto_package_indicators
- certificate_store_indicators
- windows_service_indicators
- schannel_tls_indicators
- domain_membership_indicators
- machine_role_indicators
- warnings
- errors

## Privacy/Safety Boundaries

- no secrets
- no passwords
- no private keys
- no credential dumping
- no raw user documents
- no full registry dump
- no full filesystem crawl
- no raw certificate private material

## Proposed Fixture Shape

```json
{
  "asset": {
    "asset_id": "win-host-fixture-001",
    "asset_type": "endpoint",
    "platform": "windows",
    "hostname_redacted": true
  },
  "windows_evidence": {
    "os_metadata": {
      "family": "windows",
      "version_family": "windows_server_or_workstation",
      "architecture": "x86_64"
    },
    "installed_software_summary": {
      "total_observed": 42,
      "crypto_relevant_observed": 3,
      "package_names_redacted": true
    },
    "crypto_package_indicators": {
      "crypto_packages_observed": 3,
      "package_details_redacted": true
    },
    "certificate_store_indicators": {
      "stores_observed": ["LocalMachine\\My", "LocalMachine\\Root"],
      "certificates_observed_count": 12,
      "expired_certificates_count": 1,
      "weak_signature_indicators_count": 0,
      "private_keys_exported": false
    },
    "windows_service_indicators": {
      "crypto_relevant_services_observed": 2,
      "service_names_redacted": true
    },
    "schannel_tls_indicators": {
      "schannel_policy_observed": true,
      "tls_legacy_protocols_enabled_observed": false,
      "cipher_policy_summary_redacted": true
    },
    "domain_membership_indicators": {
      "domain_joined": true,
      "domain_name_redacted": true,
      "ad_details_collected": false
    },
    "machine_role_indicators": {
      "server_role_observed": false,
      "workstation_role_observed": true,
      "domain_controller_role_observed": false
    },
    "warnings": [],
    "errors": []
  }
}
```

## Inventory Ingest Mapping

Future Windows fixtures should map into inventory-service using:

- `platform=windows`
- asset metadata block compatible with existing ingest shape
- normalized Windows evidence blocks under a dedicated object
- warnings/errors arrays preserved for non-fatal ingest diagnostics
- backward compatibility with Stage 2 enriched evidence patterns

## Future Validation Approach

Future tests should validate:

- fixture loads as JSON
- required top-level keys exist
- no forbidden sensitive fields are present
- inventory-service can accept normalized Windows evidence later
- risk/planning consume normalized signals only

## Status

Windows Evidence Fixture Contract — implemented (2026-07-06): a live collector
emits this contract and inventory-service ingests it via
`POST /scans/ingest/windows`. The fixture examples remain the shape reference.
