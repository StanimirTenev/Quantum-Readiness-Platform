# Copilot Local-First Design

## Purpose
This is a design document only.
No Copilot implementation is included.
No external LLM provider is configured.
No RAG/vector store is introduced.
No evidence is sent outside the deployment boundary.

## Current Project Context
- Stage 1 core validation is closed.
- Stage 2 enriched evidence is frozen.
- Stage 3 risk/planning improvement is frozen.
- Dependency graph is frozen as a lightweight JSON snapshot projection prototype.
- Legacy external LLM call in the demo was disabled.
- Repository checkpoint exists.

Reference:
- docs/repository-checkpoint-current-status.md
- docs/dependency-graph-freeze-status.md

## Core Principle
QRP must be useful without any LLM provider.
The deterministic core remains the source of truth.
Copilot is advisory only.

Copilot must not:
- replace deterministic scoring
- invent graph facts
- execute production changes
- rotate certificates
- change trust anchors
- send evidence externally by default

## Deployment Boundary
External LLM usage is optional and opt-in only.

- QRP is designed for internal/customer-controlled deployment.
- Evidence stays local by default.
- Graph snapshots stay local by default.
- No mandatory cloud AI dependency.
- External LLM providers must never be enabled by default.

## Sensitive Data Rules
Sensitive data includes:
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

- sensitive data must not leave the deployment boundary by default
- external sharing requires explicit operator configuration
- logs must not leak sensitive prompts/responses by default
- no private keys/secrets may ever be sent to any provider

## Provider Modes

### disabled
Default mode.

COPILOT_PROVIDER=disabled

Behavior:
- deterministic local response
- no network call
- deterministic core still works

### local
Preferred for sensitive environments.

Example:
COPILOT_PROVIDER=local
COPILOT_LOCAL_URL=http://127.0.0.1:11434

Allowed future local backends:
- Ollama
- llama.cpp server
- vLLM
- local OpenAI-compatible endpoint

### external
Optional and opt-in only.
Never default.
Not implemented now.

Example:
COPILOT_PROVIDER=external
COPILOT_EXTERNAL_PROVIDER=openai|anthropic|openrouter
COPILOT_EXTERNAL_URL=...
COPILOT_EXTERNAL_API_KEY=...

## Provider Selection Rules
- If COPILOT_PROVIDER is missing, use disabled.
- If COPILOT_PROVIDER=disabled, no network call is allowed.
- If COPILOT_PROVIDER=local, COPILOT_LOCAL_URL must be explicitly set.
- If COPILOT_PROVIDER=external, external config must be explicit and operator-approved.
- Unknown provider mode must fail closed to disabled.
- External provider must never be selected automatically.

## Future Provider Interface Design
Design only.

```python
class CopilotProvider:
    def generate(self, request: CopilotRequest) -> CopilotResponse:
        ...
```

## Copilot Request Contract
```json
{
  "query": "Summarize high-risk assets from the latest scan.",
  "context": {
    "scan_id": "scan-2026-05-09-001",
    "evidence_scope": "latest_local_scan",
    "graph_scope": "asset_neighbors_depth_1"
  },
  "sensitivity": "high",
  "metadata": {
    "request_id": "req-001",
    "operator": "security-team",
    "provider_mode": "disabled"
  }
}
```

## Copilot Response Contract
```json
{
  "answer": "High-risk assets are concentrated in legacy TLS endpoints pending migration.",
  "provider_mode": "disabled",
  "citations": ["risk:asset-12", "planner:wave-2"],
  "warnings": ["Copilot advisory only; deterministic core remains authoritative."],
  "used_external_provider": false,
  "redaction_applied": true,
  "metadata": {
    "request_id": "req-001",
    "response_id": "resp-001"
  }
}
```

## Redaction Rules
- Always block: private keys, secrets, tokens, API keys, passwords, raw credentials
- Redact by default: IPs, hostnames, FQDNs, file paths, owner names, certificate fingerprints, scan IDs, raw configs
- Summarize instead of raw sharing: risk results, planner waves, graph neighborhoods, evidence counts, package lists, certificate chain summaries

## Offline-Safe Behavior
When no provider is configured, Copilot returns:

"Copilot provider is disabled. The deterministic QRP core remains available. Configure a local provider for offline analysis."

No external network calls.

## Relationship to Retrieval / RAG
RAG is not part of this task.
Future retrieval must be local-first.

## Relationship to Graph
Graph snapshots are sensitive infrastructure intelligence.
External providers must not receive graph data unless explicitly configured.
Copilot must not invent graph facts.

## Logging and Audit Rules
- provider mode should be logged
- request ID should be logged
- sensitive prompts/responses should not be logged by default
- external provider use should be auditable
- redaction decisions should be auditable at metadata level

## Non-Goals
- no Copilot implementation
- no LLM API client
- no external provider integration
- no RAG
- no vector DB
- no embedding model
- no prompt template implementation
- no UI Copilot changes
- no auth/RBAC
- no production deployment
- no graph reasoning implementation

## Future Implementation Sequence
1. Copilot Implementation Task 1 — disabled provider stub
2. Copilot Implementation Task 2 — local provider interface
3. Copilot Implementation Task 3 — provider mode config and tests
4. Copilot Implementation Task 4 — offline-safe Copilot smoke validation
5. Copilot Implementation Task 5 — redaction/sensitivity checks
6. Later optional task — external provider opt-in design review

## Recommended Next Step
"Copilot Design Task 2 — Define local Copilot provider contract tests and offline-safe smoke behavior."
