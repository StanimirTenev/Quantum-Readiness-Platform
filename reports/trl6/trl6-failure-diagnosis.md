# TRL 6 Failure Diagnosis Note

- Diagnosis category: artifact persistence and log-path consistency.
- Fix applied: `scripts/run_trl6_readiness_validation.sh` now deterministically creates `reports/trl6/evidence/` before command execution and uses stable, non-empty log names (for example `run_trl_validation.log`).
- Effect: every required command row in `reports/trl6/trl6-readiness-report.md` now points to an evidence log path that exists, including missing-script and non-zero exit scenarios.
- Follow-up: rerun diagnosis for any remaining command failures; command-level FAIL outcomes are preserved and still drive overall FAIL until resolved.
