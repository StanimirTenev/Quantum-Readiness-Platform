# Known Limitations (TRL 6 Validation Context)

- This validation is local-first and intentionally does not claim production readiness.
- Any required command failure results in an overall FAIL.
- Missing required scripts are treated as FAIL and logged under the evidence directory.
