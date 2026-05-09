# Copilot Local-First Design

## Purpose

This document defines the future Copilot boundary for QRP before any implementation work begins.

This is a design document only.
No Copilot implementation is included.
No external LLM provider is configured.
No RAG/vector store is introduced.
No evidence is sent outside the deployment boundary.

## Current Project Context

Current repository status for this design baseline:

- Stage 1 core validation is closed.
- Stage 2 enriched evidence is frozen.
- Stage 3 risk/planning improvement is frozen.
- Dependency graph is frozen as a lightweight JSON snapshot projection prototype.
- Legacy external LLM call in the demo was disabled.
- Repository checkpoint exists.

References:

- `docs/repository-checkpoint-current-status.md`
- `docs/dependency-graph-freeze-status.md`

## Core Principle

QRP must be useful without any LLM provider.

The deterministic core remains the source of truth:

- scanners
- inventory-service
- risk-engine
- policy-engine
- planner-service
- workflow-service
- graph snapshot projection

Copilot is advisory only.

Copilot must not:

- replace deterministic scoring
- invent graph facts
- execute production changes
- rotate certificates
- change trust anchors
- send evidence externally by default

## Deployment Boundary

- QRP is designed for internal/customer-controlled deployment.
- Evidence stays local by default.
- Graph snapshots stay local by default.
- External LLM usage is optional and opt-in only.
- No mandatory cloud AI dependency.
- External LLM providers must never be enabled by default.

## Sensitive Data Rules

Copilot must treat the following as sensitive:

- hostnames
- IP addresses
- file paths
- package lists
- certificate metadata
- certificate fingerprints
- config indicators
- owner/team data
- risk scores
- graph snapshots
- migration tasks
- internal documents
- scan artifacts
- logs
- prompts/responses containing infrastructure details

Rules:

- do not send sensitive data outside the deployment boundary by default
- external sharing requires explicit operator configuration
- provider mode must be visible/configurable
- future UI/API must show provider mode clearly
- logs must not leak sensitive prompts/responses by default
- no private keys/secrets may ever be sent to any provider

## Provider Modes

Define exactly these provider modes.

### disabled

Default mode.

Behavior:

- Copilot returns a deterministic message explaining that Copilot is disabled.
- No network call.
- No external request.
- Deterministic core still works.

Example config:

```bash
COPILOT_PROVIDER=disabled
```

Example response:

"Copilot provider is disabled. The deterministic QRP core remains available. Configure a local provider for offline analysis."

### local

Preferred mode for sensitive environments.

Behavior:

- Copilot sends prompts only to a local/internal LLM endpoint.
- Endpoint must be explicitly configured.
- No external provider is used.
- Local provider must be customer-controlled.

Example config:

```bash
COPILOT_PROVIDER=local
COPILOT_LOCAL_URL=http://127.0.0.1:11434
```

Allowed future local backends:

- Ollama
- llama.cpp server
- vLLM
- local OpenAI-compatible endpoint

### external

Optional and opt-in only.

Behavior:

- External provider may be used only when explicitly configured by the operator.
- Must never be default.
- Must require explicit environment configuration.
- Must include warning in docs/UI.
- Must check that external sharing is allowed for the request.

Example config:

```bash
COPILOT_PROVIDER=external
COPILOT_EXTERNAL_PROVIDER=openai|anthropic|openrouter
COPILOT_EXTERNAL_URL=...
COPILOT_EXTERNAL_API_KEY=...
```

This mode is not implemented now.

## Provider Selection Rules

1. If `COPILOT_PROVIDER` is missing, use `disabled`.
2. If `COPILOT_PROVIDER=disabled`, no network call is allowed.
3. If `COPILOT_PROVIDER=local`, `COPILOT_LOCAL_URL` must be explicitly set.
4. If `COPILOT_PROVIDER=external`, external config must be explicit and operator-approved.
5. Unknown provider mode must fail closed to `disabled`.
6. External provider must never be selected automatically.

## Future Provider Interface Design

Design only.

Potential future interface:

```python
class CopilotProvider:
    def generate(self, request: CopilotRequest) -> CopilotResponse:
        ...
```

Notes:

- `CopilotRequest` and `CopilotResponse` are future contracts only and are not implemented in this document.
- The provider implementation must be swappable across `disabled`, `local`, and `external` modes.
- `disabled` mode must return deterministic guidance and perform no network I/O.

## Future Request/Response Contracts (Design Only)

### CopilotRequest

Proposed fields:

- `request_id`: deterministic identifier for traceability
- `intent`: supported advisory intent (for example: explain-risk, summarize-evidence, suggest-next-step)
- `context_scope`: narrow scope selector limiting what evidence is eligible
- `content`: operator/user prompt text
- `sensitivity`: classification hint (`high`, `internal`, `low`)
- `allow_external`: explicit per-request flag for external mode eligibility
- `metadata`: non-sensitive execution metadata

Contract rules:

- Requests must be minimal and scope-limited.
- Sensitive fields must pass redaction policy before provider dispatch.
- `allow_external` defaults to `false`.

### CopilotResponse

Proposed fields:

- `request_id`: mirrors request correlation id
- `mode_used`: one of `disabled`, `local`, `external`
- `advice`: advisory-only text
- `citations`: optional deterministic references to internal evidence ids
- `warnings`: policy and confidence warnings
- `redaction_applied`: boolean flag indicating outbound redaction was applied
- `provider_metadata`: bounded non-sensitive diagnostics

Contract rules:

- Response content is advisory only and non-authoritative.
- Deterministic engine outputs remain authoritative for scoring and planning decisions.
- Provider metadata must not include secrets, raw prompts, or sensitive payload dumps.

## Redaction Rules (Design Only)

Redaction applies before any non-disabled provider dispatch, with stricter enforcement for `external` mode.

### Minimum required redaction controls

- Strip or mask direct infrastructure identifiers (hostnames, IPs, internal DNS names).
- Strip absolute file paths and environment-specific directory layouts.
- Strip certificate fingerprints/serials unless explicitly required and approved.
- Strip owner/team identifiers unless needed for advisory intent and policy allows.
- Strip migration task internals that reveal internal topology.
- Strip raw logs and artifacts unless explicit allowlist permits excerpts.
- Never include secrets/private keys/tokens/passwords in any provider payload.

### Policy behavior

- Default-deny outbound fields unless explicitly allowlisted.
- Maintain a deterministic redaction report per request (`what_removed`, `why`).
- If policy cannot safely redact for external mode, fail closed and return a deterministic policy warning.
- Redaction policy must be testable as a pure deterministic component.

## Offline Behavior

- QRP deterministic core behavior is unchanged with Copilot disabled.
- In `disabled` mode, Copilot returns deterministic disabled guidance and does not degrade core workflows.
- In `local` mode, if local endpoint is unavailable, Copilot fails gracefully with deterministic fallback message and no external failover.
- External failover from local mode is forbidden unless operator explicitly switches mode to `external`.

## Non-Goals for This Document

This document does not implement:

- Copilot runtime logic
- LLM client integrations (OpenAI/Anthropic/OpenRouter/etc.)
- Retrieval-augmented generation (RAG)
- vector databases
- auth/RBAC changes
- UI changes
- deterministic core engine changes

## Acceptance Criteria for Future Implementation

Future implementation should be considered compliant only if:

- Default behavior is `COPILOT_PROVIDER=disabled` with no network traffic.
- Local mode requires explicit local endpoint configuration.
- External mode is explicit, opt-in, and policy-gated.
- Sensitive data redaction is deterministic and enforced before provider calls.
- No deterministic core authority is delegated to Copilot.
- Logs avoid leaking sensitive prompt/response data by default.
