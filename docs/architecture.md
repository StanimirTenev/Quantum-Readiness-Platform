# Quantum Readiness Platform with LLM Copilot

## 1. Цел на продукта

**Quantum Readiness Platform (QRP)** е платформа за откриване, картографиране, оценка и управление на квантово-уязвимата криптография в инфраструктурата на една организация.

Платформата е проектирана така, че:

- да открива къде се използват класически уязвими public-key алгоритми
- да оценява риска по asset, система и сценарий
- да симулира различни сценарии за квантов пробив
- да предлага поетапен migration plan
- да пази evidence за одит и compliance
- да използва LLM като аналитичен и planning слой, без да дава директен контрол върху критичната криптография

---

## 2. Основна концепция

Архитектурата се разделя на два основни свята:

### A. Deterministic Security Core
Това е твърдото, контролирано и одитируемо ядро на системата.

В него влизат:
- scanners
- inventory engine
- crypto fingerprinting
- risk engine
- policy engine
- scenario engine
- workflow approvals
- protected integrations

Този слой:
- не разчита на „творчество“
- работи по твърди правила
- позволява auditing и traceability
- е единственият, който може да стигне до controlled execution

### B. LLM Copilot Layer
Това е интелигентният аналитичен слой.

В него влизат:
- dependency analysis
- risk explanation
- migration plan drafting
- vendor-document analysis
- natural-language querying
- executive / technical summaries

LLM е:
- co-pilot, не autopilot
- помощник за discovery, reasoning и orchestration
- забранен от директно изпълнение на критични промени

---


## 2.1 Deployment and Privacy Boundary

QRP is designed to run inside a customer-controlled deployment environment (internal network, private datacenter, or equivalent controlled boundary).

- Sensitive evidence must remain inside the deployment boundary by default.
- The platform must not require external cloud LLM services to operate.
- The deterministic core must fully operate without any LLM dependency.
- External LLM providers are optional, disabled by default, and require explicit operator configuration.

## 2.2 Copilot Provider Boundary

Copilot capabilities are strictly advisory and must never bypass deterministic controls or approval workflows.

- Copilot is advisory only (co-pilot, not autopilot).
- Default Copilot provider mode must be disabled or local.
- Local LLM provider is preferred for sensitive environments.
- External provider is opt-in only and must never be default.
- No evidence, scan results, inventory data, hostnames, IP addresses, certificate metadata, configuration paths, internal documents, risk scores, or migration plans may leave the deployment boundary unless explicitly configured by the operator.

Suggested provider modes:

```bash
COPILOT_PROVIDER=disabled
COPILOT_PROVIDER=local
COPILOT_PROVIDER=external
```

## 2.3 Cross-Platform Deployment Requirement

QRP must support heterogeneous enterprise environments and must not assume Linux-only infrastructure.

- Server-side services should run Linux-first and containerized internal deployment first.
- Agents and scanners should be designed for multi-OS support over time:
  - Linux servers
  - Windows servers
  - Linux workstations
  - Windows workstations
  - macOS later if needed
- Linux agent was the first implementation; a redacted/aggregate **Windows host
  agent now exists** (`agents/windows-host-agent/collect.ps1`) and its evidence
  persists into inventory (`POST /scans/ingest/windows`).
- AD / certificate-estate discovery is future work and not part of the current implementation task.

## 2.4 Current Non-Goals

The current phase explicitly does **not** start implementation of:

- AD / certificate-estate scanner now (basic Windows host collection is done)
- cloud LLM integration now
- RAG/copilot implementation now
- production hardening now
- auth/RBAC now
- graph implementation now

## 3. Продуктова визия

Платформата трябва да отговаря на въпроси като:

- Къде в инфраструктурата се използват RSA, ECC, DH, ECDH, ECDSA?
- Кои системи са най-рискови при hidden capability сценарий?
- Кои архиви са уязвими на harvest-now-decrypt-later?
- Кои signing workflows са критични?
- Кои vendor-и са блокер за миграция?
- Какъв трябва да бъде wave 1, wave 2 и wave 3?

---

## 4. Основни сценарии, които архитектурата покрива

Платформата трябва да работи при следните сценарии:

1. **Normal public timeline**  
   Квантовият пробив идва в очакваните времеви рамки.

2. **Early break**  
   Реалната способност идва по-рано от очакваното.

3. **Hidden capability**  
   Някой има по-напреднала способност, отколкото е публично известно.

4. **Harvest now, decrypt later**  
   Данните се събират днес за бъдещо разшифроване.

5. **Partial break**  
   Не се чупи всичко наведнъж, а първо определени use case-и.

6. **Vendor lag**  
   Доставчиците не са готови за PQC миграция.

7. **Compliance pressure**  
   Регулаторните и стандартни изисквания изпреварват техническия пробив.

---

## 5. Високо ниво на архитектурата

```text
                                  ┌──────────────────────────────┐
                                  │        Web UI / API          │
                                  │ Dashboards / Copilot / RBAC  │
                                  └──────────────┬───────────────┘
                                                 │
                                        ┌────────▼────────┐
                                        │   API Gateway   │
                                        │ Auth / RateLimit│
                                        └────────┬────────┘
                                                 │
        ┌────────────────────────────────────────┼────────────────────────────────────────┐
        │                                        │                                        │
┌───────▼────────┐                      ┌────────▼────────┐                      ┌────────▼────────┐
│ Inventory API  │                      │   Risk / Policy │                      │   Copilot API   │
│ assets/scans   │                      │ scoring/rules   │                      │ LLM orchestration│
└───────┬────────┘                      └────────┬────────┘                      └────────┬────────┘
        │                                        │                                        │
        │                              ┌─────────▼──────────┐                    ┌────────▼──────────┐
        │                              │  Scenario Engine   │                    │  RAG / Retrieval  │
        │                              │ hidden/HNDL/etc.   │                    │ docs/configs/KB   │
        │                              └─────────┬──────────┘                    └────────┬──────────┘
        │                                        │                                        │
        └──────────────────────────────┬─────────┴─────────┬──────────────────────────────┘
                                       │                   │
                             ┌─────────▼───────┐   ┌──────▼─────────┐
                             │   Postgres      │   │     Graph DB    │
                             │ assets/findings │   │ deps/blast radius│
                             └─────────┬───────┘   └──────┬─────────┘
                                       │                   │
                             ┌─────────▼───────────────────▼─────────┐
                             │         Evidence Normalizer           │
                             │ certs, algos, libs, trust chains      │
                             └─────────┬───────────────────┬─────────┘
                                       │                   │
                 ┌─────────────────────┼───────────────────┼─────────────────────┐
                 │                     │                   │                     │
        ┌────────▼────────┐   ┌────────▼────────┐  ┌──────▼──────┐    ┌────────▼────────┐
        │ Host Agent      │   │ Network Scanner │  │ Repo/CI Scan │    │ Doc Ingestion   │
        │ Linux/Windows   │   │ TLS/SSH/VPN     │  │ pipelines/IaC│    │ PDFs/runbooks   │
        └─────────────────┘   └─────────────────┘  └─────────────┘    └─────────────────┘

                                   ┌──────────────────────────────────┐
                                   │ Controlled Execution Plane       │
                                   │ tickets / approvals / test jobs  │
                                   └──────────────┬───────────────────┘
                                                  │
                                   ┌──────────────▼───────────────────┐
                                   │ Protected Production Integrations│
                                   │ CA / KMS / HSM / CI signing / VPN│
                                   └──────────────────────────────────┘
```

---

## 6. Основни логически слоеве

### 6.1 Collection Layer
Събира сурови данни от инфраструктурата и документацията.

#### Компоненти
- Host Agent
- Network Scanner
- Repo/CI Scanner
- Document Ingestion
- Cloud/Infra Connectors

#### Роля
- discovery
- evidence collection
- inventory feed
- crypto surface mapping

---

### 6.2 Evidence & Asset Graph Layer
Централен слой за моделиране на системите и зависимостите.

#### Основни обекти
- Asset
- Service
- Endpoint
- Certificate
- CA
- Pipeline
- BackupSet
- Library
- VendorProduct
- PolicyRule
- MigrationTask

#### Основни връзки
- Service -> uses -> Certificate
- Certificate -> signed_by -> CA
- Pipeline -> signs -> Artifact
- Asset -> depends_on -> Library
- BackupSet -> protects -> DataStore
- Asset -> blocked_by -> VendorProduct

#### Роля
- dependency mapping
- blast radius analysis
- trust chain visualization
- migration impact analysis

---

### 6.3 Deterministic Analysis Layer
Този слой оценява риска по твърди правила.

#### Подмодули
- Crypto Fingerprinting Engine
- PQC Readiness Engine
- Risk Scoring Engine
- Policy Engine
- Scenario Engine

#### Роля
- твърдо откриване на алгоритми
- readiness classification
- scoring
- scenario-based recalculation
- enforcement of deterministic policy rules

---

### 6.4 LLM Copilot Layer
Интелигентен аналитичен слой върху evidence и graph-а.

#### Подмодули
- Discovery Analyst
- Risk Narrator
- Migration Planner
- Vendor Intelligence Analyst
- Change Assistant

#### Роля
- dependency reasoning
- executive summaries
- technical explanations
- plan generation
- question answering

---

### 6.5 Controlled Execution Layer
Няма директно AI изпълнение. Всичко минава през approval.

#### Подмодули
- Workflow Service
- Approval Service
- Ticket Generator
- Validation Runner
- Integration Service

#### Роля
- approvals
- staging checks
- controlled rollout
- audit trail

---

## 7. Модули и техните роли

## 7.1 API Gateway
### Отговорности
- входна точка за UI и външни системи
- authentication
- RBAC
- rate limiting
- request routing

### Защо е нужен
За да отделим frontend-а от вътрешните услуги и да държим централизиран достъп.

---

## 7.2 Inventory Service
### Отговорности
- регистрира assets
- пази services, endpoints, owners
- приема данни от scanner-и
- управлява asset metadata

### Примери за данни
- server name
- fqdn
- owner
- environment
- business criticality
- vendor
- lifecycle years

---

## 7.3 Evidence Normalizer
### Отговорности
- нормализира сурови данни
- парсва сертификати и ключови свойства
- идентифицира trust chains
- обединява findings от различни scanner-и

### Защо е ключов
Без нормализация discovery слоят ще дава несъвместими данни.

---

## 7.4 Crypto Fingerprinting Service
### Отговорности
- открива RSA, ECC, DH, ECDH, ECDSA
- идентифицира classical-only usage
- анализира TLS/SSH/VPN/signing stacks

### Примери за detection
- certificate algorithms
- signing commands in CI
- OpenSSL / libcrypto usage
- SSH server algorithm policies

---

## 7.5 PQC Readiness Engine
### Отговорности
Класифицира assets и услуги като:
- classical-only
- hybrid-capable
- PQC-ready
- unknown
- vendor-blocked

### Роля
Преходен слой между raw crypto findings и реална migration логика.

---

## 7.6 Risk Engine
### Отговорности
Пресмята risk score по asset, service или dependency chain.

### Примерни фактори
- criticality
- confidentiality lifetime
- quantum exposure
- blast radius
- vendor lock-in
- migration difficulty

### Примерна формула
```text
Risk Score =
Asset Criticality
× Confidentiality Lifetime
× Quantum Exposure
× Vendor Lock-in
× Migration Difficulty
× Blast Radius
```

---

## 7.7 Scenario Engine
### Отговорности
Поддържа различни рискови режими.

### Сценарии
- public timeline
- early break
- hidden capability
- HNDL active now
- vendor lag
- compliance pressure

### Роля
Позволява едни и същи assets да бъдат преоценявани спрямо различни допускания.

---

## 7.8 Policy Engine
### Отговорности
Прилага deterministic правила.

### Примери за правила
- No new classical-only signing pipelines after date X
- All critical assets must have migration owner
- All long-term archives must be tagged
- All external critical services must have scenario review

### Роля
Осигурява контролирано и одитируемо поведение.

---

## 7.9 Copilot Service
### Отговорности
- natural-language interface
- orchestration на retrieval и LLM
- обяснения и summaries
- генериране на plan drafts

### Примерни въпроси
- Кои са най-рисковите systems при hidden capability?
- Кои backups имат confidentiality lifetime над 7 години?
- Кои signing pipelines са vendor-blocked?

---

## 7.10 Retrieval Service
### Отговорности
- индексира docs, configs, vendor docs, runbooks, KB
- подава релевантен контекст на LLM
- пази traceability на отговора

### Роля
LLM да стъпва върху вътрешни данни, а не само върху общи знания.

---

## 7.11 Planner Service
### Отговорности
- генерира wave 1 / 2 / 3
- разбива промени на задачи
- отчита dependencies
- предлага sequence и rollback notes

---

## 7.12 Workflow / Approval Service
### Отговорности
- approval requests
- task lifecycle
- audit trail
- segregation of duties

### Роля
Нито една критична промяна не се изпълнява без одобрение.

---

## 7.13 Integration Service
### Отговорности
- CA integration
- KMS / HSM integration
- CI signing integration
- VPN / certificate systems
- ticketing systems

### Важна граница
Достъпът до този слой е само след approval и deterministic validation.

---

## 8. Подагенти в LLM слоя

### 8.1 Discovery Analyst
- анализира configs, docs, runbooks и repos
- открива неявни crypto dependencies
- извлича implicit risk context

### 8.2 Risk Narrator
- превежда scoring-а на човешки език
- прави executive и technical summary
- обяснява защо asset е high-risk

### 8.3 Migration Planner
- създава wave планове
- предлага tasks по екипи
- подготвя implementation notes

### 8.4 Vendor Intelligence Analyst
- чете vendor документация
- прави readiness matrix
- маркира несигурни claims

### 8.5 Change Assistant
- генерира change request
- подготвя test plan и rollback draft
- помага на operations екипа

---

## 9. Какво LLM има право да прави

LLM може:
- да анализира
- да класифицира
- да сравнява документи
- да обяснява риск
- да предлага migration план
- да генерира tickets и checklists
- да отговаря на естествен език

LLM няма право:
- да сменя сертификати
- да върти ключове
- да подписва артефакти
- да променя trust anchors
- да променя VPN/firewall/PKI конфигурации
- да изпълнява production changes без approval boundary

---

## 10. Данни и база

## 10.1 PostgreSQL модел

```sql
assets(
  id, asset_type, name, owner, criticality, environment,
  vendor, lifecycle_years, created_at, updated_at
);

services(
  id, asset_id, protocol, port, fqdn, exposure_type
);

certificates(
  id, asset_id, subject, issuer, algo, key_size,
  not_before, not_after, chain_id, pqc_readiness
);

crypto_findings(
  id, asset_id, finding_type, algorithm, location,
  evidence_ref, severity, detected_at
);

signing_pipelines(
  id, asset_id, repo, ci_system, artifact_type,
  signing_method, approval_required
);

backup_sets(
  id, asset_id, data_class, retention_years,
  confidentiality_lifetime, immutable_flag
);

risk_scores(
  id, asset_id, scenario, score, rationale_json,
  calculated_at
);

migration_tasks(
  id, asset_id, wave, task_type, status,
  owner, dependency_count, rollback_plan
);

approvals(
  id, task_id, approver, decision, decided_at, note
);
```

---

## 10.2 Graph DB модел

### Nodes
- Asset
- Service
- Certificate
- CA
- Pipeline
- BackupSet
- Library
- VendorProduct

### Edges
- USES_CERT
- SIGNED_BY
- DEPENDS_ON
- PROTECTS
- RUNS_ON
- BLOCKED_BY_VENDOR
- FEEDS_PIPELINE

### Защо graph DB
За blast radius, trust chains и dependency-driven planning.

---

## 10.3 Object Storage
Пази:
- scan artifacts
- config snapshots
- vendor PDFs
- policies
- reports
- exported evidence

---

## 10.4 Vector Store
Пази:
- parsed docs
- configs
- standards mappings
- runbooks
- previous decisions
- vendor notes

Използва се за retrieval към LLM.

---

## 11. Примерни потоци

## 11.1 Discovery Flow
1. Host agent сканира хост.
2. Network scanner сканира TLS/SSH/VPN.
3. Repo scanner проверява CI/IaC.
4. Evidence normalizer обединява резултатите.
5. Inventory service записва assets и findings.
6. Risk engine изчислява score.
7. Copilot генерира explanation.

---

## 11.2 Scenario Flow
1. Потребител избира сценарий „hidden capability“.
2. Scenario engine вдига тежестта на long-term secrecy.
3. Risk engine преизчислява всички affected assets.
4. Planner service прави нов priority order.
5. Copilot връща summary.

---

## 11.3 Controlled Change Flow
1. Planner service създава migration task.
2. Workflow service отваря approval.
3. След approval integration service пуска validation.
4. Ако validation е ОК, тогава стига до protected integration.
5. Резултатът се връща като evidence.

---

## 12. Примерна scoring логика

```text
base_score =
  criticality * 0.25 +
  confidentiality_lifetime * 0.20 +
  quantum_exposure * 0.20 +
  blast_radius * 0.15 +
  vendor_lock_in * 0.10 +
  migration_difficulty * 0.10

scenario_multiplier =
  1.00 public_timeline
  1.20 early_break
  1.35 hidden_capability
  1.40 HNDL_active_now
  1.15 vendor_lag

final_score = base_score * scenario_multiplier
```

---

## 13. UI и dashboards

## 13.1 Executive Dashboard
Показва:
- readiness %
- top critical assets
- top blockers
- vendor lag
- migration waves
- scenario selector

## 13.2 Security Engineering Dashboard
Показва:
- certificate chains
- signing dependencies
- TLS/SSH/VPN findings
- classical-only hotspots
- blast radius graph

## 13.3 Operations Dashboard
Показва:
- pending approvals
- rollout tasks
- failed validations
- rollback readiness

## 13.4 Copilot Panel
Примерни заявки:
- Кои са най-рисковите signing assets?
- Покажи всички external TLS services с high score.
- Направи wave 1 план за Linux fleet.
- Кои vendor-и блокират миграцията?

---

## 14. Security boundaries

### Trust Zone 1: Read-Only Observation
- scanners
- log readers
- repo readers
- doc ingestion

### Trust Zone 2: Analysis
- risk engine
- policy engine
- scenario engine
- LLM copilot
- retrieval

### Trust Zone 3: Controlled Execution
- workflow
- approvals
- validation runners
- ticketing

### Trust Zone 4: Protected Production Control
- CA
- KMS / HSM
- CI signing
- VPN / certificate systems
- production cryptographic control plane

**LLM никога не получава директен достъп до Trust Zone 4.**

---

## 15. Технологичен стек

## Backend
- Go за scanners и performance-critical services
- Python за orchestration, analysis и LLM integration
- FastAPI или Go Fiber за API

## Data
- PostgreSQL
- Neo4j
- S3-compatible object storage
- pgvector или отделен vector store

## Frontend
- React
- RBAC-based dashboards

## Agents
- Linux daemon in Go
- по-късно Windows agent ако е необходимо

## AI
- local model за чувствителни среди
- enterprise-routed model за по-широки случаи
- RAG върху вътрешната knowledge база

---

## 16. MVP версия

## Какво включва MVP
- Linux host agent
- basic TLS/SSH scanner
- inventory service
- evidence normalizer
- basic risk engine
- basic scenario engine
- PostgreSQL
- basic graph store
- simple copilot endpoint
- 3 dashboards

## Какво НЕ включва MVP
- автоматичен cert rotation
- активни production changes
- full CA/KMS/HSM integration
- сложни cloud integrations
- full CI signing automation
- autonomous execution

### Цел на MVP
Да докаже, че платформата може:
- да открива exposure
- да дава meaningful risk score
- да прави dependency map
- да отговаря на operational въпроси
- да предлага първичен migration plan

---

## 17. Етапи на разработка

## Етап 1 — Foundation
### Цели
- дефиниране на asset model
- базова база данни
- basic API
- Linux host agent
- TLS/SSH scanning
- inventory ingest

### Deliverables
- asset schema
- inventory service
- host agent v1
- network scanner v1
- evidence normalizer v1

### Резултат
Имаме базов discovery слой.

---

## Етап 2 — Analysis Core
### Цели
- crypto fingerprinting
- risk scoring
- scenario engine
- graph dependencies
- first dashboards

### Deliverables
- fingerprint rules
- scoring model
- scenario multipliers
- blast radius graph
- executive + technical dashboard

### Резултат
Имаме смислен анализ и risk prioritization.

---

## Етап 3 — LLM Copilot
### Цели
- ingestion на docs и configs
- retrieval service
- copilot endpoint
- risk explanation
- migration plan drafts

### Deliverables
- vector index
- parsed docs pipeline
- copilot API
- prompt templates
- planner outputs

### Резултат
Платформата вече е usable на естествен език.

---

## Етап 4 — Workflow & Approvals
### Цели
- migration tasks
- approvals
- audit trail
- tickets
- validation runners

### Deliverables
- workflow service
- approval model
- change request templates
- execution pre-checks

### Резултат
Има контролиран operational процес.

---

## Етап 5 — Integrations
### Цели
- CI/CD integration
- signing integration
- CA/KMS/HSM integration
- vendor matrix
- production-safe workflows

### Deliverables
- integration adapters
- vendor readiness registry
- signing workflow controls
- controlled execution boundary

### Резултат
Платформата става enterprise-ready.

---

## Етап 6 — Hardening & Expansion
### Цели
- Windows support
- cloud connectors
- richer policy packs
- reporting and compliance
- multi-tenant support

### Deliverables
- Windows agent
- AWS/Azure/GCP connectors
- compliance exports
- richer dashboards

### Резултат
Платформата може да се продава по-широко.

---

## 18. Предложен backlog за първите спринтове

## Sprint 1
- define DB schema
- create inventory API skeleton
- create Linux host agent skeleton
- create raw findings ingestion
- store assets in Postgres

## Sprint 2
- TLS/SSH scanner
- certificate parser
- evidence normalizer
- first UI page for asset list
- first risk placeholders

## Sprint 3
- crypto fingerprint rules
- scoring engine v1
- scenario engine v1
- top-risk dashboard
- graph dependencies v1

## Sprint 4
- document ingestion
- retrieval index
- copilot query endpoint
- risk explanation prompt
- first migration draft template

## Sprint 5
- workflow model
- approval states
- task generation
- rollout checklist template
- validation runner prototype

## Sprint 6
- vendor registry
- signing pipeline ingestion
- backup/retention model
- wave planner v1
- executive report export

---

## 19. Файлова структура на проекта

```text
quantum-readiness-platform/
├─ docs/
│  ├─ architecture.md
│  ├─ threat-model.md
│  ├─ scoring-model.md
│  ├─ api-spec.md
│  └─ prompts/
│     ├─ risk-explainer.md
│     ├─ planner.md
│     └─ vendor-analyst.md
│
├─ services/
│  ├─ api-gateway/
│  ├─ inventory-service/
│  ├─ evidence-normalizer/
│  ├─ crypto-fingerprint-service/
│  ├─ risk-engine/
│  ├─ scenario-engine/
│  ├─ policy-engine/
│  ├─ planner-service/
│  ├─ workflow-service/
│  ├─ retrieval-service/
│  ├─ copilot-service/
│  └─ integration-service/
│
├─ agents/
│  ├─ linux-host-agent/
│  ├─ network-scanner/
│  ├─ repo-ci-scanner/
│  └─ doc-ingestion/
│
├─ frontend/
│  ├─ web-ui/
│  └─ shared-components/
│
├─ data/
│  ├─ migrations/
│  ├─ seed/
│  └─ samples/
│
├─ infra/
│  ├─ docker/
│  ├─ k8s/
│  ├─ terraform/
│  └─ monitoring/
│
├─ shared/
│  ├─ schemas/
│  ├─ clients/
│  ├─ auth/
│  └─ utils/
│
└─ tests/
   ├─ unit/
   ├─ integration/
   └─ e2e/
```

---

## 20. Как да се позиционира продуктът

По-добро позициониране:
- Quantum Readiness Platform
- Quantum Migration Intelligence
- Quantum Risk & Crypto Agility Platform
- Quantum Readiness Platform with LLM Copilot

По-слабо позициониране:
- AI that protects against quantum computers

Причина:
- защитата идва от криптографията, контрола и миграцията
- LLM е intelligence layer, а не cryptographic shield

---

## 21. Най-важният принцип

**LLM не е ключалката.  
LLM е интелигентният инженер, анализатор и planner около ключалката.**

---

## 22. Следващи конкретни стъпки

1. Финализиране на asset schema  
2. Избор на стек за MVP  
3. Дефиниране на първите 10 risk rules  
4. Дефиниране на първите 10 copilot queries  
5. Изграждане на Linux host agent v1  
6. Изграждане на TLS/SSH scanner v1  
7. Построяване на inventory + findings ingest  
8. Добавяне на scoring engine v1  
9. Добавяне на graph dependency model  
10. Пускане на първи dashboard и copilot panel

---

## 23. Кратко финално резюме

Тази архитектура е изградена така, че:
- да работи при различни сценарии на квантов риск
- да държи AI извън директния cryptographic control
- да позволява discovery, scoring, migration planning и evidence-driven operations
- да започне просто като MVP и да се разширява поетапно

Крайният продукт е комбинация от:
- discovery platform
- risk engine
- crypto-agility planner
- operational workflow
- LLM copilot
