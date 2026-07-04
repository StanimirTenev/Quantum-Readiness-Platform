# Integration Service

> **Safety boundary:** this is a **disabled, dry-run-only skeleton**. It never
> connects to any CA / KMS / HSM / CI-signing / VPN / ticketing system and never
> executes a production change. `executed` is always `false`. Real Trust Zone 4
> connectors are intentionally out of scope.

## What this service does
- Validates a *proposed* integration action against the deterministic approval
  boundary and returns a preview — without doing anything.
- Enforces per-action required approvals (e.g. `rotate_certificate` needs
  `security_review` + `change_approval`).
- Rejects any secret-like parameters (private keys, tokens, passwords, API keys)
  and never echoes them back.

## Current role in the prototype
- Safe skeleton. Deterministic, local-first, no network, no execution. Models
  the Trust Zone 4 boundary described in `docs/architecture.md` §7.13 without
  implementing any real adapter.

## Main endpoints
- `GET /health`
- `GET /integrations` — known targets/actions; everything reports `disabled`.
- `POST /dry-run` — validate a proposed action (never executes).

## Inputs / outputs

`POST /dry-run`:

```json
{
  "action": "rotate_certificate",
  "target_type": "ca",
  "asset_name": "payments-api",
  "approved": true,
  "approvals_provided": ["security_review", "change_approval"],
  "parameters": {"reason": "expiring cert"}
}
```

returns:

```json
{
  "mode": "dry_run_disabled",
  "executed": false,
  "recognized_action": true,
  "approval_required": true,
  "required_approvals": ["security_review", "change_approval"],
  "approvals_satisfied": true,
  "would_execute_if_enabled": true,
  "blocked_reasons": ["integration_execution_disabled"],
  "parameter_keys": ["reason"],
  "warnings": []
}
```

- `executed` is **always** `false`.
- `would_execute_if_enabled` shows whether the action would pass validation and
  approvals *if* a real connector existed — it never triggers execution.
- `integration_execution_disabled` is always present in `blocked_reasons`.
- Unknown actions, wrong target types, and secret-like parameters are blocked.

Known actions: `issue_certificate`, `rotate_certificate`, `revoke_certificate`,
`rotate_key`, `sign_artifact`, `update_trust_anchor`, `open_ticket`.

## Run locally

```bash
cd services/integration-service
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8011
```

## Tests

```bash
cd services/integration-service
PYTHONPATH=. pytest -q
```

## Known limitations
- No real CA/KMS/HSM/CI/VPN/ticketing adapters — by design.
- Stateless; does not persist dry-run requests.
- Backs the API Gateway `GET /api/integrations` and `POST /api/integrations/dry-run`.
