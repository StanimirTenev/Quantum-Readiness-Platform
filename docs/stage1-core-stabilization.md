# Stage 1 / Core Stabilization Execution (Canonical)

Този документ фиксира изпълнението на **Stage 1 / Core Stabilization** за текущия monorepo и следва архитектурния ред от `docs/architecture.md` (Discovery -> Inventory -> Risk -> Planning -> Workflow -> Dashboard).  

## 0) Session header template (задължителен за всяка сесия)

- **Step:** [1..6]
- **Scope today:** [конкретни модули/файлове]
- **Out of scope:** [какво НЕ се пипа]
- **Test criterion:** [какво трябва да мине]
- **Session DoD:** [как разбираме, че сесията е затворена]

---

## 1) Canonical end-to-end flow (Stage 1)

`linux-host-agent / network-scanner -> inventory-service -> risk-engine -> planner-service -> workflow-service -> dashboard-ui`

### 1.1 Discovery входни точки

- `linux-host-agent`: CLI `cmd/agent/main.go` с флагове `-ingest` и `-inventory-url`; при ingest праща scan към inventory-service.  
- `network-scanner`: CLI `cmd/scanner/main.go` с флагове `-target`, `-ingest`, `-inventory-url`; при ingest праща TLS scan към inventory-service.  

### 1.2 Evidence ingress в inventory

- Централна ingress точка: `POST /scans/ingest` в inventory-service.
- Payload: `ScanIngestRequest` със `source`, `assets`, и optional evidence блокове (`host_inventory`, `crypto_evidence`, `tls_evidence`).
- Inventory записва scan + asset-и и (по default) тригерира auto-score към risk-engine (`auto_score=true`).

### 1.3 Risk -> Planner -> Workflow -> Dashboard

- Inventory към Risk: `build_risk_payload(...)` -> `POST /score`.
- Planner чете от inventory (`/assets`, `/risks`) и строи plan (`/plan`, `/waves`).
- Planner към Workflow: `POST /export-tasks` формира task-и и ги праща към `POST /tasks`.
- Dashboard е BFF-style proxy (`/api/*`) към copilot/planner/workflow/retrieval endpoints.

### 1.4 Retrieval + Copilot в flow-а

- Retrieval агрегира inventory + planner + workflow за `overview`, `asset`, `search`.
- Copilot orchestration layer: резюмета и query routing върху retrieval/planner/workflow, без директен production execution.

### 1.5 Placeholder маркировка по връзки

- **Real:** scanner ingest -> inventory -> risk -> planner.
- **Partial/Placeholder:** planner export към workflow е реален, но workflow lifecycle е базов (няма пълен approval domain/SoD engine).
- **Placeholder:** dashboard visual layer е демо-ориентиран и не е production-polished.

---

## 2) Contracts и payload sheet (Stage 1)

## 2.1 inventory-service

- **`POST /scans/ingest` input**
  - required: `source`, `assets[]`
  - optional: `host_inventory`, `crypto_evidence`, `tls_evidence`
- **`POST /scans/ingest` output**
  - `source`, `created`, `asset_ids[]`, `scan_id`
- **`GET /risks` output**
  - `RiskRecord[]` с `contract_version`, `asset_name`, `scenario`, `normalized_score_100`, `rating`, `dependency_count`, `vendor_blocked`, `rationale`

## 2.2 risk-engine

- **`POST /score` input**
  - canonical fields: `contract_version=stage1-v1`, `asset_name`, scoring factors, `dependency_count`, `vendor_blocked`, `scenario`
- **`POST /score` output**
  - `contract_version`, `asset_name`, `scenario`, `scenario_multiplier`, `base_score`, `final_score`, `normalized_score_100`, `rating`, `dependency_count`, `vendor_blocked`, `rationale`

## 2.3 planner-service

- **`GET /plan` output**
  - `summary`, `wave_1[]`, `wave_2[]`, `wave_3[]`, `execution_plan`
  - plan item canonical fields: `asset_name`, `asset_type`, `rating`, `normalized_score_100`, `priority_score_100`, `scenario`, `dependency_count`, `vendor_blocked`, `recommended_action`
- **`POST /export-tasks` input**
  - `waves[]`, `auto_submit` (в момента `auto_submit` не се използва)
- **`POST /export-tasks` output**
  - `exported_waves`, `created_count`, `tasks[]`

## 2.4 workflow-service

- **Task input (`POST /tasks`)**
  - `title`, `asset_name`, `wave`, `priority`, `description`, `recommended_action?`
- **Approval input (`POST /tasks/{id}/approve`)**
  - `approver`, `decision`, `note?`
- **Known behavior**
  - status transition matrix е deterministic, но минимален.

## 2.5 Known mismatches (за Stage 1)

1. `docs/api-spec.md` не отразява реалните endpoint-и в services (`/scans/ingest`, `/score`, `/plan`, `/tasks` и др.)
2. Naming е смесен между `snake_case` payload-и и някои UI формати, но core pipeline е последователен на `snake_case`.
3. `auto_submit` в planner export request е заявен field, но няма runtime ефект (placeholder behavior).

**Canonical naming за Stage 1:** `snake_case`, `asset_name` като canonical cross-service asset key.

---

## 3) Real vs Placeholder matrix

| Module | Component | Status | Note | Next action |
|---|---|---|---|---|
| inventory-service | `/assets`, `/scans/ingest`, `/risks` + SQLite repo | real_logic | CRUD + scan ingestion + risk persistence са активни | Freeze schema v1 |
| risk-engine | `/score` + scenario multipliers | real_logic | deterministic scoring работи | Add richer factors in Stage 2 |
| planner-service | `build_plan`, `/plan`, `/export-tasks` | real_logic | wave generation + export са активни | Add dependency graph (Stage 2+) |
| workflow-service | tasks/approvals lifecycle | partial_logic | валидни transitions, но ограничен approval domain | Extend approval policy model |
| retrieval-service | `/overview`, `/asset`, `/search` | partial_logic | aggregation/search са rule-based | Upgrade to semantic retrieval later |
| copilot-service | intent routing + summaries | partial_logic | no true LLM reasoning yet (template routing) | Replace with model-backed orchestration |
| dashboard-ui | `/api/*` proxies + static rendering | placeholder_logic | usable demo UI, non-polished UX | Keep minimal in Stage 1 |
| linux-host-agent | collect + optional ingest | real_logic | local collection + posting работи | enrich evidence depth (Stage 2) |
| network-scanner | TLS scan + optional ingest | real_logic | deterministic TLS extraction + posting | add broader protocol coverage |

---

## 4) Repeatable local demo (Stage 1)

## 4.1 Startup order

1. `risk-engine`
2. `inventory-service`
3. `workflow-service`
4. `planner-service`
5. `retrieval-service`
6. `copilot-service`
7. `dashboard-ui`

Практически shortcut: `scripts/start_all.sh`.

## 4.2 Environment variables (основни)

- `RISK_ENGINE_URL`
- `INVENTORY_SERVICE_URL`
- `WORKFLOW_SERVICE_URL`
- `PLANNER_SERVICE_URL`
- `RETRIEVAL_SERVICE_URL`
- `COPILOT_SERVICE_URL`

Всички имат локални defaults към `127.0.0.1` с фиксирани портове.

## 4.3 Minimal demo scenario

1. Стартирай services (`scripts/start_all.sh`).
2. Ingest host evidence (`linux-host-agent -ingest`) или network evidence (`network-scanner -target ... -ingest`).
3. Провери създаден risk (`GET /risks`).
4. Генерирай план (`GET /plan`).
5. Експортирай задачи (`POST /export-tasks`).
6. Отвори dashboard (`http://127.0.0.1:8010`) и провери summary/tasks/waves.

## 4.4 Known issues (Stage 1)

- Няма production auth/RBAC boundary на service level.
- Няма semantic retrieval (само deterministic text matching).
- Dashboard е demo UI слой, не production frontend.

---

## 5) Minimal cleanup backlog (без раздуване)

- Align `docs/api-spec.md` към реалните endpoint-и.
- Премахване/реализиране на неактивни полета като `auto_submit`.
- Уеднаквяване на naming annotations в docs за `asset_name` като canonical key.
- Дръж Stage 1 cleanup само документален/contract-level; без голям refactor.

---

## 6) Test freeze checklist (Stage 1)

Минимумът за freeze run:

- `services/inventory-service/tests`
- `services/risk-engine/tests`
- `services/planner-service/tests`
- `services/workflow-service/tests`
- `services/retrieval-service/tests`
- `services/copilot-service/tests`
- smoke flow check с локално стартирани услуги

Freeze artifact: този документ + `docs/core-flow-stage1-contract.md` + тестов отчет от последния run.

---

## 7) Stage 1 success criteria (definition)

Stage 1 е успешен, ако:

- core flow е еднозначно описан;
- contracts между inventory/risk/planner/workflow са ясни;
- real vs placeholder е прозрачно маркирано;
- local demo е repeatable;
- има freeze checklist и known issues list.

---

## 8) Test execution story closure (run: 2026-04-13)

### 8.1 Stage 1 test suites (required by freeze checklist)

- `services/inventory-service/tests` -> **6 passed**
- `services/risk-engine/tests` -> **7 passed**
- `services/planner-service/tests` -> **6 passed**
- `services/workflow-service/tests` -> **7 passed**
- `services/retrieval-service/tests` -> **6 passed**
- `services/copilot-service/tests` -> **5 passed**

**Total:** 37 passed, 0 failed (Python/pytest run with `PYTHONPATH=.` per service).

### 8.2 Repeatable local demo verification

- `scripts/start_all.sh` беше hard-failing в среди без per-service `.venv`; скриптът е коригиран да стартира и без `.venv` (fallback към текущия Python env).
- Добавена е и защита в `scripts/status_all.sh` срещу false-positive статус при zombie PID.
- End-to-end smoke (multi-service runtime + API flow) остава **частично верифициран** в текущата execution среда; процесите се маркират като стартирани, но в тази sandbox среда не остават routable за стабилен multi-service HTTP smoke.

### 8.3 Known limitations (freeze-impacting)

1. `docs/api-spec.md` е извън синхрон с реалните service contracts (вкл. endpoint и payload детайли).
2. Има naming/contract drift в scenario стойности между документи и runtime валидатори (пример: `public_timeline` vs. `normal_public_timeline`).
3. `auto_submit` в planner export request е placeholder поле без runtime ефект.
4. Няма production-grade auth/RBAC boundary на service level.
5. Dashboard слой е demo-oriented, не production-polished UI.

### 8.4 Stage 1 freeze-ready decision

**Decision (2026-04-13): NOT freeze-ready.**

Причина: въпреки че required test suites минават (37/37), има freeze-impacting contract/documentation drift и непълна end-to-end demo верификация в текущата среда. Минимален prerequisite за freeze: contract/docs alignment (`docs/api-spec.md` + scenario/naming sync) и един валидиран reproducible smoke run artifact.
