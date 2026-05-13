# Local Copilot Provider Implementation Plan

**Status:** Local Copilot Provider Implementation Plan — docs-only, not implemented.

## 1) Purpose

This document is a future implementation plan only for a local-only Copilot provider.

It does **not** activate a provider, implement a provider, or add provider tests in the current repository state.

## 2) Current State

Current baseline behavior to preserve:

- Current default provider mode is `disabled`.
- Missing provider configuration returns the disabled-safe response.
- Unknown provider values fail closed to disabled-safe behavior.
- Deterministic QRP services remain the source of truth.
- Local provider remains not implemented.

## 3) Implementation Principles

Any future implementation should follow these principles:

- local-first
- fail-closed
- no external fallback
- minimal code changes
- deterministic core remains authoritative
- advisory-only Copilot
- backward compatibility with current disabled response
- no sensitive evidence export by default

## 4) Proposed Future Implementation Sequence

### Phase 0 — Baseline verification

- Run existing Copilot tests.
- Run existing offline smoke.
- Confirm disabled behavior before touching code.

### Phase 1 — Add provider configuration parser

- Parse `COPILOT_PROVIDER`.
- Parse `COPILOT_LOCAL_URL`.
- Default missing config to disabled.
- Unknown provider fails closed.
- No network calls yet.

### Phase 2 — Add local URL validation helper

- Accept `localhost`.
- Accept `127.0.0.1`.
- Accept RFC1918 private IP ranges.
- Reject public DNS names.
- Reject public IPs.
- Reject malformed URLs.
- Fail closed on parser errors.

### Phase 3 — Add local provider interface shell

- Define an internal provider interface.
- No external provider implementation.
- No vendor-specific client.
- No OpenAI/OpenRouter/Anthropic references.
- Local provider remains controlled by config.

### Phase 4 — Add safe local request packaging

- Summarized/redacted context by default.
- No raw hostnames/IPs/package lists by default.
- No secrets/tokens/private keys.
- No full graph snapshot by default.

### Phase 5 — Add local provider call with strict timeout

- Call only a validated local URL.
- Timeout returns a safe warning.
- Malformed response returns a safe warning.
- `used_external_provider` remains `false`.

### Phase 6 — Add contract tests

- Provider selection tests.
- URL validation tests.
- External fallback prevention tests.
- Context redaction tests.
- Response safety tests.
- Deterministic-core protection tests.

### Phase 7 — Add smoke script

- Existing local disabled smoke remains valid.
- New local-provider smoke uses a mock/local test server only.
- No internet required.

## 5) Files Likely to Change in Future Implementation

The exact file list may differ, but future work would likely touch:

- `services/copilot-service/*`
- `services/copilot-service/tests/*`
- `scripts/run_copilot_offline_smoke.sh` or a new smoke script
- `docs/copilot-freeze-status.md`
- `README.md`

## 6) Files/Areas That Must Not Be Changed for This Feature

Future local provider work must not change these runtime or architecture areas:

- risk-engine runtime logic
- planner-service runtime logic
- inventory-service runtime logic
- graph projection runtime logic
- agent collectors
- production auth/RBAC
- dependency graph DB/API/UI

## 7) Backward Compatibility Requirements

Future implementation must preserve:

- Existing disabled-provider response contract remains valid.
- Existing tests continue to pass.
- Missing provider config behaves as disabled.
- Unknown provider values fail closed.
- No current smoke path requires a local LLM.

## 8) Stop Conditions

Future implementation must stop immediately if any of these occurs:

- A public URL is required.
- An external fallback appears.
- A vendor SDK is introduced.
- Sensitive evidence is sent by default.
- Disabled behavior changes unexpectedly.
- Deterministic service outputs are modified by Copilot.
- Broad architecture changes are required.

## 9) Validation Gates

Future work should use explicit gates:

- Gate A: before implementation (baseline tests/smoke + disabled contract confirmation)
- Gate B: after config parser (selection/fail-closed behavior unchanged)
- Gate C: after URL validator (local-only acceptance + fail-closed rejection paths)
- Gate D: after provider shell (interface present, no vendor coupling, no external fallback)
- Gate E: after request packaging (redaction defaults verified)
- Gate F: after provider call (strict timeout + safe-warning behavior verified)
- Gate G: after smoke tests (offline-disabled smoke still passes + local mock smoke passes)

## 10) Status Wording

Local Copilot Provider Implementation Plan — docs-only, not implemented.
