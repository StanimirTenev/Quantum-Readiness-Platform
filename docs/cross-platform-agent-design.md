# Cross-Platform Agent Design

**Status:** Partially implemented (2026-07-06). A Windows host collector now
exists and its evidence persists into inventory; AD / certificate-estate
discovery remains future scope. Retained as the design record.

## 1) Purpose

This document defines the design for cross-platform evidence collection in QRP.
The Windows host collector described here has since been implemented; the AD
scanner and broader certificate-estate discovery remain future scope.

## 2) Current state

QRP operates with deterministic local-first evidence collection on Linux and
Windows hosts:

- Linux host agent exists.
- Network scanner exists.
- Windows host agent exists (`agents/windows-host-agent/collect.ps1`) —
  redacted/aggregate collector; its evidence persists into inventory via
  `POST /scans/ingest/windows`.
- Enriched evidence ingestion exists (Linux/network/Windows).
- AD / certificate-estate discovery is future scope.
- Deterministic local-first collection remains the rule.

## 3) Design principles

Future cross-platform agent design should preserve the following principles:

- Local-first evidence collection.
- No sensitive content parsing by default.
- Bounded discovery.
- Deterministic output contracts.
- Backward compatibility with Stage 2 ingest.
- Platform-specific collectors, common normalized schema.
- No mandatory external service dependency.

## 4) Platform model

Future platform categories:

- Linux server
- Linux workstation
- Windows workstation
- Windows server
- Active Directory environment
- Network/TLS endpoint scanner

## 5) Evidence categories

Possible normalized evidence categories:

- Package/software inventory
- OS metadata
- Crypto/security package indicators
- Certificate file indicators
- TLS endpoint metadata
- SSH/TLS/VPN configuration indicators
- Windows certificate store indicators
- Windows installed software indicators
- Windows service indicators
- AD/domain relationship indicators
- Machine role indicators

## 6) Linux current implementation

Current Linux-first capability summary:

- Package metadata
- Package manager detection
- Certificate/config file indicators
- Bounded file discovery
- No content parsing
- Stable evidence output

## 7) Windows collection design (implemented 2026-07-06)

Implemented in `agents/windows-host-agent/collect.ps1` (redacted/aggregate):

- Installed software via registry/WMI/PowerShell ✅
- Windows certificate store inventory summary ✅ (+ safe per-cert crypto surface)
- Machine role detection ✅
- Local services with crypto/security relevance ✅
- TLS/Schannel configuration indicators ✅
- Domain membership indicators ✅
- No private key export ✅
- No secret collection ✅
- No full filesystem crawl by default ✅

## 8) AD/certificate estate future design

Future AD/certificate estate discovery scope (design only):

- Domain presence detection
- CA presence indicators
- Certificate template summary
- Expiring certificate indicators
- Weak crypto indicators where safely observable
- No credential dumping
- No secret extraction
- No invasive domain scanning by default

## 9) Normalized evidence contract

Proposed high-level common schema (conceptual only; no schema changes in this task):

- `asset_id`
- `platform`
- `collector_type`
- `collection_timestamp`
- `evidence_version`
- `os_metadata`
- `software_inventory_summary`
- `crypto_evidence`
- `certificate_indicators`
- `service_indicators`
- `domain_indicators`
- `warnings`
- `errors`

This section does not change any actual code/schema now.

## 10) Inventory ingest compatibility

Future Windows evidence should map into the existing `inventory-service` ingest pathway by:

- Preserving current Stage 1/Stage 2 payload acceptance boundaries.
- Adding Windows-derived signals through optional normalized fields rather than breaking required fields.
- Keeping existing fixtures valid and unchanged.
- Introducing new fixtures in additive form only.

Goal: no breakage of Stage 1/2 fixtures or current ingest behavior.

## 11) Risk/planning compatibility

Risk and planning layers should consume normalized signals instead of platform-specific raw internals:

- `risk-engine` should evaluate common evidence signals regardless of collector platform.
- `planner-service` should prioritize based on normalized risk posture, not OS-specific raw collector structure.
- Platform-specific collection detail remains an upstream concern.

## 12) Privacy and safety boundaries

The future cross-platform design must explicitly maintain these boundaries:

- No secrets
- No private keys
- No credential collection
- No content parsing by default
- No unbounded filesystem crawl
- No forced remote execution
- No autonomous remediation

## 13) Future implementation phases

Proposed implementation phases:

- **Phase 0** — Review current Linux agent contract
- **Phase 1** — Define Windows evidence fixture only ✅ done
- **Phase 2** — Add inventory-service fixture validation ✅ done
- **Phase 3** — Add Windows collector design tests ✅ done
- **Phase 4** — Implement minimal Windows collector ✅ done + inventory ingestion
- **Phase 5** — Add E2E smoke using fixture, not live AD ✅ done (`scripts/run_windows_evidence_smoke.ps1`)
- **Phase 6** — Optional AD/certificate estate discovery design 🔲 open

## 14) Non-goals

Explicit non-goals for this task:

- No Windows agent implementation in this task
- No AD scanner implementation
- No remote execution
- No credential collection
- No production deployment hardening
- No cloud/KMS/HSM integration
- No autonomous remediation

## 15) Status wording

Cross-Platform Agent Design — partially implemented (2026-07-06): Windows host
collector + inventory ingestion shipped; AD / certificate-estate discovery and
production hardening remain future scope.
