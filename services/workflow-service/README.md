# Workflow Service

## What this service does
- Manages remediation tasks, status transitions, and approval records.

## Current role in the prototype
- Working prototype workflow backend for planner and dashboard operations.

## Main endpoints or functions
- `GET /health`
- `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/{submit|status|approve}`
- `GET /approvals`, `POST /admin/cleanup-duplicates`

## Inputs / outputs
- Input: task creation payloads (require `requested_by`) and approval/status update requests.
- Output: JSON task objects, approval records, and cleanup counters.

## Database location
- Defaults to the service-local `workflow.db`. Set `WORKFLOW_DB_PATH` to point the store at
  another file -- mirrors `inventory-service`'s `INVENTORY_DB_PATH` convention.
- Set `DATABASE_URL` (a `postgresql://` connection string) to use PostgreSQL instead --
  takes priority over `WORKFLOW_DB_PATH` when both are set. `infra/docker/docker-compose.yml`
  points this at the same Postgres instance/database `inventory-service` uses (table names
  don't collide: `tasks`/`approvals` vs. `workspaces`/`assets`/`scans`/`risk_results`/
  `reports`) so the deployed product gets concurrent-write-safe persistence without a second
  database server. Bare-metal dev/tests/CI stay on SQLite by default. See
  `tools/db_compat.py` and `services/inventory-service/README.md`.

## Current status
- Working prototype service. Enforces segregation of duties: `POST /tasks/{task_id}/approve`
  rejects (409) when `approver` matches the task's `requested_by`.

## How to run tests
- `pytest services/workflow-service/tests`

## Known limitations
- Workflow state model is intentionally compact for prototype scope.
