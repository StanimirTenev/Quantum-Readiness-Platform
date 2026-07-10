# Linux Host Agent

## What this service does
- Collects local host inventory and crypto-related evidence from a Linux machine.

## Current role in the prototype
- Working prototype agent for host-side evidence collection and optional ingest into `inventory-service`.

## Main endpoints or functions
- CLI entrypoint: `cmd/agent/main.go`
- Main flow: `collector.Collect()` and optional `client.PostScan(...)` with `-ingest`

## Inputs / outputs
- Input: local OS/files/package state; CLI flags (`-ingest`, `-inventory-url`, `-timeout`).
- Output: JSON evidence payload (stdout) or ingest response JSON.
- Output includes `crypto_evidence.package_metadata` with best-effort crypto/security package metadata collection.
- Output includes `crypto_evidence.cert_indicators.certificate_file_indicators` with best-effort certificate/key footprint discovery based on file names only.
- Output includes `crypto_evidence.cert_indicators.config_file_indicators` with best-effort SSH/TLS/VPN/keystore configuration footprint discovery based on file names/paths only.

## Evidence Output Contract
- Canonical evidence blocks are always present in the JSON payload:
  - `crypto_evidence.package_metadata`
  - `crypto_evidence.cert_indicators.certificate_file_indicators`
  - `crypto_evidence.cert_indicators.config_file_indicators`
- These blocks are best-effort and non-fatal. Collection failures are represented in-block via `collected: false` and populated `errors`, while successful collection with no matches uses `collected: true`, empty arrays, and zero counts.

## Current status
- Working prototype service.

## How to run tests
- `cd agents/linux-host-agent && go test ./...`

## Bounded mode (reliability hardening)
- Every subprocess this agent shells out to (`dpkg-query`, `rpm`, `pacman`, `apk`, `uname`,
  `openssl version`) runs under a 5-second timeout (`commandTimeout` in
  `internal/collector/collector.go`). A stuck package-manager lock -- a real failure mode in
  some sandboxed/containerized environments -- times out with a clear error instead of hanging
  the whole agent forever; the failure is recorded in `package_metadata.errors`, not fatal.
- The whole collection run is additionally bounded by `-timeout` (default 60s, seconds). If
  collection somehow doesn't finish within that window, the agent exits 1 with a clear
  "collector timed out" message on stderr instead of hanging indefinitely.
- `scripts/run_product_demo.sh` passes an explicit `-timeout 30` (its own `AGENT_TIMEOUT_SEC`)
  when invoking this agent, and additionally wraps the whole invocation in its own outer
  `timeout` as a safety net -- see that script's "Demo Reliability Hardening" comments.

## Known limitations
- Evidence depth depends on host permissions, installed tools, and available config paths.
- Package metadata collection is best-effort and non-fatal. If collection fails, `package_metadata.collected` is `false`, `package_manager` becomes `unknown`, and the error is recorded in `package_metadata.errors`.
- Certificate file discovery is limited to standard paths, max traversal depth 3, and max 200 files to avoid broad filesystem scans.
- Certificate file discovery does not read or parse certificate/key contents; it only inspects path names and extensions.
- SSH/TLS/VPN/keystore config discovery does not read or parse config contents; it only inspects file paths and names in standard locations.
- SSH/TLS/VPN/keystore config discovery is limited to standard paths, max traversal depth 3, and max 200 files.

## Certificate file discovery
- Standard paths inspected (if present):
  - `/etc/ssl`
  - `/etc/pki`
  - `/etc/ca-certificates`
  - `/usr/local/share/ca-certificates`
  - `/etc/letsencrypt`
  - `/etc/nginx`
  - `/etc/apache2`
  - `/etc/httpd`
  - `/etc/haproxy`
  - `/etc/openvpn`
  - `/etc/ipsec.d`
  - `/etc/strongswan`
  - `/etc/ssh`
- Matching/classification is deterministic and based on file names/extensions only:
  - `certificate`: `.crt`, `.cer`, `.pem`, `.der`
  - `key`: `.key`, `id_rsa`, `id_ecdsa`, `id_ed25519`
  - `keystore`: `.jks`, `.p12`, `.pfx`, `keystore`
  - `truststore`: `cacerts`, `truststore`
  - `unknown`: crypto-looking names that do not map to a stronger class
- Best-effort and non-fatal: inaccessible directories/files are recorded in `errors`, while the agent continues collection.

## Package metadata collection
- Supported package managers: `dpkg`/`apt` (via `dpkg-query`), `rpm`, `apk`, and `pacman`.
- If no supported package manager is detected, the agent returns:
  - `package_manager: "unknown"`
  - `collected: true`
  - `packages: []`
  - `errors: []`
- The agent only keeps crypto/security-relevant package names (for example: OpenSSL/libssl, SSH, certificates, TLS/network security tooling, Java/OpenJDK/keytool, and common TLS termination services).

## SSH/TLS/VPN config indicators
- Standard paths inspected (if present):
  - `/etc/ssh/sshd_config`
  - `/etc/ssh/ssh_config`
  - `/etc/ssh/sshd_config.d`
  - `/etc/ssh/ssh_config.d`
  - `/etc/nginx`
  - `/etc/apache2`
  - `/etc/httpd`
  - `/etc/haproxy`
  - `/etc/stunnel`
  - `/etc/letsencrypt`
  - `/etc/openvpn`
  - `/etc/ipsec.conf`
  - `/etc/ipsec.d`
  - `/etc/strongswan`
  - `/etc/wireguard`
  - `/etc/java`
  - `/etc/default`
  - `/etc/sysconfig`
- Classification is deterministic and path/name-based only:
  - `sshd_config`/`sshd_config.d` => `ssh_server_config`
  - `ssh_config`/`ssh_config.d` => `ssh_client_config`
  - `nginx.conf`, `apache2.conf`, `httpd.conf`, `haproxy.cfg`, `stunnel.conf`, `sites-enabled`, `conf.d`, `vhosts.d`, and `letsencrypt/renewal` => `tls_server_config`
  - OpenVPN/IPSec/WireGuard patterns (for example: `*.conf` under `/etc/openvpn`, `ipsec.conf`, `strongswan.conf`, `swanctl.conf`, `wg*.conf`) => `vpn_config`
  - `keystore`, `truststore`, `cacerts`, `java.security` => `keystore_config`
  - Other config-like files in the searched locations => `unknown`
- Best-effort and non-fatal: inaccessible directories/files are recorded in `errors`, and collection continues.

### Sample JSON block
```json
{
  "certificate_file_indicators": {
    "collected": true,
    "searched_paths": [
      "/etc/ssl",
      "/etc/pki",
      "/usr/local/share/ca-certificates"
    ],
    "files": [
      {
        "path": "/etc/ssl/certs/ca-certificates.crt",
        "type": "certificate",
        "extension": ".crt",
        "readable": true,
        "source": "standard_path"
      }
    ],
    "counts": {
      "certificate": 1,
      "key": 0,
      "keystore": 0,
      "truststore": 0,
      "unknown": 0
    },
    "errors": []
  }
}
```

### Sample config indicators JSON block
```json
{
  "config_file_indicators": {
    "collected": true,
    "searched_paths": [
      "/etc/ssh/sshd_config",
      "/etc/nginx",
      "/etc/wireguard"
    ],
    "files": [
      {
        "path": "/etc/ssh/sshd_config",
        "type": "ssh_server_config",
        "readable": true,
        "source": "standard_path"
      }
    ],
    "counts": {
      "ssh_server_config": 1,
      "ssh_client_config": 0,
      "tls_server_config": 0,
      "vpn_config": 0,
      "keystore_config": 0,
      "unknown": 0
    },
    "errors": []
  }
}
```
