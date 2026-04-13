# Quantum Readiness Platform — TRL5 Working Navigator

Този документ фиксира ежедневния работен ред за достигане на **TRL 5** (validated prototype in relevant environment) без разпиляване на усилията между прекалено много паралелни теми.

## 1) Current baseline (as of April 13, 2026)

### Product maturity
- Architected prototype
- Foundational MVP skeleton
- Partial end-to-end flow (not production-ready)

### Working modules
- `inventory-service`
- `risk-engine`
- `planner-service`
- `workflow-service`
- `retrieval-service` (keyword-level)
- `copilot-service` (routing/summary layer)
- `dashboard-ui`
- `agents/linux-host-agent`
- `agents/network-scanner`

### Skeleton / early modules
- `services/api-gateway`
- `services/evidence-normalizer`
- `services/crypto-fingerprint-service`
- `services/integration-service`
- `services/policy-engine`
- `services/scenario-engine`
- `agents/doc-ingestion`
- `agents/repo-ci-scanner`
- `frontend/web-ui`
- `infra/terraform`
- `infra/monitoring`

## 2) TRL5 target definition for this repository

За този проект TRL5 се счита постигнато, когато има:

1. **Стабилен core flow**: evidence → inventory → risk → planning → workflow → dashboard.
2. **Expanded evidence quality**: Linux host + network scanner дават обогатени, повторяеми артефакти.
3. **Decision-useful output**: risk/planning резултатите са обясними и actionable.
4. **Repeatable demo in relevant environment**: локален или staging сценарий, който се стартира последователно със същия резултат.
5. **Clear boundaries**: ясно разграничение между deterministic core и copilot/retrieval слоевете.

## 3) Ordered development sequence (single-threaded focus)

1. Stage 1 — Stabilize core contracts and data model.
2. Stage 2 — Expand discovery/evidence.
3. Stage 3 — Improve risk/planning logic.
4. Stage 4 — Introduce dependency graph MVP.
5. Stage 5 — Upgrade retrieval/doc intelligence.
6. Stage 6 — Build grounded copilot reasoning.
7. Stage 7 — Production hardening.

> Rule: only one primary layer is active at a time.

## 4) Active stage now

### Active stage
**Stage 1 — Stabilize and clarify the core.**

### Stage 1 Definition of Done
- Всички ключови API контракти са ясни и съгласувани.
- Ясно е кое е real logic и кое е placeholder.
- Има описан стабилен локален demo flow.
- Няма двусмислие в naming/schema между основните услуги.

## 5) Execution checklist for each coding session

В началото:
1. Кой е активният stage?
2. Кой е единственият модул фокус за сесията?
3. Какво е smallest valuable increment?

В края:
1. Какво е затворено?
2. Какво остава?
3. Каква е следващата най-малка стъпка?
4. Какво умишлено няма да се пипа още?

## 6) Status model

Използвай само тези статуси за големи модули:
- `NOT STARTED`
- `IN PROGRESS`
- `SKELETON ONLY`
- `PARTIALLY WORKING`
- `WORKING`
- `NEEDS REFACTOR`
- `READY FOR NEXT LAYER`

## 7) Live tracker table template

| Module | Status | What works now | What is missing | Next step |
|---|---|---|---|---|
| inventory-service | PARTIALLY WORKING | assets/scans storage | richer schema alignment | unify contracts |
| risk-engine | PARTIALLY WORKING | base scoring | richer risk factors | add exposure/impact/confidence separation |
| planner-service | PARTIALLY WORKING | wave grouping | dependency-aware ranking | introduce blocking/dependency inputs |
| workflow-service | PARTIALLY WORKING | tasks/approvals base | richer lifecycle | add explicit lifecycle transitions |
| retrieval-service | SKELETON ONLY | keyword summary | semantic retrieval | define ingestion+chunk metadata model |
| copilot-service | SKELETON ONLY | routing/summaries | grounded reasoning | bind retrieval outputs to deterministic evidence |
| linux-host-agent | PARTIALLY WORKING | baseline host evidence | richer crypto discovery | add collectors for cert/config/lib signals |
| network-scanner | PARTIALLY WORKING | TLS probe | richer normalization | normalize chain/signature metadata |
| dependency graph | NOT STARTED | conceptual only | graph model/store | design graph schema and seed pipeline |
| doc-ingestion | NOT STARTED | conceptual only | parser pipeline | implement source adapters |
| policy-engine | SKELETON ONLY | minimal behavior | real rule system | define policy rule model |
| scenario-engine | SKELETON ONLY | initial idea | simulation logic | define scenario input/output contracts |
| dashboard-ui | PARTIALLY WORKING | baseline dashboard | deeper graph/evidence views | align UI views to core contracts |

## 8) Immediate next package (recommended)

### Package 1 (now)
- Document and freeze core flow.
- Align service contracts/schemas.
- Mark placeholder vs real logic explicitly.

### Package 2
- Enrich Linux host evidence.
- Enrich network scan evidence normalization.
- Improve evidence schema in inventory ingest path.

### Package 3
- Upgrade risk scoring explainability.
- Improve migration priority ranking in planner.

## 9) Anti-drift guardrails

If any of these happen, stop and re-scope:
- starting new services before closing current module DoD
- UI changes before data model is stable
- copilot expansion before retrieval quality is improved
- production hardening before core value flow is stable

## 10) Session decision rule

Когато има колебание за следваща задача:

> "Кое е най-малкото следващо нещо, което увеличава реалната стойност на core-а?"

Ако отговорът не е ясен, задачата се разбива още преди имплементация.
