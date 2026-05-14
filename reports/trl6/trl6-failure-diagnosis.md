# TRL 6 Failure Diagnosis Note

- Diagnosis category: artifact persistence and missing generated outputs.
- Fix: validation script now creates report/evidence structure and companion markdown artifacts before returning status.
- Behavior: required command failures still produce overall FAIL and non-zero exit.
