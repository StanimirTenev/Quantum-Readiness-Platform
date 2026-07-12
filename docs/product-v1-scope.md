# QRP Product v1 — Scope

> Locks down what QRP v1 is, so future engineering work has something to map to instead of
> growing by ad hoc feature addition. See `docs/product-v1-roadmap.md` for the full phased task
> list driving this work; `docs/product-v1-acceptance-checklist.md` for the checklist this scope
> implies; `docs/adr/0001-product-v1-architecture.md` for the technical decisions.

## 1. What QRP v1 is

QRP (Quantum Readiness Platform) v1 is an **on-prem discovery / assessment / planning product**
for post-quantum cryptography readiness. It:

- discovers cryptographic assets and their dependencies;
- collects evidence safely (redacted, aggregate-only where the evidence source requires it);
- normalizes findings into a consistent shape across evidence sources;
- scores PQC/quantum risk deterministically;
- proposes migration waves and per-asset remediation tasks;
- generates operator and executive reports;
- keeps an audit trail of who did what;
- assists via a deterministic Copilot layer (no external LLM call by default);
- does **not** execute production migrations itself.

## 2. Target users

- **Security Architect / PQC lead** — runs assessments, reviews risk, approves migration plans.
- **Operator** — executes approved migration tasks outside QRP, reports back status/validation.
- **Auditor / compliance reviewer** — read-only access to evidence, risk, and audit trail.
- **Admin** — manages users, workspaces, scan scopes, and system configuration.

Not a target user in v1: an anonymous public visitor with write access, or a multi-tenant SaaS
customer self-service signup flow (see Non-goals).

## 3. Deployment mode

- **On-prem, single-node, Docker Compose** (see `infra/docker/`). Kubernetes/Helm is a later,
  explicitly deferred option, not a v1 requirement.
- PostgreSQL is the production data store (see `docs/adr/0001-product-v1-architecture.md`).
  SQLite remains supported as a local/dev-only fallback, never the production deployment target.
- No mandatory external network dependency beyond what a customer's own scan targets require
  (e.g. TLS/SSH endpoints, a repository) and, if enabled, Let's Encrypt for the optional Caddy
  reverse-proxy HTTPS termination.

## 4. Supported evidence sources

Already implemented (see the corresponding service/agent READMEs for exact contracts):

- **Network** — TLS certificate/cipher evidence, SSH algorithm-negotiation evidence, IPsec/IKEv2
  algorithm-negotiation evidence (`agents/network-scanner`).
- **Linux host** — installed crypto packages, certificate/config file indicators
  (`agents/linux-host-agent`).
- **Windows host** — aggregate, redacted certificate-store/domain-membership/service indicators
  (`agents/windows-host-agent`).
- **Repository / CI-CD** — source code and IaC crypto usage, embedded private keys, CI signing
  commands (`agents/repo-ci-scanner`).
- **Vendor/product documents** — ingested and searched for PQC readiness claims
  (`agents/doc-ingestion`, `services/retrieval-service`).
- **AD / Certificate Services estate** — fixture-validated evidence shape and full downstream
  signal/report support; no live collector yet (blocked on a lab AD environment -- see
  `docs/ad-certificate-estate-design.md`).

## 5. Supported workflows

- Ingest evidence (via agents or fixture/manual ingest) into a workspace.
- Automatic deterministic risk scoring on ingest.
- Browse assets, findings, and risk via the web console or the API.
- Ask the deterministic Copilot subagents (Risk Narrator, Discovery Analyst, Vendor Intelligence
  Analyst, Migration Planner, Change Assistant) about any asset or the platform as a whole.
- Generate and export a workspace operator report (executive summary through technical
  appendix).
- Draft a per-asset pre-change checklist and recommended migration wave for human review.

## 6. Explicit non-goals

- Not a SaaS multi-tenant platform (see the workspace model's own "not multi-tenancy" framing).
- Not a PKI / CA / KMS / HSM replacement.
- Not an autonomous remediation system -- QRP discovers, assesses, explains, and plans; it does
  not execute production changes. Trust Zone 4 integrations (CA/KMS/HSM/signing) are dry-run
  only.
- Not a scanner for arbitrary external targets without explicit scope approval.
- Not an external-LLM product by default -- the Copilot layer is deterministic; a local LLM
  adapter is a possible, disabled-by-default, later addition (Phase 10).
- No production-readiness claim and no TRL7-achieved claim (the earlier grant/TRL framing was
  deliberately removed from this repository -- see the TRL6/TRL7 cleanup work).

## 7. Security / privacy boundaries

- Evidence collection is aggregate/redacted by default wherever the source can leak sensitive
  detail (Windows host evidence, AD evidence design) -- no private keys, no passwords, no raw
  PII collected.
- No credential prompting or storage by any collector; Windows/AD collection runs under the
  invoking user's existing integrated authentication only.
- The gateway supports an optional shared API key (`QRP_API_KEY`) and an optional Public Demo
  Safety Mode (`QRP_DEMO_MODE`) that restricts the API to a fixed read-only-plus-demo-seeding
  allowlist -- see `services/api-gateway/README.md`. v1 requires moving beyond the shared key to
  real per-user authentication (Phase 3 of the roadmap).
- HTTPS is available via an opt-in Caddy reverse-proxy profile with automatic Let's Encrypt
  certificates (`infra/docker/PUBLIC_DEMO.md`) for any deployment reachable outside a trusted
  local network.

## 8. Minimum v1 capabilities

The roadmap's 43 tasks across 16 phases define the full build-out; at minimum, v1 must ship:

- Real local authentication + RBAC (not just a shared API key).
- An audit trail for every mutating action.
- A workspace/environment/asset/service/endpoint data model, not just raw per-scan assets.
- Scan scope enforcement (no arbitrary target scanning).
- Evidence provenance (what was observed, by which collector, when, at what confidence).
- Deduplicated, normalized findings across all evidence sources.
- Explainable, policy-pack-driven risk scoring.
- A migration task workflow with an approval step, not silent auto-execution.
- Exportable reports (Markdown/HTML/JSON/CSV) with evidence references and no secrets.
- A documented install/backup/restore/upgrade path.
- A documented threat model and secrets-handling policy.

## 9. Acceptance checklist

See `docs/product-v1-acceptance-checklist.md` for the full, checkable list this scope implies.
