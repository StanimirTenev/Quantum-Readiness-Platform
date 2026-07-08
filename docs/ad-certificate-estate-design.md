# AD / Certificate Estate Discovery — Design

## Purpose

This document expands `docs/cross-platform-agent-design.md` §8 ("AD/certificate
estate future design") into a concrete safety contract and evidence shape for
future domain-level PKI discovery. **Design only — no collector, no ingest
changes, no risk/planning changes are implemented by this document.** It
follows the same before-code-design discipline used for the Windows host
evidence vertical (`windows-evidence-fixture-contract.md`,
`inventory-windows-evidence-acceptance-design.md`,
`windows-risk-planning-signal-mapping-design.md`), consolidated into one
document since this is a single upfront design pass (backlog §7B, Phase 6 in
the cross-platform doc), not an incremental multi-session build yet.

## Why domain-level evidence, not just per-host

`agents/windows-host-agent/collect.ps1` sees only certificates already
installed in one host's local store. It cannot see:

- How many Certificate Authorities exist in the forest, or whether their own
  certificates are expiring.
- Which certificate **templates** are configured and what algorithm/key-size
  they mandate. A weak template is higher-leverage than a single weak leaf
  certificate — every certificate issued from it going forward inherits the
  weakness, until the template itself is fixed.
- Domain/forest functional level, which bounds available crypto agility (e.g.
  for Kerberos PKINIT).

This is the gap Phase 6 of the cross-platform design leaves open.

## Non-goals (explicit)

- No AD scanner implementation in this task — design only.
- No credential prompting or storage. Collection runs under the invoking
  user's existing Windows-integrated authentication only, same principle as
  `collect.ps1` (which never prompts for or stores credentials).
- No requirement for elevated/admin AD rights. If a check needs elevated
  access, it is optional/best-effort and omitted with a warning, never a hard
  requirement — matches the project's existing "reliable vs best-effort"
  boundary (see README §4).
- No per-user object enumeration. No user accounts, group memberships, OUs,
  or any PII-bearing AD objects. Scope is strictly PKI infrastructure objects
  (CAs, certificate templates) and domain/forest topology metadata.
- No LDAP crawling of arbitrary containers. Bounded to the well-known PKI
  container (`CN=Public Key Services,CN=Services,CN=Configuration,...`) and
  the domain/forest root objects only.
- No private key access (not obtainable via AD queries regardless, stated
  explicitly for consistency with the other design docs).
- No modification of any AD object — strictly read-only queries.
- No remote execution against other hosts. Runs locally against AD via LDAP;
  does not connect to remote CA servers beyond their AD-published objects.
- No secret/credential extraction.
- No automatic/scheduled execution. Explicit opt-in invocation only, same as
  the Windows host collector.
- No production-AD dry run as part of implementation without explicit
  operator sign-off — a lab/test AD environment is the default target for
  Phase 6b (see below), given this touches shared domain infrastructure
  rather than a single host.

## Safety / privacy boundaries (aggregate-only)

Mirrors `docs/cross-platform-agent-design.md` §12 and the redaction pattern
already shipped in `windows-evidence-fixture-contract.md`:

- **Domain name:** redacted by default (`domain_name_redacted: true`, same
  field already used at host level).
- **CA names/hostnames:** redacted by default — aggregate counts and boolean
  indicators only, no raw CA server names in default output
  (`ca_names_redacted: true`).
- **Certificate template names:** aggregate summary only by default (counts,
  not a raw name list) — template names can reveal internal naming/org
  structure (`template_names_redacted: true`).
- **No LDAP bind credentials stored or logged** — always the current
  process's integrated Windows authentication.
- **Bounded object count** — a cap on templates/CAs enumerated per run
  (mirrors `-MaxCerts` on `collect.ps1`), so a large forest cannot turn a
  "discovery" run into an unbounded query.
- **Structural metadata only** — only a certificate template's configured key
  algorithm/size/validity attributes are read, never any issued certificate's
  actual subject or content.

## Evidence categories (proposed, additive — no schema changes yet)

```json
{
  "ad_evidence": {
    "domain_topology_indicators": {
      "forest_present": true,
      "domain_functional_level_observed": true,
      "forest_functional_level_observed": true,
      "domain_controllers_count": 2,
      "domain_name_redacted": true
    },
    "ca_presence_indicators": {
      "enterprise_cas_observed_count": 1,
      "standalone_ca_indicators_observed": false,
      "root_ca_certificates_expiring_count": 0,
      "ca_names_redacted": true
    },
    "certificate_template_indicators": {
      "templates_observed_count": 14,
      "templates_with_weak_key_algorithm_count": 2,
      "templates_with_weak_signature_algorithm_count": 1,
      "templates_expiring_soon_count": 0,
      "template_names_redacted": true
    },
    "warnings": [],
    "errors": []
  }
}
```

`warnings` carries best-effort gaps (e.g.
`"active_directory_module_not_available"`,
`"insufficient_permissions_for_pki_container"`) rather than failing the whole
collection, matching the existing collector's degrade-gracefully behavior.

## Collection mechanism (conceptual)

- Ships as an opt-in extension of the existing Windows collector philosophy —
  either a flag on `collect.ps1` (e.g. `-ScanAD`) or a separate opt-in script.
  Which of the two is an implementation-time decision, not fixed here.
- Uses the built-in `ActiveDirectory` PowerShell module (RSAT) if present. If
  absent, all `ad_evidence` fields are omitted with
  `warnings: ["active_directory_module_not_available"]` — best-effort, not a
  hard dependency.
- PKI container query follows the standard, well-known, read-only path:
  `Get-ADObject -SearchBase "CN=Public Key Services,CN=Services,CN=Configuration,<domain DN>"`,
  bounded by a `-MaxTemplates`/`-MaxCAs` cap.
- Certificate template algorithm/key-size read from the template object's
  published attributes (e.g. `msPKI-Minimal-Key-Size`) — structural metadata
  only.

## Ingest / risk / planning integration (conceptual, no code)

- Extends the existing Windows host ingest contract with an `ad_evidence`
  block (shape above), or persists as its own scan representing "the domain"
  as an asset — exact modeling is an implementation-time decision.
- risk-engine mapping should follow the same pattern as
  `WINDOWS_SIGNAL_WEIGHTS`: a new signal family (e.g.
  `ad_weak_certificate_template`) with weight reflecting that a weak template
  is higher-leverage than a single weak leaf certificate (exact weight TBD at
  implementation).
- planner-service should read the resulting rationale flags the same way it
  already reads `windows_domain_controller` etc.
- `tools/report/build_operator_report.py`'s `persisted_risk` bundle shape
  (added 2026-07-08 for the Windows host) already generalizes to any
  aggregate-signal-scored asset, so an AD/domain entry should fit it without
  further changes to that tool.

## Phased implementation plan (for whenever this is picked up)

- **Phase 6a** — Fixture-only contract validation (mirrors Windows host
  Phases 1–3): formalize the shape above with a committed fixture + a
  contract test, no live collector yet.
- **Phase 6b** — Minimal read-only collector, exercised against a lab/test AD
  environment only (see Non-goals — no production AD without operator
  sign-off).
- **Phase 6c** — Inventory ingest acceptance (mirrors
  `inventory-windows-evidence-acceptance-design.md`).
- **Phase 6d** — Risk/planning signal mapping (mirrors
  `windows-risk-planning-signal-mapping-design.md`).
- **Phase 6e** — E2E smoke using the fixture (mirrors
  `run_windows_evidence_smoke.ps1` / `.sh`).

## Status

AD / Certificate Estate Discovery — design-only (2026-07-08). No collector,
no ingest changes, no risk/planning changes are implemented. This document is
the safety contract and evidence shape future implementation must follow;
`docs/cross-platform-agent-design.md` §8/Phase 6 point here for the expanded
version.
