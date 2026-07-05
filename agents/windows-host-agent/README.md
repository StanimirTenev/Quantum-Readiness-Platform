# Windows Host Agent (evidence collector)

A read-only, **redacted, aggregate** Windows evidence collector. It scans the
local host and emits the documented Windows evidence contract
(`docs/windows-evidence-fixture-contract.md`) so real Windows crypto posture can
feed the QRP pipeline instead of fixtures.

Unlike the Linux host agent (Go), this is a dependency-free PowerShell 7 script.

## Safety
- Read-only. No changes to the host.
- **No private keys** are collected or exported (`private_keys_exported: false`).
- No secrets, credentials, raw hostnames, domains, IPs, or certificate subjects.
- Aggregate/redacted by design; software/service/certificate details are counted,
  not retained.

## What it collects
- `os_metadata` — family, version family, architecture.
- `installed_software_summary` / `crypto_package_indicators` — counts (crypto-relevant subset).
- `certificate_store_indicators` — cert count, expired count, weak-signature count,
  over `LocalMachine\My|Root|CA`.
- `windows_service_indicators` — crypto-relevant service count.
- `schannel_tls_indicators` — SCHANNEL policy presence, legacy TLS enabled.
- `domain_membership_indicators`, `machine_role_indicators`.
- `certificate_crypto_surface` — a **safe, fingerprint-able** per-certificate list:
  public-key algorithm + size, signature algorithm, expiry. No subjects, no
  thumbprints, no private material.

## Run

```powershell
pwsh agents/windows-host-agent/collect.ps1
# writes agents/windows-host-agent/output/windows-evidence.json (git-ignored)
```

Feed the real certificates through the running pipeline:

```powershell
pwsh scripts/run_full_smoke.ps1 -KeepRunning        # or scripts/run_flow.ps1 -KeepRunning
pwsh agents/windows-host-agent/collect.ps1 -Assess http://127.0.0.1:8000
```

`-Assess` posts each collected certificate's algorithms to the gateway
`/api/assess` and prints the real PQC readiness — this machine's certificates
classified by the deterministic pipeline.

Options: `-OutFile <path>`, `-MaxCerts <n>` (default 50), `-Assess <gatewayUrl>`.

## Status / limitations
- First Windows collector implementation (the architecture lists Windows as
  future work; the fixture contract and inventory acceptance were already defined).
- AD/certificate-estate discovery and Windows ingestion into inventory-service
  remain out of scope (aggregate signals only, per the Windows signal-mapping design).
