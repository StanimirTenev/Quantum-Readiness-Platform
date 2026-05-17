# Known Limitations (TRL 6 Validation Context)

This document defines review-time limitations for the TRL6 readiness package and demo evidence.

## Operational limitations

- Validation is local-first and not production-ready.
- Demo and smoke scripts depend on local toolchain prerequisites (`python3`/`python`, `pytest`, shell tools).
- Any required command failure is treated as a validation failure in the related report context.
- Missing required scripts/artifacts are logged as failures under the relevant evidence/report location.

## Scope limitations

- Production authentication/authorization hardening (including production RBAC) is not implemented in this prototype scope.
- Windows agent implementation is not included in this TRL6 prototype scope.
- Real Copilot provider integration is not implemented; local/offline safety boundary remains in effect.
- Graph DB/traversal/blast-radius capabilities (including Neo4j-backed graph traversal analysis) are not implemented in this scope.

## Review/claim limitations

- TRL 6 achieved is not claimed by this package until accepted claim review/sign-off is completed.
- Production readiness is not claimed by this package.
- External review acceptance-with-limitations does not override operator sign-off requirements.

## Not implemented items

- Production hardening and operations controls beyond prototype/demo needs.
- Copilot provider runtime integration beyond disabled-safe/local-first boundaries.
- Windows collection/runtime agent parity with Linux host-agent workflows.
- Graph traversal/blast-radius runtime services and supporting graph database infrastructure.

## Follow-up actions from StravixLab

- SRX-001: document Ubuntu 24.04 `python-is-python3`/`python3` prerequisite for validation scripts.
- SRX-002: document explicit `pytest` prerequisite for validation/test flows.
- SRX-003: expand this limitations document for clearer reviewer interpretation.
- SRX-004: correct demo-bundle `status_hint` logic so contextual wording does not cause false `FAIL` hints.
- SRX-005: maintain traceability from operator/review records to StravixLab accepted-with-limitations outcome without over-claiming maturity.
