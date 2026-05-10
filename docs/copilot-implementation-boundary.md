# Copilot Implementation Boundary

## Purpose
This document defines the first safe Copilot implementation boundary.

This is a design decision document only.
No Copilot implementation is included.
No LLM client is added.
No external endpoint is configured.
No RAG/vector store is introduced.
The first implementation must be offline-safe.

## Current Copilot Design Status
- local-first provider boundary documented
- provider contract test plan documented
- context packaging policy documented
- legacy external LLM demo call disabled
- repository remains local-first

## Problem to Solve
The project needs a future Copilot entry point, but must avoid:
- external LLM dependency
- accidental evidence leakage
- premature RAG/vector DB work
- UI complexity
- prompt/template overbuild
- replacing deterministic risk/planning logic

## Implementation Options Considered

### Option A — Disabled Provider Stub First
Description:
Implement only a disabled provider that returns a deterministic offline-safe response.

Pros:
- safest
- no network
- no external dependency
- easy to test
- validates provider boundary
- keeps deterministic core independent

Cons:
- no real AI behavior yet
- limited demo value

### Option B — Local Provider First
Description:
Implement local LLM provider support immediately.

Pros:
- closer to useful Copilot behavior
- local-first

Cons:
- requires local model endpoint
- introduces provider/network behavior
- more testing complexity
- premature before disabled boundary is proven

### Option C — External Provider First
Description:
Implement OpenAI/Anthropic/OpenRouter-style provider first.

Pros:
- fastest AI demo

Cons:
- violates local-first default
- privacy risk
- external dependency
- not acceptable as default path

### Option D — RAG First
Description:
Implement retrieval/vector store before provider boundary.

Pros:
- more grounded future answers

Cons:
- too early
- needs indexing/redaction/storage decisions
- expands scope too much

## Recommended Decision
"Disabled Provider Stub First"

The first Copilot implementation should not call any LLM.
It should only validate:
- provider selection
- disabled default behavior
- request/response shape
- no network call
- offline-safe response
- smoke report generation

## Minimal First Implementation Boundary
Allowed in first future Copilot implementation:
- small Copilot provider interface
- DisabledCopilotProvider
- provider selection logic defaulting to disabled
- offline-safe deterministic response
- unit tests proving no network call
- smoke script: scripts/run_copilot_offline_smoke.sh
- report: reports/copilot/offline-smoke-report.md
- README note

Not allowed in first implementation:
- local LLM call
- external LLM call
- OpenAI/OpenRouter/Anthropic clients
- RAG/vector DB
- embedding model
- prompt template system
- UI changes
- auth/RBAC
- production deployment changes
- graph reasoning
- raw evidence packaging

## Proposed First Implementation Shape
Future files may be:
- services/copilot-service/app/providers.py
- services/copilot-service/app/models.py
- services/copilot-service/tests/test_disabled_provider.py
- scripts/run_copilot_offline_smoke.sh
- reports/copilot/offline-smoke-report.md

Exact file names may follow existing copilot-service structure during implementation.

## Disabled Provider Behavior
Expected response:

```json
{
  "answer": "Copilot provider is disabled. The deterministic QRP core remains available. Configure a local provider for offline analysis.",
  "provider_mode": "disabled",
  "citations": [],
  "warnings": ["copilot_provider_disabled"],
  "used_external_provider": false,
  "redaction_applied": false,
  "metadata": {
    "request_id": "string",
    "provider_name": "disabled"
  }
}
```

Rules:
- no network call
- no external endpoint
- no retries
- no API key required
- deterministic response
- safe with or without context

## Provider Selection Rules for First Implementation
- Missing COPILOT_PROVIDER => disabled
- COPILOT_PROVIDER=disabled => disabled
- Unknown COPILOT_PROVIDER => disabled or fail-closed to disabled
- COPILOT_PROVIDER=local => not implemented yet; fail safely with clear warning
- COPILOT_PROVIDER=external => not implemented yet; fail safely with clear warning
- No mode may silently call external provider

## Future Offline Smoke Behavior
Define script:

scripts/run_copilot_offline_smoke.sh

Expected checks:
- starts/uses copilot-service if current local scripts support it, or directly runs provider smoke if service is not yet in startup set
- sends sample Copilot request
- verifies provider_mode=disabled
- verifies used_external_provider=false
- verifies warnings include copilot_provider_disabled
- verifies no external URL configured
- writes report:

reports/copilot/offline-smoke-report.md

Report sections:

# Copilot Offline Smoke Report

## Validation Date

## Scope
- disabled provider default
- offline-safe deterministic response
- no external LLM call
- no network dependency

## Provider Mode

## Request Summary

## Response Summary

## Boundary Checks

| Check | Result |
|---|---|

Required checks:
- provider_mode is disabled
- used_external_provider is false
- no external endpoint configured
- deterministic response returned
- no raw evidence required

## Result

PASS or FAIL

## Unit Test Expectations
Future tests must cover:

1. missing provider env selects disabled
2. COPILOT_PROVIDER=disabled selects disabled
3. unknown provider fails closed
4. local provider mode fails safely until implemented
5. external provider mode fails safely until implemented
6. disabled provider returns deterministic answer
7. used_external_provider=false
8. no network client called
9. no API key required
10. context with sensitive fields does not change disabled response behavior

## Privacy / Local-First Boundary
- disabled provider must work without internet
- deterministic core must work without Copilot
- no sensitive evidence leaves the process
- no external LLM is used
- no graph snapshot is sent anywhere
- no raw scan artifacts are sent anywhere

## What Would Trigger Local Provider Later
Local provider implementation becomes reasonable only after:
- disabled provider stub works
- offline smoke passes
- provider selection tests pass
- redaction/context packaging tests exist
- local provider interface is reviewed
- local-only URL validation is defined

## What Would Trigger External Provider Later
External provider implementation becomes reasonable only after:
- local provider works
- redaction is implemented
- operator opt-in config exists
- allowed_external enforcement exists
- audit logging exists
- external provider design review is completed

## Non-Goals
- no Copilot implementation in this task
- no disabled provider code in this task
- no local provider implementation
- no external provider implementation
- no LLM API client
- no RAG/vector DB
- no embedding model
- no UI
- no auth/RBAC
- no production deployment
- no graph reasoning implementation

## Recommended Next Step
"Copilot Implementation Task 1 — Add disabled provider stub and offline smoke validation."
