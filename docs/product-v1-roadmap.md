# QRP Product v1 — пълен план за довършване точка по точка

> Цел: да преминем от демо/prototype към завършен on-prem Product v1.
>
> Този документ умишлено НЕ включва DARMI / field validation. Засега редът е:
>
> ```text
> scope → foundation → auth/RBAC → data model → scan jobs → agents → evidence → risk/policy → workflow → graph → reports → backup/restore → security → lab validation → release
> ```

---

## 0. Основно правило за Product v1

QRP v1 трябва да бъде **on-prem discovery / assessment / planning продукт**.

QRP v1:

```text
- открива cryptographic assets и dependencies;
- събира evidence безопасно;
- нормализира findings;
- оценява PQC/quantum risk;
- предлага migration waves;
- генерира reports;
- пази audit trail;
- помага чрез deterministic Copilot;
- не изпълнява production migration сам.
```

QRP v1 НЕ е:

```text
- SaaS multi-tenant платформа;
- PKI / CA / KMS / HSM заместител;
- autonomous remediation система;
- scanner за произволни външни targets без scope approval;
- външен LLM продукт по подразбиране;
- production-ready claim без реален acceptance процес.
```

---

# Phase 1 — Product Definition

## 1. Product v1 Scope Document

### Цел

Да се заключи какво точно е QRP v1, за да не се добавят хаотично функции.

### Файлове

```text
docs/product-v1-scope.md
docs/product-v1-acceptance-checklist.md
```

### Да съдържа

```text
1. What QRP v1 is
2. Target users
3. Deployment mode
4. Supported evidence sources
5. Supported workflows
6. Explicit non-goals
7. Security/privacy boundaries
8. Minimum v1 capabilities
9. Acceptance checklist
```

### Non-goals да са ясни

```text
- no autonomous remediation
- no production CA/KMS/HSM execution
- no external LLM by default
- no production-ready claim
- no TRL7 achieved claim
- no arbitrary public scanning
```

### Acceptance

```text
[PASS] има ясно v1 scope
[PASS] има acceptance checklist
[PASS] няма production-ready claim
[PASS] няма autonomous remediation claim
[PASS] всички бъдещи задачи могат да се мапнат към v1 scope
```

---

## 2. Product Architecture Decision Record

### Цел

Да се документира техническото решение за v1.

### Файлове

```text
docs/adr/0001-product-v1-architecture.md
```

### Решение за v1

```text
Deployment:
- on-prem
- Docker Compose single-node first
- Kubernetes/Helm later

Database:
- Postgres
- SQLite only for local/dev fallback if still needed

Auth:
- local users + sessions/JWT
- OIDC later

Graph:
- persistent graph in Postgres first
- Neo4j later only if needed

Copilot:
- deterministic by default
- local LLM optional later, disabled by default

Execution:
- no production-changing actions
- workflows generate tasks/checklists/exports only
```

### Acceptance

```text
[PASS] architecture choices documented
[PASS] later/larger features are explicitly deferred
[PASS] engineering sequence is clear
```

---

# Phase 2 — Database and Domain Model

## 3. Schema Migrations

### Цел

Postgres schema да стане versioned и upgradeable.

### Да се направи

```text
- Add Alembic or equivalent migration system.
- Stop relying on implicit table creation in production mode.
- Add migration command to Makefile.
- Add migration smoke test.
```

### Примерни команди

```bash
make db-migrate
make db-check
```

### Acceptance

```text
[PASS] clean Postgres DB може да се създаде чрез migrations
[PASS] existing DB може да се upgrade-не
[PASS] CI пуска migration check
[PASS] production mode не създава silently schema без migration
```

---

## 4. Workspace / Environment / Asset Model

### Цел

Да се изчисти основният data model.

### Минимален v1 model

```text
Organization / Installation
Workspace
Environment
Asset
Service
Endpoint
Scan
Evidence
Finding
RiskRecord
MigrationWave
MigrationTask
Report
AuditEvent
```

### Relationships

```text
Workspace → Environment
Environment → Asset
Asset → Service
Service → Endpoint
Scan → Evidence
Evidence → Finding
Finding → RiskRecord
RiskRecord → MigrationWave
Finding/RiskRecord → MigrationTask
Workspace → Report
All mutations → AuditEvent
```

### Acceptance

```text
[PASS] всяко evidence принадлежи към workspace
[PASS] всяко asset има environment
[PASS] findings са свързани с asset/service/endpoint когато е възможно
[PASS] reports са workspace-scoped
[PASS] няма глобално смесване на данни между workspaces
```

---

## 5. Service / Endpoint Normalization

### Цел

Да не виждаме само raw assets, а реални services/endpoints.

### Да се направи

```text
- Normalize network scan results to endpoints.
- Normalize host agent results to services/packages.
- Normalize repo scan results to repository/pipeline/service context.
- Link endpoint → service → asset where possible.
```

### Acceptance

```text
[PASS] TLS endpoint се вижда като endpoint
[PASS] SSH endpoint се вижда като endpoint
[PASS] repo finding се вижда като repository/pipeline context
[PASS] asset detail показва services/endpoints, не само raw scan data
```

---

# Phase 3 — Authentication, RBAC, Audit

## 6. Local Authentication

### Цел

QRP v1 да има реален login, не само shared API key.

### Минимално

```text
- local admin user
- password hash
- session cookie or JWT
- login/logout
- password change
- bootstrap admin creation
```

### Да НЕ се прави още

```text
- full SaaS accounts
- multi-tenant billing
- SSO/OIDC като задължителна част
```

### Acceptance

```text
[PASS] първият admin може да се създаде безопасно
[PASS] login работи
[PASS] logout работи
[PASS] password не се пази plaintext
[PASS] API key не е единствената защита
```

---

## 7. RBAC v1

### Роли

```text
Admin
Security Architect
Operator
Auditor
```

### Права

```text
Admin:
- manage users
- manage workspaces
- configure scan scopes
- manage system settings

Security Architect:
- create scan jobs
- view evidence/risk
- approve migration plan
- generate reports

Operator:
- view assigned tasks
- update task status
- attach validation notes

Auditor:
- read-only access to reports, evidence, audit logs
```

### Acceptance

```text
[PASS] unauthorized user cannot access API
[PASS] Auditor cannot create scans
[PASS] Operator cannot change system config
[PASS] Admin can manage users
[PASS] route permissions tested
```

---

## 8. Audit Log Foundation

### Цел

Всеки важен action да има следа.

### Audit event fields

```text
id
timestamp
actor_user_id
actor_role
workspace_id
action
resource_type
resource_id
source_ip
request_id
before/after summary for mutations
result: success/failure
```

### Actions to log

```text
login/logout
user creation/update
workspace creation/update
scan scope changes
scan job creation
evidence ingest
risk recalculation
task approval/status change
report generation/export
settings changes
```

### Acceptance

```text
[PASS] всяка mutation пише audit event
[PASS] failed authorization се логва
[PASS] audit log се вижда в UI за Admin/Auditor
[PASS] audit log е read-only
```

---

# Phase 4 — Scan Scope and Job Orchestration

## 9. Scan Scope Manager

### Цел

Да не може произволен потребител да scan-ва произволен IP/domain.

### Data model

```text
ScanScope
- workspace_id
- allowed_cidr_ranges
- allowed_domains
- excluded_targets
- allowed_scan_types
- scan_windows
- rate_limits
- created_by
- approved_by
```

### Rules

```text
- всяко target трябва да е в approved scope
- excluded target винаги печели
- internet-wide scan забранен
- scope changes require Admin/Security Architect
```

### Acceptance

```text
[PASS] scan към allowed target се приема
[PASS] scan към disallowed target се отказва
[PASS] excluded target се отказва дори да е в CIDR
[PASS] scope change се audit-ва
```

---

## 10. Scan Job Model

### Цел

Long-running scans да не се изпълняват директно в API request.

### Model

```text
ScanJob
- id
- workspace_id
- scan_type
- targets
- status: queued/running/succeeded/failed/cancelled
- created_by
- created_at
- started_at
- finished_at
- logs
- result_summary
```

### Acceptance

```text
[PASS] API създава queued job
[PASS] worker взима job
[PASS] status се вижда в UI
[PASS] logs се пазят
[PASS] failed job има error summary
[PASS] job може да бъде cancelled ако още не е приключил
```

---

## 11. Worker Queue v1

### Варианти

За v1 избери прост подход:

```text
Option A: Postgres-backed queue
Option B: lightweight worker service
Option C: RQ/Celery later
```

Препоръка за v1:

```text
Postgres-backed queue + one worker container
```

### Acceptance

```text
[PASS] worker стартира с Docker Compose
[PASS] worker обработва queued scans
[PASS] retry/failed state работи
[PASS] API не блокира дълго при scan start
```

---

# Phase 5 — Agent Management

## 12. Agent Enrollment

### Цел

Linux/Windows agents да не са просто scripts, а управлявани agents.

### Model

```text
Agent
- id
- workspace_id
- enrollment_token_id
- hostname_hash or redacted host id
- os_type
- agent_version
- capabilities
- last_seen
- status
```

### Enrollment flow

```text
1. Admin/Security Architect creates enrollment token.
2. Agent is installed with token.
3. Agent registers itself.
4. Gateway returns agent_id and config.
5. Agent sends evidence using agent identity.
```

### Acceptance

```text
[PASS] enrollment token може да се създаде
[PASS] token може да се revoke-не
[PASS] agent register работи
[PASS] last_seen се обновява
[PASS] unsupported agent version се маркира
```

---

## 13. Agent Security

### Изисквания

```text
- no private key collection
- redaction before send
- signed/encrypted transport through HTTPS
- token never printed in logs
- agent config file permissions documented
- uninstall instructions
```

### Acceptance

```text
[PASS] token не се логва
[PASS] evidence е redacted преди ingest
[PASS] agent version се вижда в UI
[PASS] uninstall procedure exists
```

---

## 14. Agent Packages

### Цел

Клиентът да може да инсталира agents без ръчно ровене.

### Deliverables

```text
Linux:
- binary
- config example
- systemd unit
- install.sh
- uninstall.sh

Windows:
- collect.ps1 or agent package
- install instructions
- scheduled task option
- uninstall instructions
```

### Acceptance

```text
[PASS] Linux agent се инсталира чрез script
[PASS] Linux agent може да се пусне като systemd service/timer
[PASS] Windows collector има ясна инструкция
[PASS] agent package version е видима
```

---

# Phase 6 — Evidence, Findings, Provenance

## 15. Evidence Schema Versioning

### Цел

Evidence payload-ите да са стабилни и версионирани.

### Required fields

```json
{
  "schema_version": "1.0",
  "source": "network|host|windows|repo|doc|ad_certificate_estate",
  "collector_version": "0.1.0",
  "workspace_id": "...",
  "asset_ref": "...",
  "collected_at": "...",
  "redaction_level": "safe",
  "evidence": {}
}
```

### Acceptance

```text
[PASS] всеки source има schema_version
[PASS] collector_version се пази
[PASS] collected_at се пази
[PASS] redaction_level се пази
[PASS] invalid schema се отказва с ясна грешка
```

---

## 16. Evidence Provenance

### UI/report трябва да показва

```text
What was observed?
Where was it observed?
Which collector found it?
When was it collected?
What confidence?
What redaction level?
Which risk/finding uses it?
```

### Acceptance

```text
[PASS] всяко finding сочи към evidence
[PASS] report има evidence references
[PASS] Copilot отговор има “based on” references
[PASS] evidence може да се audit-не назад до scan/job/agent
```

---

## 17. Finding Normalization

### Цел

Различни scanners да произвеждат единен finding model.

### Finding fields

```text
id
workspace_id
asset_id
service_id optional
endpoint_id optional
source
category
algorithm
location
severity
confidence
evidence_ids
first_seen
last_seen
status
```

### Categories

```text
classical_crypto
weak_key
expired_certificate
expiring_certificate
weak_ssh_algorithm
embedded_private_key
repo_signing_dependency
vendor_blocker
adcs_template_risk
unknown_crypto_dependency
```

### Acceptance

```text
[PASS] TLS RSA finding влиза в normalized finding
[PASS] SSH weak KEX finding влиза в normalized finding
[PASS] repo embedded key finding влиза в normalized finding
[PASS] Windows cert-store finding влиза в normalized finding
[PASS] duplicate finding не се създава при повторен scan
```

---

## 18. Finding Deduplication

### Правило

Dedup key:

```text
workspace + asset + service/endpoint/location + category + algorithm/rule
```

### States

```text
open
accepted_risk
planned
in_progress
resolved
false_positive
```

### Acceptance

```text
[PASS] repeated scan updates last_seen
[PASS] resolved finding може да се reopen-не ако се появи пак
[PASS] false positive се пази с причина
[PASS] dedup logic има tests
```

---

# Phase 7 — Risk and Policy Engine v1

## 19. Policy Packs

### Цел

Risk логиката да не е hardcoded само в код.

### Policy packs

```text
Default PQC Readiness
Strict Regulated Environment
Financial Services
Critical Infrastructure
```

### Policy config example

```yaml
name: Default PQC Readiness
risk_weights:
  rsa_2048: high
  rsa_3072: medium
  ecdsa_p256: high
  expired_certificate: high
  weak_ssh_kex: high
  embedded_private_key: critical
  adcs_exportable_template: high
```

### Acceptance

```text
[PASS] workspace може да избере policy pack
[PASS] risk-engine използва policy pack
[PASS] policy rule се показва в explanation
[PASS] tests покриват поне 2 policy packs
```

---

## 20. Risk Explainability

### Всяко risk score трябва да показва

```text
score
rating
drivers
evidence references
policy rules
recommended wave
confidence
```

### Acceptance

```text
[PASS] asset detail показва drivers
[PASS] report показва drivers
[PASS] Copilot не измисля причини извън rationale/evidence
[PASS] risk score може да се trace-не до evidence
```

---

## 21. Risk History

### Цел

Да се вижда прогрес.

### Да показва

```text
risk trend over time
new findings
resolved findings
wave movement
coverage change
```

### Acceptance

```text
[PASS] repeated scans пазят history
[PASS] risk trend се вижда в asset detail
[PASS] workspace dashboard има overall risk trend
```

---

# Phase 8 — Migration Workflow v1

## 22. Migration Task Model

### Model

```text
MigrationTask
- id
- workspace_id
- asset_id
- finding_id
- wave
- owner
- status
- due_date
- checklist
- evidence_links
- created_by
- approved_by
```

### Statuses

```text
proposed
approved
in_progress
blocked
validated
accepted
deferred
```

### Acceptance

```text
[PASS] planner може да предложи task
[PASS] Security Architect може да approve-не task
[PASS] Operator може да update-не status
[PASS] Auditor може да view-не task без mutation
```

---

## 23. Approval Flow

### Минимален flow

```text
Planner proposes task.
Security Architect approves.
Operator executes outside QRP.
Operator marks validated.
Auditor reviews evidence.
```

### Acceptance

```text
[PASS] proposed task не е автоматично approved
[PASS] approval се audit-ва
[PASS] status change се audit-ва
[PASS] QRP не изпълнява production changes
```

---

## 24. Export Integrations v1

### Първо само exports

```text
CSV export
Markdown export
JSON export
Jira-ready CSV
GitHub Issues markdown draft
```

### Не още

```text
- direct Jira write
- ServiceNow write
- GitHub issue creation
```

### Acceptance

```text
[PASS] migration tasks могат да се export-нат
[PASS] export не съдържа secrets
[PASS] export има evidence links/references
```

---

# Phase 9 — Persistent Graph v1

## 25. Graph in Postgres

### Цел

Да се премине от само snapshot/in-memory към persistent graph.

### Tables

```text
graph_nodes
graph_edges
```

### Node types

```text
Asset
Service
Endpoint
Certificate
CA
Library
Pipeline
VendorProduct
PolicyRule
MigrationTask
```

### Edge types

```text
RUNS_ON
EXPOSES
USES_CERTIFICATE
SIGNED_BY
DEPENDS_ON
BLOCKED_BY
AFFECTS
HAS_FINDING
HAS_EVIDENCE
```

### Acceptance

```text
[PASS] scan ingest updates graph nodes/edges
[PASS] graph is workspace-scoped
[PASS] duplicate nodes are deduped
[PASS] graph queries still work
```

---

## 26. Read-only Graph Queries

### Queries

```text
blast radius
trust chain
evidence path
vendor blocker path
service dependency path
certificate dependency path
```

### Acceptance

```text
[PASS] blast radius works from asset
[PASS] trust chain works from certificate/CA
[PASS] evidence path works from finding
[PASS] UI shows graph context
```

---

# Phase 10 — Copilot Productization

## 27. Copilot with Citations

### Цел

Copilot да е audit-friendly.

### Всеки Copilot отговор да има

```text
answer
evidence_used
risk_records_used
documents_used
confidence
limitations
recommended_next_action
```

### Acceptance

```text
[PASS] Risk Narrator показва evidence references
[PASS] Discovery Analyst показва sources
[PASS] Vendor Intelligence показва document citations
[PASS] Change Assistant не предлага production execution
```

---

## 28. Optional Local LLM Adapter Later

### Не в първи product-hardening sprint

Само след deterministic Copilot стабилизация:

```text
Ollama/local provider
disabled by default
no external provider by default
no execution permission
customer-approved documents only
```

### Acceptance, когато се прави

```text
[PASS] deterministic fallback works
[PASS] LLM output cannot execute actions
[PASS] citations required
[PASS] no external call unless explicitly configured
```

---

# Phase 11 — UI v1

## 29. Product UI Navigation

### Sections

```text
Dashboard
Workspaces
Assets
Services
Findings
Graph
Migration Plan
Tasks
Reports
Admin
Settings
Audit Log
Copilot
```

### Acceptance

```text
[PASS] user can navigate without raw API knowledge
[PASS] role-based UI hides unauthorized actions
[PASS] dashboard is workspace-aware
```

---

## 30. Asset Detail Screen

### Tabs

```text
Overview
Services / Endpoints
Findings
Evidence
Risk History
Migration Plan
Tasks
Copilot
Graph Context
```

### Acceptance

```text
[PASS] asset detail answers “what is risky?”
[PASS] shows where finding is located
[PASS] shows why it matters
[PASS] shows recommended wave/action
[PASS] links to evidence
```

---

## 31. Executive View

### Shows

```text
top risks
risk trend
coverage %
wave summary
vendor blockers
open/blocked tasks
progress over time
```

### Acceptance

```text
[PASS] CISO can understand risk without raw JSON
[PASS] summary is exportable
[PASS] no misleading production readiness claim
```

---

# Phase 12 — Reports v1

## 32. Report Builder

### Report types

```text
Executive Summary
Technical Findings
Migration Plan
Evidence Appendix
Workspace Export
```

### Sections

```text
1. Executive Summary
2. Scope and Coverage
3. Top Risks
4. Findings by Asset/Service
5. Migration Waves
6. Vendor Blockers
7. Open Tasks
8. Evidence References
9. Boundaries / Non-Claims
10. Technical Appendix
```

### Acceptance

```text
[PASS] report can be generated per workspace
[PASS] report has evidence references
[PASS] report has boundary section
[PASS] report has no secrets/private keys
```

---

## 33. Export Formats

### Minimum

```text
HTML
Markdown
JSON evidence bundle
CSV findings
CSV migration tasks
```

### Later

```text
PDF
DOCX
signed evidence bundle
```

### Acceptance

```text
[PASS] Markdown export works
[PASS] HTML export works
[PASS] JSON evidence export works
[PASS] CSV findings export works
```

---

# Phase 13 — Installation, Backup, Upgrade

## 34. Installation Package

### v1 install mode

```text
Docker Compose single-node
```

### Files

```text
infra/docker/.env.example
infra/docker/README.md
docs/install.md
docs/admin-guide.md
docs/operator-guide.md
```

### Acceptance

```text
[PASS] clean server install works from documented steps
[PASS] all required env vars documented
[PASS] no default weak secrets in production config
```

---

## 35. Backup / Restore

### Scope

```text
Postgres DB
uploaded documents
evidence files if stored outside DB
reports
config
```

### Commands

```bash
make backup
make restore BACKUP=<file>
make restore-smoke
```

### Acceptance

```text
[PASS] backup creates usable artifact
[PASS] restore to clean environment works
[PASS] restored system can login
[PASS] restored reports/evidence are available
```

---

## 36. Upgrade Path

### Required

```text
versioned releases
schema migrations
release notes
upgrade guide
rollback notes
```

### Acceptance

```text
[PASS] v1.0.0 → v1.0.1 migration tested
[PASS] migration failure is visible
[PASS] rollback instructions exist
```

---

# Phase 14 — Security Hardening

## 37. Threat Model

### File

```text
docs/security-threat-model.md
```

### Must cover

```text
malicious user
compromised agent token
API token leak
poisoned vendor document
malicious scan target
report data exposure
secret leakage in logs
Copilot hallucination/unsafe advice
```

### Acceptance

```text
[PASS] threats documented
[PASS] mitigations documented
[PASS] non-goals documented
```

---

## 38. Secrets and Redaction

### Required

```text
no secrets in logs
no secrets in reports
no private keys collected
no passwords collected
redaction tests
secret scanning in CI
```

### Acceptance

```text
[PASS] committed fixtures contain no secrets
[PASS] generated reports contain no private keys
[PASS] logs do not print tokens
[PASS] CI secret scan passes
```

---

## 39. Rate Limits and Request Limits

### Required

```text
body size limits
scan target limits
scan timeout limits
job concurrency limits
API rate limits
```

### Acceptance

```text
[PASS] large request rejected
[PASS] too many scan targets rejected
[PASS] scan timeout enforced
[PASS] concurrent jobs limited
```

---

# Phase 15 — Lab Validation

## 40. Local Lab Validation Matrix

### Labs

```text
Linux host lab
Windows host lab
TLS endpoint lab
SSH endpoint lab
Repo/IaC lab
AD/CA lab
Document ingestion lab
```

### Acceptance

```text
[PASS] each evidence source has a lab fixture
[PASS] each evidence source has live lab validation
[PASS] each validation produces report
[PASS] no production environment required
```

---

## 41. AD/CA Lab Validation

### Sequence

```text
1. fixture-first AD evidence flow
2. Windows Server VM
3. AD DS + DNS
4. AD CS Enterprise CA
5. fake certificate templates
6. read-only collector
7. ingest into QRP
8. risk/planner/Copilot/report validation
```

### Acceptance

```text
[PASS] exportable-key template detected
[PASS] broad enrollment detected
[PASS] enrollee-supplies-subject detected
[PASS] AD CS evidence is redacted
[PASS] no real AD data used
```

---

# Phase 16 — Release Readiness

## 42. Product v1 Acceptance Run

### Master checklist

```text
[ ] clean install works
[ ] login/RBAC works
[ ] workspace/environment model works
[ ] scan scopes enforced
[ ] scan jobs/worker works
[ ] agents enroll and send evidence
[ ] evidence provenance works
[ ] finding dedup works
[ ] risk/policy works
[ ] planner/tasks work
[ ] audit log works
[ ] reports export
[ ] backup/restore works
[ ] upgrade migration works
[ ] security tests pass
[ ] lab validation pass
```

---

## 43. Version and Release Notes

### Files

```text
CHANGELOG.md
docs/release-notes/v1.0.0.md
docs/known-limitations.md
```

### Must state

```text
- Product v1 supported features
- Known limitations
- Non-goals
- Safety boundaries
- Upgrade notes
```

### Acceptance

```text
[PASS] version is tagged
[PASS] release notes exist
[PASS] known limitations are explicit
[PASS] no unsupported claim
```

---

# Recommended Engineering Order

Работи точно в този ред:

```text
1. Product v1 scope + acceptance checklist
2. Architecture decision record
3. DB migrations
4. Workspace/environment/asset model
5. Local auth
6. RBAC
7. Audit log
8. Scan scope manager
9. Scan job model
10. Worker queue
11. Agent enrollment
12. Agent security/package
13. Evidence schema versioning
14. Evidence provenance
15. Finding normalization/dedup
16. Policy packs
17. Risk explainability/history
18. Migration task workflow
19. Export integrations
20. Persistent graph in Postgres
21. Graph queries/UI context
22. Copilot citations
23. UI v1 navigation/asset detail/executive view
24. Report builder/export formats
25. Install docs/package
26. Backup/restore
27. Upgrade path
28. Threat model
29. Secrets/redaction/rate limits
30. Lab validation matrix
31. AD/CA lab validation
32. Release readiness run
33. v1 release notes/tag
```

---

# First Task Prompt for Codex

```text
Task: Define QRP Product v1 scope and acceptance criteria.

Context:
We are no longer focusing on the public demo. QRP already has a working local product demo, Web UI, Docker Compose, Postgres persistence, scanners/agents, risk engine, planner, reports, and deterministic Copilot subagents. The next goal is to move from demo/prototype toward a finished on-prem Product v1.

Goal:
Create a clear Product v1 definition and acceptance baseline so future engineering work is not random feature expansion.

Required:
1. Add docs/product-v1-scope.md.
2. Add docs/product-v1-acceptance-checklist.md.
3. Add docs/adr/0001-product-v1-architecture.md if an ADR folder already exists; otherwise create docs/adr/.
4. The scope must define:
   - what QRP v1 is
   - target users
   - supported deployment mode
   - supported evidence sources
   - supported workflows
   - explicit non-goals
   - security and privacy boundaries
   - minimum product capabilities
5. The acceptance checklist must cover:
   - clean install
   - authentication/RBAC
   - workspace/environment model
   - scan scope management
   - scan jobs/worker
   - agent enrollment
   - evidence provenance
   - finding normalization/deduplication
   - risk scoring and policy packs
   - migration planning/tasks
   - reporting
   - audit logging
   - backup/restore
   - upgrade path
   - lab validation
6. Keep wording conservative:
   - no production-ready claim
   - no autonomous remediation claim
   - no TRL7 achieved claim
   - QRP discovers, assesses, explains and plans
   - QRP does not execute production migrations

Do not implement new product features in this task.
Do not add auth/RBAC yet.
Do not add external LLM.
Do not add graph DB.
Do not add AD scanner.
This is a product definition and acceptance task only.
```
