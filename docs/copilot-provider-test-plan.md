# Copilot Provider Test Plan

## Purpose

This document defines future test expectations for Copilot provider behavior before implementation.

This is a design/test-plan document only.
No Copilot implementation is included.
No LLM client is added.
No external endpoint is configured.
No RAG/vector DB is introduced.

## Relationship to Local-First Design

Reference:
- docs/copilot-local-first-design.md

That document defines the provider boundary and request/response contracts.
This document defines how future implementation should be tested.

## Test Principles

- fail closed to disabled
- no network call in disabled mode
- no external call unless explicitly configured
- local provider must require explicit local URL
- unknown provider mode must behave as disabled or fail closed
- deterministic core must work without Copilot
- sensitive data must not be logged or sent externally by default
- tests must not require internet access

## Provider Modes to Test

### disabled mode

Expected:
- default when COPILOT_PROVIDER is missing
- default/no-network behavior
- deterministic offline-safe response
- used_external_provider=false
- provider_mode=disabled
- no retry loop to external services

### local mode

Expected:
- requires COPILOT_PROVIDER=local
- requires COPILOT_LOCAL_URL
- sends request only to configured local/internal URL
- never falls back to external provider
- handles local provider unavailable gracefully
- response includes provider_mode=local when successful

### external mode

Expected:
- not implemented initially
- must never be default
- must require explicit config
- must require allowed_external=true
- tests should confirm external is blocked when allowed_external=false

## Future Unit Test Cases

List exact test cases.

### Provider selection tests

1. Missing COPILOT_PROVIDER selects disabled provider.
2. COPILOT_PROVIDER=disabled selects disabled provider.
3. Unknown COPILOT_PROVIDER fails closed to disabled.
4. COPILOT_PROVIDER=local without COPILOT_LOCAL_URL fails safely.
5. COPILOT_PROVIDER=external without explicit external config fails safely.
6. External provider is never selected automatically.

### Disabled provider tests

1. generate() returns offline-safe deterministic answer.
2. used_external_provider is false.
3. provider_mode is disabled.
4. no network client is called.
5. sensitive context is not logged.

### Local provider tests

1. local provider uses only COPILOT_LOCAL_URL.
2. local provider does not call external URLs.
3. local provider handles unavailable local endpoint with clear warning.
4. local provider preserves request_id.
5. local provider returns used_external_provider=false.

### External guardrail tests

1. external mode blocked when allowed_external=false.
2. external mode requires explicit operator config.
3. sensitive raw_evidence is redacted or blocked.
4. graph_snapshot context is blocked unless explicitly allowed.
5. no private keys/secrets ever leave the boundary.

### Redaction tests

1. private keys are always blocked.
2. API keys/tokens/passwords are always blocked.
3. IP addresses are redacted by default.
4. hostnames/FQDNs are redacted by default.
5. file paths are redacted by default.
6. certificate fingerprints are redacted by default.
7. graph node IDs are redacted when marked sensitive.
8. summaries are preferred over raw evidence.

### Logging/audit tests

1. provider_mode is logged.
2. request_id is logged.
3. full sensitive prompt is not logged by default.
4. full sensitive response is not logged by default.
5. redaction_applied metadata is recorded.
6. external provider use is auditable without storing raw sensitive content.

## Future Smoke Validation

Define a future smoke script:

scripts/run_copilot_offline_smoke.sh

Expected behavior:

- sets COPILOT_PROVIDER=disabled
- sends a sample Copilot request
- verifies deterministic disabled response
- verifies used_external_provider=false
- verifies no external endpoint is configured
- verifies no network call is attempted
- writes report:

reports/copilot/offline-smoke-report.md

Report sections:

# Copilot Offline Smoke Report

## Validation Date

## Scope
- disabled provider default
- offline-safe behavior
- no external LLM call
- sensitive context blocked/redacted

## Provider Mode

## Request Summary

## Response Summary

## Redaction / Boundary Checks

## Result

PASS or FAIL

## Future Local Provider Smoke

Define future script:

scripts/run_copilot_local_provider_smoke.sh

Expected behavior:

- requires COPILOT_PROVIDER=local
- requires COPILOT_LOCAL_URL
- calls only local/internal URL
- fails if URL is external
- verifies provider_mode=local
- verifies used_external_provider=false
- writes report:

reports/copilot/local-provider-smoke-report.md

This is future work. Do not implement now.

## Test Data Rules

Future tests should use fake/safe data only:

- demo-host.local
- 10.0.0.1 or documentation-reserved IPs
- /redacted/path/example.conf
- fake certificate fingerprints
- fake graph node IDs
- no real secrets
- no real private keys
- no real infrastructure data

## Network Isolation Rules

Future tests must be able to pass without internet access.

Rules:
- disabled provider tests must not create sockets
- local provider tests must use mock/local test server
- external provider tests must be mocked or blocked
- CI must not require external LLM accounts

## Acceptance Criteria for Future Implementation

Future Copilot implementation may be accepted only when:

- disabled mode works without network
- local provider mode is explicit and tested
- external mode is blocked by default
- redaction tests pass
- smoke report is generated
- deterministic core still passes without Copilot
- no sensitive data leaves boundary by default

## Non-Goals

- no Copilot implementation now
- no LLM client now
- no external provider now
- no RAG/vector DB now
- no embedding model now
- no UI changes now
- no auth/RBAC now
- no production deployment now

## Recommended Next Step

"Copilot Design Task 3 — Define Copilot context packaging and summary-only prompt policy."
