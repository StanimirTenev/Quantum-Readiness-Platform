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
  another file -- mirrors `inventory-service`'s `INVENTORY_DB_PATH` convention. Used by
  `infra/docker/docker-compose.yml` to persist tasks/approvals on a named volume across
  `docker compose up --build` (previously reset every rebuild, fixed 2026-07-11).

## Current status
- Working prototype service. Enforces segregation of duties: `POST /tasks/{task_id}/approve`
  rejects (409) when `approver` matches the task's `requested_by`.

## How to run tests
- `pytest services/workflow-service/tests`

## Known limitations
- Workflow state model is intentionally compact for prototype scope.
