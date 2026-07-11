# Network Scanner

## What this service does
- Performs TLS endpoint scans and builds network evidence payloads.
- Collects richer `tls_metadata` for negotiated protocol/cipher details and leaf certificate properties.
- Performs SSH algorithm-negotiation scans: reads the server's identification banner and its
  `SSH_MSG_KEXINIT` packet (both sent in plaintext before any key exchange, per RFC 4253) to
  report which key-exchange, host-key, encryption, and MAC algorithms it offers -- no
  authentication or key exchange is attempted.
- Performs IPsec/IKEv2 algorithm-negotiation scans: sends a single `IKE_SA_INIT` request
  (RFC 7296) offering a spread of encryption/PRF/integrity/DH-group transforms and reports
  whichever single combination the responder selects (or its rejection reason) -- no
  IKE_AUTH, no tunnel is ever established.

## Current role in the prototype
- Working prototype agent for network-side evidence collection and optional ingest into `inventory-service`.

## Main endpoints or functions
- CLI entrypoint: `cmd/scanner/main.go`
- Main flow: `scanner.ScanTLS(target, insecure, timeout)`, `scanner.ScanSSH(target, timeout)`,
  or `scanner.ScanIPsec(target, timeout)` (selected via `-protocol`), and optional
  `client.PostScan(...)`

## Inputs / outputs
- Input: CLI flags (`-target`, `-protocol` [`tls` default, `ssh`, or `ipsec`], `-insecure`
  [tls only], `-timeout`, optional `-ingest`, optional `-workspace-id` to group this scan
  under an existing workspace -- see `services/inventory-service/README.md`'s workspace
  model). For `-protocol ipsec`, `-target` must include the IKE port, e.g. `10.0.0.6:500`.
- Output: JSON TLS, SSH, or IPsec evidence (stdout) or ingest response JSON.

## TLS Evidence Output Contract
`tls_metadata` is always present in output JSON.

Canonical shape:
- `tls_metadata`
  - `collected`
  - `target`
  - `port`
  - `server_name`
  - `protocol_version`
  - `cipher_suite`
  - `certificate` (object on success, `null` when unavailable)
    - `subject`
    - `issuer`
    - `not_before`
    - `not_after`
    - `signature_algorithm`
    - `public_key_algorithm`
    - `public_key_size`
    - `fingerprint_sha256`
  - `certificate_chain` (always present)
    - `available`
    - `length`
    - `certificates` (always present array; empty when unavailable)
      - `position`
      - `subject`
      - `issuer`
      - `not_before`
      - `not_after`
      - `signature_algorithm`
      - `public_key_algorithm`
      - `public_key_size`
      - `fingerprint_sha256`
    - `errors` (`[]` when available, non-empty when unavailable)
  - `errors` (`[]` when no errors)

Fields are best-effort. When TLS collection fails, output remains stable with `collected=false`, empty `protocol_version`/`cipher_suite`, `certificate=null`, always-present `certificate_chain`, and populated `errors` values.

`certificate_chain` is a summary of certificates presented by the peer TLS connection state only. It is not a full trust validation result, does not fetch missing intermediates, and does not perform OCSP/AIA lookups.

## SSH Evidence Output Contract
`ssh_metadata` is always present in output JSON (with `collected=false` on a TLS-mode scan, or
when an SSH-mode scan fails).

Canonical shape:
- `ssh_metadata`
  - `collected`
  - `target`
  - `port`
  - `server_banner` (the server's SSH identification string, e.g. `SSH-2.0-OpenSSH_9.6`)
  - `kex_algorithms`
  - `server_host_key_algorithms`
  - `encryption_algorithms_client_to_server`
  - `encryption_algorithms_server_to_client`
  - `mac_algorithms_client_to_server`
  - `mac_algorithms_server_to_client`
  - `errors` (`[]` when no errors)

These are the algorithm name-lists the server offers in its `SSH_MSG_KEXINIT` packet -- what it
is willing to negotiate, not what a completed session would actually use. The scanner reports
them as neutral facts (mirroring how `tls_metadata` reports `signature_algorithm`/
`public_key_algorithm` without judging them); classifying an offered algorithm as
quantum-vulnerable or weak is a downstream deterministic-analysis-layer concern, not this
collector's job.

## IPsec/IKEv2 Evidence Output Contract
`ipsec_metadata` is always present in output JSON (with `collected=false` on a TLS/SSH-mode
scan, or when an IPsec-mode scan gets no response).

Canonical shape:
- `ipsec_metadata`
  - `collected` (true once a real, SPI-matched `IKE_SA_INIT` response arrives -- regardless
    of whether the responder accepted or rejected the proposal)
  - `target`
  - `port`
  - `ike_version` (e.g. `"2.0"`)
  - `selected_encryption`, `selected_prf`, `selected_integrity`, `selected_dh_group`
    (populated when the responder accepts a transform)
  - `rejected_notify` (populated instead, e.g. `"NO_PROPOSAL_CHOSEN"`, when the responder
    declines every offered transform -- not set if the response also carries an accepted
    proposal, since a real accept can legitimately carry informational Notify payloads too,
    e.g. NAT-detection or vendor-specific extensions)
  - `errors` (`[]` when no errors)

The offered proposal deliberately spans modern and legacy/weak options in the same request
(AES-CBC-256/128 and 3DES; SHA2-256 and SHA1 PRF/integrity; 2048-bit and 1024-bit MODP DH) so
the responder's selection is itself informative -- e.g. a responder that picks 3DES or a
1024-bit group even though stronger options were also offered reveals its actual ceiling. No
real Diffie-Hellman key exchange is performed (the KE payload carries random bytes of the
correct length); the exchange never proceeds past `IKE_SA_INIT`.

## Timeout and scanning behavior
- The scanner remains non-aggressive: a single TLS dial attempt; for SSH, a single TCP
  connection followed by one identification-banner read and one `SSH_MSG_KEXINIT` packet
  read; for IPsec, a single UDP `IKE_SA_INIT` request and one response read -- no
  authentication, key exchange completion, or retry is attempted for any protocol.
  Configurable timeout (`-timeout`, default `5s`) applies to all three.
- No async or parallel scanning behavior is introduced.

## Sample output (success)
```json
{
  "source": "network",
  "tls_metadata": {
    "collected": true,
    "target": "example.com",
    "port": 443,
    "server_name": "example.com",
    "protocol_version": "TLS 1.3",
    "cipher_suite": "TLS_AES_256_GCM_SHA384",
    "certificate": {
      "subject": "CN=*.example.com,O=Example Corp",
      "issuer": "CN=Example Issuing CA",
      "not_before": "2026-01-01T00:00:00Z",
      "not_after": "2027-01-01T23:59:59Z",
      "signature_algorithm": "SHA256-RSA",
      "public_key_algorithm": "RSA",
      "public_key_size": 2048,
      "fingerprint_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    },
    "certificate_chain": {
      "available": true,
      "length": 2,
      "certificates": [
        {
          "position": 0,
          "subject": "CN=*.example.com,O=Example Corp",
          "issuer": "CN=Example Issuing CA",
          "not_before": "2026-01-01T00:00:00Z",
          "not_after": "2027-01-01T23:59:59Z",
          "signature_algorithm": "SHA256-RSA",
          "public_key_algorithm": "RSA",
          "public_key_size": 2048,
          "fingerprint_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        }
      ],
      "errors": []
    },
    "errors": []
  },
  "assets": [
    {
      "asset_type": "endpoint",
      "name": "example.com:443",
      "criticality": 3,
      "environment": "unknown",
      "lifecycle_years": 3
    }
  ]
}
```

## Sample output (SSH success)
```json
{
  "source": "network",
  "ssh_metadata": {
    "collected": true,
    "target": "10.0.0.5",
    "port": 22,
    "server_banner": "SSH-2.0-OpenSSH_9.6",
    "kex_algorithms": ["curve25519-sha256", "diffie-hellman-group14-sha256"],
    "server_host_key_algorithms": ["rsa-sha2-512", "ssh-ed25519"],
    "encryption_algorithms_client_to_server": ["chacha20-poly1305@openssh.com", "aes256-gcm@openssh.com"],
    "encryption_algorithms_server_to_client": ["chacha20-poly1305@openssh.com", "aes256-gcm@openssh.com"],
    "mac_algorithms_client_to_server": ["hmac-sha2-256"],
    "mac_algorithms_server_to_client": ["hmac-sha2-256"],
    "errors": []
  },
  "assets": [
    {
      "asset_type": "endpoint",
      "name": "10.0.0.5:22",
      "criticality": 3,
      "environment": "unknown",
      "lifecycle_years": 3
    }
  ]
}
```

## Sample output (IPsec success)
```json
{
  "source": "network",
  "ipsec_metadata": {
    "collected": true,
    "target": "10.0.0.6",
    "port": 500,
    "ike_version": "2.0",
    "selected_encryption": "AES-CBC",
    "selected_prf": "HMAC-SHA2-256",
    "selected_integrity": "HMAC-SHA2-256-128",
    "selected_dh_group": "2048-bit MODP",
    "errors": []
  },
  "assets": [
    {
      "asset_type": "endpoint",
      "name": "10.0.0.6:500",
      "criticality": 3,
      "environment": "unknown",
      "lifecycle_years": 3
    }
  ]
}
```

## Current status
- Working prototype service. SSH scanning verified live against a real `sshd` (this machine's
  own, including a real post-quantum-hybrid KEX algorithm,
  `sntrup761x25519-sha512@openssh.com`, correctly captured) and ingested end to end through
  `inventory-service` (`ssh_evidence` on the scan record). IPsec/IKEv2 scanning verified live
  against a real strongSwan `charon` daemon -- both the accept path (a configured connection
  selecting AES-CBC-256/HMAC-SHA2-256/2048-bit MODP from the offered spread) and the
  no-connection-configured `NO_PROPOSAL_CHOSEN` rejection path -- and ingested end to end
  through `inventory-service` (`ipsec_evidence` on the scan record).

## How to run tests
- `cd agents/network-scanner && go test ./...`

## Known limitations
- Only IKEv2 is implemented; IKEv1/ISAKMP (a different header and payload format) and
  non-IKE VPN protocols (OpenVPN, WireGuard, L2TP/PPTP) are out of scope.
- `ssh_metadata`'s algorithm lists are ingested, persisted (`inventory-service`'s
  `ssh_evidence`), and wired into risk-engine's `weak_ssh_kex_detected`/
  `legacy_ssh_host_key_detected`/`weak_ssh_cipher_detected`/`weak_ssh_mac_detected`
  signals (see `services/risk-engine/README.md`) -- the scanner itself still only
  reports the offered algorithms as neutral facts, never judging them.
- `ipsec_metadata`'s selected transforms are ingested, persisted (`inventory-service`'s
  `ipsec_evidence`), and wired into risk-engine's `legacy_ipsec_dh_group_detected`/
  `weak_ipsec_encryption_detected`/`weak_ipsec_integrity_detected`/`weak_ipsec_prf_detected`
  signals (see `services/risk-engine/README.md`) -- the scanner itself still only reports the
  responder's selected transform as a neutral fact, never judging it.
- Not exercised in `scripts/run_product_demo.sh` (that script's own bash/openssl-based fixture
  setup can't easily fake a real SSH server or IKE responder); covered instead by Go unit
  tests against scripted fake servers plus manual live verification against this machine's
  real `sshd` and (temporarily installed for verification) `strongswan`.
