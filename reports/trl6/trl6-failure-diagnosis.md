# TRL 6 Failure Diagnosis Note

- Diagnosis category: missing deterministic service preflight before service-dependent checks.
- Primary blocker observed: `inventory-service` unavailable at `http://127.0.0.1:8001/health`, which causes downstream validation/smoke commands to fail.
- Fix: run local preflight startup using `scripts/start_all.sh` (and optional `scripts/status_all.sh`) before required checks, while preserving strict FAIL behavior for required command failures.
