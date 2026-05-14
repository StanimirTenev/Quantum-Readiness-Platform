# Copilot Safety Contract Smoke Report

## Timestamp (UTC)
2026-05-14T04:43:48Z

## Scope
- Validate Copilot safety-contract helper module presence.
- Run focused offline Copilot service tests.
- Optionally run existing Copilot offline smoke script when available.

## Checks Run
| Check | Result |
|---|---|
| services/copilot-service/app/provider_config.py | PASS |
| services/copilot-service/app/local_url_validation.py | PASS |
| services/copilot-service/app/context_packaging.py | PASS |
| services/copilot-service pytest -q | PASS |
| optional scripts/run_copilot_offline_smoke.sh | PASS |

## Contract Statements
- No local or external Copilot provider is implemented or activated by this smoke.
- No network access is required for this smoke.

## Result
PASS
