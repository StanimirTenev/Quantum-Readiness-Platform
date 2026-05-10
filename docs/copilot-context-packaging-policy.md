# Copilot Context Packaging Policy

## Purpose

This document defines how future Copilot requests should package context from QRP data.

This is a design document only.
No Copilot implementation is included.
No prompt templates are implemented.
No RAG/vector store is introduced.
No external LLM provider is configured.
No raw evidence is sent by default.

## Relationship to Existing Copilot Docs

Reference:
- docs/copilot-local-first-design.md
- docs/copilot-provider-test-plan.md

The local-first design defines the provider boundary.
The provider test plan defines future provider tests.
This document defines safe context packaging and a summary-only prompt policy.

## Core Policy

Copilot should receive summarized context first, not raw evidence by default.

Default context mode:

summary_only

Raw evidence mode:

explicit_operator_allowed_only

External provider mode:

summary_only_plus_redaction_required

## Context Sensitivity Levels

### public_safe

Safe for generic text, with no infrastructure details.

Examples:
- generic PQC explanation
- general migration checklist

### internal_summary

Summarized internal context without raw sensitive details.

Examples:
- "production service has weak RSA key"
- "three certificate indicators found"
- "asset assigned to wave_1 due to urgency"

### sensitive_evidence_ref

References to internal evidence IDs, scan IDs, graph nodes, or findings.

Examples:
- evidence_ref
- graph node ID
- scan ID
- finding ID

### raw_sensitive

Raw infrastructure details.

Examples:
- hostnames
- IP addresses
- file paths
- package lists
- certificate fingerprints
- raw configs
- graph snapshots
- logs

Policy:
- public_safe may be sent to any configured provider.
- internal_summary may be sent to local provider by default.
- sensitive_evidence_ref stays local by default.
- raw_sensitive is blocked by default.
- external provider may receive only redacted summary context unless operator explicitly allows more.

## Context Package Shape

Define future context package:

```json
{
  "context_mode": "summary_only|evidence_refs|raw_allowed",
  "provider_mode": "disabled|local|external",
  "query": "string",
  "risk_summary": {
    "score": 0,
    "rating": "string",
    "confidence_score": 0,
    "risk_dimensions": {
      "exposure": 0,
      "impact": 0,
      "urgency": 0,
      "migration_complexity": 0
    },
    "reasons": []
  },
  "planner_summary": {
    "wave": "string",
    "priority_score": 0,
    "planning_reasons": []
  },
  "graph_summary": {
    "node_count": 0,
    "edge_count": 0,
    "warning_count": 0,
    "key_relationships": []
  },
  "evidence_refs": [],
  "raw_evidence": null,
  "redaction": {
    "redaction_required": true,
    "redaction_applied": true,
    "blocked_fields": []
  },
  "sensitivity": {
    "contains_sensitive_data": true,
    "allowed_external": false
  }
}
```

## Summary-Only Prompt Policy

By default, future Copilot prompts must include:
- user question
- risk summary
- planner summary
- graph summary
- evidence references only if needed
- warnings about missing context

By default, future Copilot prompts must not include:
- raw hostnames
- raw IP addresses
- raw file paths
- raw package lists
- raw certificate fingerprints
- raw graph snapshots
- raw configs
- raw logs
- private keys
- secrets
- tokens

## Context Source Mapping

Map current QRP outputs to safe Copilot context.

| Source | Raw Data | Summary Context | Default Mode |
|---|---|---|---|
| risk-engine | normalized_score_100; confidence_score; risk_dimensions; stage2_signals; rationale | score/rating; confidence; dimensions; concise reasons | internal_summary |
| planner-service | wave; priority_score; planning_reasons | assigned wave; why scheduled early/late; migration priority explanation | internal_summary |
| graph projection | graph-snapshot.json; node IDs; edge IDs; warnings | node/edge/warning counts; key relationship types; selected evidence path summary | internal_summary; evidence_refs local only |
| inventory-service | assets; scans; raw evidence | asset class; environment; criticality; evidence availability | summary_only |
| evidence artifacts | reports/evidence/latest/*.json | evidence categories found; evidence counts; validation status | summary_only |

## Redaction and Blocking Rules

Always block:
- private keys
- secrets
- passwords
- tokens
- API keys
- credentials

Redact by default:
- hostnames
- IP addresses
- FQDNs
- file paths
- owner/team names
- certificate fingerprints
- graph node IDs
- scan IDs
- raw config snippets

Summarize instead:
- package lists
- graph neighborhoods
- certificate chains
- scan findings
- risk findings
- migration plans

## External Provider Context Rules

If provider_mode=external:

Allowed by default:
- public_safe
- redacted internal_summary

Blocked by default:
- sensitive_evidence_ref
- raw_sensitive
- graph snapshots
- scan artifacts
- raw configs
- logs
- owner/team metadata
- certificate fingerprints

Required:
- allowed_external=true
- redaction_applied=true
- used_external_provider=true in response
- provider mode visible to operator

## Local Provider Context Rules

If provider_mode=local:

Allowed by default:
- internal_summary
- redacted evidence_refs if needed
- graph summaries

Still blocked by default:
- private keys
- secrets
- tokens
- passwords
- raw credentials

Raw evidence:
- only allowed when explicitly requested/configured
- should be auditable

## Disabled Provider Context Rules

If provider_mode=disabled:

- no prompt is sent anywhere
- no context package leaves process
- deterministic disabled response returned
- context may be summarized internally for report/debug only if safe

## Prompt Construction Rules

Future prompt construction should use:

1. system boundary message:
   - Copilot is advisory only
   - deterministic core is source of truth
   - do not invent facts
   - cite local evidence refs when available

2. user question

3. context summary:
   - risk summary
   - planner summary
   - graph summary
   - evidence refs

4. explicit uncertainty:
   - missing evidence
   - low confidence
   - unknown relationships

Do not include raw evidence unless context_mode=raw_allowed.

## Refusal / Safe Response Rules

Copilot should refuse or limit output when:

- user asks to execute production changes directly
- user asks to rotate keys/certificates without approval
- user asks to bypass approval
- required evidence is missing
- provider mode does not allow requested data sharing
- request would expose raw_sensitive data externally

## Logging Rules

Log:
- request_id
- provider_mode
- context_mode
- redaction_required
- redaction_applied
- allowed_external
- used_external_provider

Do not log by default:
- full prompts with sensitive context
- full raw evidence
- secrets/private keys
- full graph snapshot
- full raw configs

## Future Test Cases

1. summary_only context excludes raw hostnames/IPs/file paths.
2. external mode blocks raw_sensitive context.
3. local mode allows internal_summary.
4. disabled mode sends no context.
5. private keys/secrets are always blocked.
6. evidence_refs are included only when allowed.
7. graph snapshot is summarized, not sent raw.
8. redaction_applied is true when sensitive data exists.
9. missing evidence creates uncertainty warning.
10. prompt includes deterministic-core source-of-truth instruction.

## Non-Goals

- no Copilot implementation now
- no prompt template implementation now
- no LLM client now
- no RAG/vector DB now
- no external provider integration now
- no embedding model now
- no UI changes now
- no auth/RBAC now
- no production deployment now

## Recommended Next Step

"Copilot Design Task 4 — Define local-first Copilot implementation boundary and disabled-provider stub plan."
