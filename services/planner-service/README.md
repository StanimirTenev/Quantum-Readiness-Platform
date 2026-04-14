# Planner Service

## What this service does
- Builds wave-based remediation plans from inventory and risk data.

## Current role in the prototype
- Working prototype planning service with task export into workflow.

## Main endpoints or functions
- `GET /health`, `GET /plan`, `GET /waves`
- `POST /export-tasks`

## Inputs / outputs
- Input: inventory/risk data from upstream services and export options (`waves`, `auto_submit`).
- Output: JSON plan summaries and created workflow task payloads.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/planner-service/tests`

## Known limitations
- Planning logic is deterministic and rule-based; scenario customization is limited.
