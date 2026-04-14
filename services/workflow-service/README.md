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
- Input: task creation payloads and approval/status update requests.
- Output: JSON task objects, approval records, and cleanup counters.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/workflow-service/tests`

## Known limitations
- Workflow state model is intentionally compact for prototype scope.
