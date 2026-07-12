# QRP Product v1 — Acceptance Checklist

> The master checklist `docs/product-v1-scope.md`'s minimum capabilities imply. Mirrors
> `docs/product-v1-roadmap.md`'s Phase 16 "Product v1 Acceptance Run" master checklist --
> each top-level item below expands to that phase's own detailed `[PASS]` criteria once the
> corresponding roadmap task is implemented. Unchecked here means not yet implemented, not
> failed -- this file tracks v1 readiness as work proceeds through the roadmap, one phase at a
> time.

- [ ] **Clean install works** -- a documented, from-scratch `docker compose` install on a clean
      server succeeds (Phase 13).
- [ ] **Authentication / RBAC works** -- real local login (not just a shared API key), four
      roles (Admin, Security Architect, Operator, Auditor) enforced on every route (Phase 3).
- [ ] **Workspace / environment / asset model works** -- evidence, findings, and reports are
      workspace-scoped; assets have an environment; no cross-workspace data leakage (Phase 2).
- [ ] **Scan scopes enforced** -- no target can be scanned unless it is in an approved scope;
      excluded targets always win (Phase 4).
- [ ] **Scan jobs / worker queue works** -- scans run as queued jobs, not synchronously inside
      an API request; job status/logs are visible (Phase 4).
- [ ] **Agents enroll and send evidence** -- Linux/Windows agents register with an identity
      (not just an anonymous script run) and send evidence under that identity (Phase 5).
- [ ] **Evidence provenance works** -- every finding traces back to what was observed, by which
      collector, when, and at what confidence (Phase 6).
- [ ] **Finding deduplication works** -- repeated scans update `last_seen`, not create
      duplicates; findings can be marked accepted-risk/false-positive with a reason (Phase 6).
- [ ] **Risk / policy works** -- risk scoring is explainable (drivers, evidence references,
      policy rule, confidence) and policy packs are selectable per workspace (Phase 7).
- [ ] **Planner / migration tasks work** -- tasks go through propose -> approve -> execute
      (outside QRP) -> validate -> audit, never silently auto-approved (Phase 8).
- [ ] **Audit log works** -- every mutating action is logged with actor/timestamp/before-after;
      failed authorization attempts are logged too; the log itself is read-only (Phase 3).
- [ ] **Reports export** -- Markdown/HTML/JSON/CSV exports work, contain evidence references,
      and never contain secrets or private key material (Phase 12).
- [ ] **Backup / restore works** -- a backup artifact can be restored to a clean environment and
      the restored system can log in and see its reports/evidence (Phase 13).
- [ ] **Upgrade migration works** -- a versioned schema migration from one release to the next
      is tested, with a visible failure mode and documented rollback (Phase 13).
- [ ] **Security tests pass** -- threat model documented, no secrets in logs/reports/fixtures,
      CI secret scanning passes, rate/size/concurrency limits enforced (Phase 14).
- [ ] **Lab validation passes** -- each evidence source (Linux, Windows, TLS, SSH, Repo/IaC,
      AD/CA, document ingestion) has a fixture and a live lab validation run producing a report
      (Phase 15). AD/CA lab validation specifically requires a lab Windows Server + AD DS + AD CS
      environment not yet available -- see `docs/ad-certificate-estate-design.md`.

## Non-claims (must stay true throughout v1)

- [ ] No production-readiness claim anywhere in shipped docs/UI copy.
- [ ] No autonomous-remediation claim -- QRP never executes a production change itself.
- [ ] No TRL7-achieved claim.
- [ ] No claim of arbitrary/unscoped scanning capability.
