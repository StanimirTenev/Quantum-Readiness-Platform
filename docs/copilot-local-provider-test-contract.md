# Local Copilot Provider Test Contract

**Status:** Local Copilot Provider Test Contract — docs-only, not implemented.

## 1. Purpose

This document defines the **future acceptance test contract** for a local-only Copilot provider in QRP. It is a documentation artifact only; it is not an implementation and does not activate any provider mode.

## 2. Current implementation status

Current system behavior remains unchanged:

- current provider mode remains disabled
- unknown providers fail closed
- local provider is design-only
- no external provider exists
- deterministic QRP services remain the source of truth

## 3. Test categories

The following categories define future acceptance tests for a later implementation.

### A. Provider selection tests

- missing `COPILOT_PROVIDER` returns `disabled`
- `COPILOT_PROVIDER=disabled` returns `disabled`
- unknown provider returns disabled/fail-closed warning
- `COPILOT_PROVIDER=local` without valid `COPILOT_LOCAL_URL` fails closed

### B. Local URL validation tests

- `localhost` accepted
- `127.0.0.1` accepted
- RFC1918 private LAN IP accepted
- public DNS rejected
- public IP rejected
- malformed URL rejected
- redirect to public network rejected
- parse error fails closed

### C. External fallback prevention tests

- no OpenAI/OpenRouter/Anthropic fallback
- unknown provider must not call external URL
- local provider timeout must not call external URL
- malformed local response must not call external URL
- `used_external_provider` must remain `false`

### D. Context packaging and redaction tests

- request context is summarized/redacted by default
- raw hostnames are not sent by default
- raw IPs are not sent by default
- raw package lists are not sent by default
- secrets/tokens/private keys are never sent
- full graph snapshot is not sent by default

### E. Response safety tests

- timeout returns safe warning
- malformed provider response returns safe warning
- provider unavailable returns safe warning
- response preserves `request_id`
- response remains compatible with existing Copilot response contract

### F. Deterministic-core protection tests

- local provider answer is advisory only
- local provider cannot modify inventory/risk/planning state
- local provider cannot execute remediation
- deterministic services remain source of truth

## 4. Expected future fixtures

Fixture names for future test implementation:

- `local_provider_valid_request.json`
- `local_provider_redacted_context_request.json`
- `local_provider_malformed_response.json`
- `local_provider_timeout_case.json`
- `local_provider_public_url_rejected.env`
- `local_provider_private_url_allowed.env`

## 5. Acceptance criteria

A future local-provider implementation is acceptable only if:

- all local-provider contract tests pass
- no external provider fallback exists
- `used_external_provider` is `false` in all local/disabled paths
- `redaction_applied` is `true` when sensitive context is summarized
- unknown/malformed configuration fails closed
- current disabled-provider behavior remains backward compatible

## 6. Non-goals

- this document does not implement tests
- this document does not activate local provider
- this document does not introduce provider code
- this document does not approve external provider usage
- this document does not add RAG/vector DB/embeddings
- this document does not add autonomous execution

## 7. Relationship to existing docs

- Local provider design: `docs/copilot-local-provider-design.md`
- Freeze status: `docs/copilot-freeze-status.md`
- Context packaging policy: `docs/copilot-context-packaging-policy.md`
- Provider test plan: `docs/copilot-provider-test-plan.md`

## 8. Status wording

Local Copilot Provider Test Contract — docs-only, not implemented.
