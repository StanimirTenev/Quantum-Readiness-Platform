# Local Copilot Provider Design — docs-only, not implemented.

## 1. Purpose

This document defines a **future** local-only provider boundary for the Copilot service without implementing provider behavior in the current codebase.

It is a design package only. The active Copilot safety boundary remains disabled-provider and fail-closed.

## 2. Current state

Copilot currently supports disabled/fail-closed behavior only.

- Provider default is disabled.
- Unknown or unsupported provider values fail closed to disabled-safe behavior.
- No local LLM provider is implemented.
- No external provider is implemented.

Deterministic QRP services remain the source of truth for evidence ingest, risk scoring, and planning.

## 3. Non-goals

This design explicitly does **not** include:

- external provider integration
- OpenAI/OpenRouter/Anthropic integration
- RAG or vector database
- embeddings
- graph reasoning
- autonomous execution
- production change control
- sensitive evidence export by default

## 4. Local provider boundary

Future provider mode `local` is defined as local-only inference with explicit operator configuration.

Allowed local endpoint examples:

- `localhost`
- `127.0.0.1`
- private LAN address (RFC1918)
- explicitly configured local inference server

Rejected endpoint examples:

- public internet URL
- SaaS LLM endpoint
- unknown provider name
- missing provider config that falls back to any external service

## 5. Configuration model (future design only)

The following environment variables are proposed for a future implementation design and are not active behavior in current code:

- `COPILOT_PROVIDER=disabled|local`
- `COPILOT_LOCAL_URL`
- `COPILOT_LOCAL_TIMEOUT_SECONDS`
- `COPILOT_ALLOW_EXTERNAL=false`

Default must remain `disabled`.

## 6. URL validation policy (future design only)

Future `local` mode validation rules:

- allow `localhost`, `127.0.0.1`, and RFC1918 private IP ranges
- reject public IP addresses and public DNS names by default
- reject HTTP redirects that resolve to public networks
- fail closed on URL parse or validation errors
- never silently fall back to external providers

## 7. Context packaging policy (future design only)

What may be sent to a local provider:

- redacted summary by default
- no raw hostnames/IPs unless explicitly enabled in a future approved step
- no raw package lists unless explicitly enabled in a future approved step
- no private keys/secrets/tokens
- no full graph snapshot by default

## 8. Response contract (future-compatible)

Future provider responses should remain compatible with the current Copilot response shape:

- `answer`
- `provider_mode`
- `citations`
- `warnings`
- `used_external_provider`
- `redaction_applied`
- `metadata`

For local mode, `used_external_provider` must remain `false`.

## 9. Test plan (future tests only)

Future tests to add in a separately approved implementation step:

- missing provider config returns `disabled`
- unknown provider fails closed
- external URL rejected
- localhost URL accepted
- private LAN URL accepted
- public DNS rejected
- timeout returns safe warning
- malformed response returns safe warning
- `used_external_provider` always `false` for local mode

## 10. Implementation boundary

Actual provider implementation is out of scope for this document.

Any implementation work must be a separate, explicitly approved future step with targeted code changes and dedicated tests.

## 11. Status wording

**Local Copilot Provider Design — docs-only, not implemented.**
