# Repo/CI Scanner

## What this service does
- Scans a repository's source code and CI/CD pipeline configs for classical
  crypto usage and signing commands.
- Detects hard-coded/imported algorithms (RSA, DSA, DH, ECDSA, EC, MD5, SHA1,
  RC4, DES/3DES) across common languages (Python, Go, Java, JS/TS, Ruby, PHP,
  C/C++/C#, shell/OpenSSL invocations).
- Detects signing commands (`gpg --sign`, `openssl ... -sign`, `cosign sign`,
  `signtool sign`, `jarsigner`, `codesign`) in CI/CD configs
  (`.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`,
  `azure-pipelines.yml`, `.circleci/config.yml`).

## Current role in the prototype
- Working prototype agent. Emits evidence in the standard ingest contract
  (`source=repo`), consumable by `inventory-service` `POST /scans/ingest`
  directly, or via the gateway proxy `POST /api/scans/repo`.

## Main endpoints or functions
- CLI entrypoint: `scanner.py`
- Detection logic: `detectors.py` (`scan_repo`, `scan_source_file`, `scan_ci_file`)

## Inputs / outputs
- Input: CLI flags (`--repo-path`, optional `--out`, optional `--ingest`, optional
  `--workspace-id` to group this scan under an existing workspace -- see
  `services/inventory-service/README.md`'s workspace model).
- Output: JSON ingest payload (stdout or `--out` file), or ingest response
  JSON when `--ingest <inventory-service base URL>` is given.

## Evidence Output Contract
```json
{
  "source": "repo",
  "assets": [{"asset_type": "other", "name": "<repo directory name>"}],
  "crypto_evidence": {
    "known_crypto_files": ["<path>", "..."],
    "repo_scan": {
      "files_scanned": {"source": 0, "ci_config": 0},
      "source_code_findings": [
        {"path": "app/crypto.py", "line": 3, "algorithm": "RSA", "description": "RSA usage", "excerpt": "..."}
      ],
      "ci_pipeline_findings": [
        {"path": ".github/workflows/release.yml", "line": 2, "command_type": "gpg_sign", "excerpt": "..."}
      ],
      "detected_algorithms": ["RSA"]
    }
  }
}
```

Excluded directories: `.git`, `node_modules`, `venv`, `.venv`, `__pycache__`,
`vendor`, `dist`, `build`, `.tox`, `target`.

## Run
```bash
cd agents/repo-ci-scanner
python3 scanner.py --repo-path /path/to/repo
python3 scanner.py --repo-path /path/to/repo --ingest http://127.0.0.1:8001
```

## Current status
- Working prototype. Verified live against `inventory-service` + `risk-engine`
  (ingest -> asset created -> risk score computed).

## How to run tests
- `cd agents/repo-ci-scanner && PYTHONPATH=. python3 -m pytest -q`

## Known limitations
- Detection is regex/line-based, not AST-based — no cross-line or
  string-concatenation detection, and no distinction between real usage and
  comments/string literals.
- No IaC (Terraform/CloudFormation/Kubernetes manifests) scanning yet — only
  source code and CI/CD pipeline configs, per the current architecture scope.
- No inventory/risk-engine wiring beyond the generic `crypto_evidence`
  contract (unlike the Windows host evidence vertical, there is no dedicated
  risk-mapper signal family for repo findings yet).
