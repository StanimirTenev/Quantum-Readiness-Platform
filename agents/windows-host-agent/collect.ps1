#requires -Version 7.0
<#
.SYNOPSIS
  Windows host evidence collector for QRP (read-only, redacted, aggregate).

.DESCRIPTION
  Scans the local Windows host and emits the documented Windows evidence contract
  (see docs/windows-evidence-fixture-contract.md): OS metadata, installed-software
  and crypto-package indicators, certificate-store indicators, crypto-relevant
  services, SCHANNEL/TLS protocol posture, domain membership and machine role.
  Everything is aggregate and redacted — no hostnames, domains, IPs, certificate
  subjects, secrets, or private keys are collected or exported.

  It also emits a safe, fingerprint-able `certificate_crypto_surface`: per
  certificate the public-key algorithm + size and signature algorithm (no
  subjects, no thumbprints, no private material). With -Assess it feeds each
  certificate through a running API Gateway `/api/assess` and prints the real
  readiness/attribution for this machine.

.PARAMETER OutFile
  Where to write the evidence JSON. Default: agents/windows-host-agent/output/windows-evidence.json

.PARAMETER MaxCerts
  Cap on certificates enumerated per store. Default: 50.

.PARAMETER Assess
  API Gateway base URL (e.g. http://127.0.0.1:8000). If set, each collected
  certificate is assessed and a short readiness line is printed.

.EXAMPLE
  pwsh agents/windows-host-agent/collect.ps1
  pwsh agents/windows-host-agent/collect.ps1 -Assess http://127.0.0.1:8000
#>
[CmdletBinding()]
param(
    [string]$OutFile,
    [int]$MaxCerts = 50,
    [string]$Assess
)

$ErrorActionPreference = "Stop"

$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $OutFile) { $OutFile = Join-Path $PSScriptRoot "output/windows-evidence.json" }

$warnings = [System.Collections.Generic.List[string]]::new()
$errors = [System.Collections.Generic.List[string]]::new()
function Safe([scriptblock]$block, [string]$label, $fallback) {
    try { & $block } catch { $errors.Add("${label}: $($_.Exception.Message)"); $fallback }
}

$CRYPTO_SOFTWARE = 'openssl|openssh|libressl|wolfssl|gnutls|bouncycastle|gpg|gnupg|putty|openvpn|wireguard|stunnel|nginx|apache|nmap|keepass|veracrypt'
$CRYPTO_SERVICES = 'ssh|openvpn|wireguard|cert|crypt|keyiso|scard|schannel|certprop|vault'

# --- OS metadata + machine role ---
$os = Safe { Get-CimInstance Win32_OperatingSystem } "os_metadata" $null
$cs = Safe { Get-CimInstance Win32_ComputerSystem } "computer_system" $null
$productType = if ($os) { [int]$os.ProductType } else { 1 }   # 1=workstation, 2=DC, 3=server
$arch = if ($os -and $os.OSArchitecture -match '64') { "x86_64" } elseif ($os) { "x86" } else { "unknown" }
$versionFamily = switch ($productType) { 1 { "windows_workstation" } 2 { "windows_domain_controller" } 3 { "windows_server" } default { "windows_server_or_workstation" } }

# --- Installed software (aggregate only; names not retained) ---
$uninstallPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
)
$softwareNames = Safe {
    $names = foreach ($p in $uninstallPaths) {
        Get-ItemProperty $p -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | Select-Object -Expand DisplayName
    }
    @($names)
} "installed_software" @()
$totalSoftware = $softwareNames.Count
$cryptoSoftware = @($softwareNames | Where-Object { $_ -match $CRYPTO_SOFTWARE }).Count

# --- Certificate stores (aggregate + safe per-cert crypto surface) ---
$stores = @("LocalMachine\My", "LocalMachine\Root", "LocalMachine\CA")
$certSurface = [System.Collections.Generic.List[object]]::new()
$now = Get-Date
foreach ($store in $stores) {
    Safe {
        $certs = Get-ChildItem "Cert:\$store" -ErrorAction SilentlyContinue | Select-Object -First $MaxCerts
        foreach ($c in $certs) {
            $sig = if ($c.SignatureAlgorithm) { $c.SignatureAlgorithm.FriendlyName } else { $null }
            $pubAlg = if ($c.PublicKey -and $c.PublicKey.Oid) { $c.PublicKey.Oid.FriendlyName } else { $null }
            $size = 0
            try { $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPublicKey($c); if ($rsa) { $size = $rsa.KeySize } } catch {}
            if ($size -eq 0) { try { $ec = [System.Security.Cryptography.X509Certificates.ECDsaCertificateExtensions]::GetECDsaPublicKey($c); if ($ec) { $size = $ec.KeySize } } catch {} }
            if ($size -eq 0) { try { $size = [int]$c.PublicKey.Key.KeySize } catch {} }
            # Safe crypto surface: algorithm/size only, no subject/thumbprint/private material.
            $certSurface.Add([ordered]@{
                    public_key_algorithm = $pubAlg
                    public_key_size      = $size
                    signature_algorithm  = $sig
                    not_after            = $c.NotAfter.ToUniversalTime().ToString("o")
                    expired              = ($c.NotAfter -lt $now)
                })
        }
    } "cert_store_$store" $null
}
# Aggregate counts are derived after collection (the Safe child scope cannot
# mutate outer value-type counters, but the certificate list is shared).
$certCount = $certSurface.Count
$expiredCount = @($certSurface | Where-Object { $_.expired }).Count
$weakSigCount = @($certSurface | Where-Object { $_.signature_algorithm -match '(?i)sha1|md5' }).Count

# --- Crypto-relevant services (aggregate only) ---
$cryptoServices = Safe {
    @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $CRYPTO_SERVICES -or $_.DisplayName -match $CRYPTO_SERVICES }).Count
} "services" 0

# --- SCHANNEL / TLS protocol posture ---
$schannelKey = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols"
$schannelObserved = Safe { Test-Path $schannelKey } "schannel" $false
$legacyEnabled = Safe {
    $legacy = $false
    foreach ($proto in @("SSL 2.0", "SSL 3.0", "TLS 1.0", "TLS 1.1")) {
        $client = Join-Path $schannelKey "$proto\Client"
        if (Test-Path $client) {
            $enabled = (Get-ItemProperty $client -Name Enabled -ErrorAction SilentlyContinue).Enabled
            $disabledByDefault = (Get-ItemProperty $client -Name DisabledByDefault -ErrorAction SilentlyContinue).DisabledByDefault
            if ($enabled -eq 1 -or $disabledByDefault -eq 0) { $legacy = $true }
        }
    }
    $legacy
} "schannel_legacy" $false

# --- Domain membership ---
$domainJoined = if ($cs) { [bool]$cs.PartOfDomain } else { $false }

if ($certCount -eq 0) { $warnings.Add("no_certificates_observed_or_access_denied") }
if (-not $schannelObserved) { $warnings.Add("schannel_policy_key_not_found") }

$evidence = [ordered]@{
    asset            = [ordered]@{
        asset_id           = "win-local-$([guid]::NewGuid().ToString('N').Substring(0,8))"
        asset_type         = if ($productType -eq 3 -or $productType -eq 2) { "server" } else { "endpoint" }
        name               = "redacted-windows-host"
        platform           = "windows"
        hostname_redacted  = $true
        domain_name_redacted = $true
        ip_redacted        = $true
    }
    windows_evidence = [ordered]@{
        os_metadata                 = [ordered]@{ family = "windows"; version_family = $versionFamily; architecture = $arch }
        installed_software_summary  = [ordered]@{ total_observed = $totalSoftware; crypto_relevant_observed = $cryptoSoftware; package_names_redacted = $true }
        crypto_package_indicators   = [ordered]@{ crypto_packages_observed = $cryptoSoftware; package_details_redacted = $true }
        certificate_store_indicators = [ordered]@{
            stores_observed                 = $stores
            certificates_observed_count     = $certCount
            expired_certificates_count      = $expiredCount
            weak_signature_indicators_count = $weakSigCount
            certificate_fingerprints_redacted = $true
            private_keys_exported           = $false
        }
        windows_service_indicators  = [ordered]@{ crypto_relevant_services_observed = $cryptoServices; service_names_redacted = $true }
        schannel_tls_indicators     = [ordered]@{ schannel_policy_observed = [bool]$schannelObserved; tls_legacy_protocols_enabled_observed = [bool]$legacyEnabled; cipher_policy_summary_redacted = $true }
        domain_membership_indicators = [ordered]@{ domain_joined = $domainJoined; domain_name_redacted = $true; ad_details_collected = $false }
        machine_role_indicators     = [ordered]@{ server_role_observed = ($productType -eq 3); workstation_role_observed = ($productType -eq 1); domain_controller_role_observed = ($productType -eq 2) }
        warnings                    = @($warnings)
        errors                      = @($errors)
    }
    # Safe fingerprint-able crypto surface (no subjects / no private material).
    certificate_crypto_surface = @($certSurface)
}

New-Item -ItemType Directory -Force -Path (Split-Path $OutFile) | Out-Null
[System.IO.File]::WriteAllText($OutFile, (($evidence | ConvertTo-Json -Depth 8)), (New-Object System.Text.UTF8Encoding($false)))

$we = $evidence.windows_evidence
Write-Host "== Windows host evidence (redacted, aggregate) ==" -ForegroundColor Cyan
Write-Host ("OS: {0} / {1}  role: {2}" -f $we.os_metadata.version_family, $we.os_metadata.architecture, ($productType))
Write-Host ("Software: {0} observed, {1} crypto-relevant" -f $we.installed_software_summary.total_observed, $we.installed_software_summary.crypto_relevant_observed)
Write-Host ("Certificates: {0} ({1} expired, {2} weak signature)" -f $we.certificate_store_indicators.certificates_observed_count, $we.certificate_store_indicators.expired_certificates_count, $we.certificate_store_indicators.weak_signature_indicators_count)
Write-Host ("Crypto services: {0}  SCHANNEL policy: {1}  legacy TLS: {2}" -f $we.windows_service_indicators.crypto_relevant_services_observed, $we.schannel_tls_indicators.schannel_policy_observed, $we.schannel_tls_indicators.tls_legacy_protocols_enabled_observed)
Write-Host ("Domain joined: {0}" -f $we.domain_membership_indicators.domain_joined)
Write-Host ("Fingerprint-able certificates: {0}" -f $certSurface.Count)
Write-Host "Output: $OutFile"

# --- Optional: feed real certificates through the flow ---
if ($Assess) {
    Write-Host "`n== Assessing real certificates through $Assess ==" -ForegroundColor Cyan
    $i = 0
    foreach ($c in ($certSurface | Where-Object { $_.public_key_algorithm } | Select-Object -First 8)) {
        $i++
        $body = @{
            asset_name   = "win-cert-$i"
            tls_metadata = @{ certificate = @{ algorithms = @{ public_key = $c.public_key_algorithm; signature = $c.signature_algorithm }; key = @{ size_bits = $c.public_key_size } } }
        } | ConvertTo-Json -Depth 8
        try {
            $r = Invoke-RestMethod "$Assess/api/assess" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 8
            Write-Host ("  {0} {1}-bit / {2}: readiness={3}, risk-relevant vuln count={4}" -f $c.public_key_algorithm, $c.public_key_size, $c.signature_algorithm, $r.pqc_readiness.readiness, $r.fingerprint.summary.quantum_vulnerable_count)
        } catch { Write-Host "  assess failed for cert ${i}: $($_.Exception.Message)" -ForegroundColor Yellow }
    }
}
