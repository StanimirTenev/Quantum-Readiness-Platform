#requires -Version 7.0
<#
.SYNOPSIS
  Generate an operator / executive migration report from a live assessment.

.DESCRIPTION
  Starts the assessment stack + API Gateway, assesses a set of assets through
  /api/assess, and renders an operator/exec Markdown report via
  tools/report/build_operator_report.py (executive summary, migration waves,
  findings, attribution/evidence chains, boundaries).

  With -WindowsEvidence it also assesses a sample of this host's real
  certificates and includes them as assets.

.EXAMPLE
  pwsh scripts/run_report.ps1
  pwsh scripts/run_report.ps1 -WindowsEvidence
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$WindowsEvidence,
    [string]$OutFile
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Gateway = "http://127.0.0.1:8000"
$FixtureDir = Join-Path $Root "services/inventory-service/tests/fixtures/stage2_evidence"
if (-not $OutFile) { $OutFile = Join-Path $Root "reports/operator-report.md" }

$Services = [ordered]@{
    "risk-engine"                 = 8002
    "crypto-fingerprint-service"  = 8003
    "pqc-readiness-service"       = 8012
    "finding-attribution-service" = 8014
}
$procs = @()
function Wait-Health($port, $t = 30) {
    $d = (Get-Date).AddSeconds($t)
    while ((Get-Date) -lt $d) { try { if ((Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 2).status -eq "ok") { return $true } } catch { Start-Sleep -Milliseconds 400 } }
    return $false
}
function Post($path, $body) { Invoke-RestMethod "$Gateway$path" -Method Post -Body ($body | ConvertTo-Json -Depth 12) -ContentType "application/json" -TimeoutSec 15 }

$HIGH_RISK = @{ criticality = 5; confidentiality_lifetime = 4; quantum_exposure = 4; blast_radius = 4; vendor_lock_in = 3; migration_difficulty = 3 }
$MED_RISK = @{ criticality = 3; confidentiality_lifetime = 3; quantum_exposure = 3; blast_radius = 3; vendor_lock_in = 2; migration_difficulty = 2 }

try {
    Write-Host "Starting assessment stack..." -ForegroundColor Cyan
    $env:CRYPTO_FINGERPRINT_URL = "http://127.0.0.1:8003"
    $env:PQC_READINESS_URL = "http://127.0.0.1:8012"
    $env:FINDING_ATTRIBUTION_URL = "http://127.0.0.1:8014"
    $env:RISK_ENGINE_URL = "http://127.0.0.1:8002"
    foreach ($name in $Services.Keys) {
        $procs += Start-Process $Python -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$($Services[$name])" -WorkingDirectory (Join-Path $Root "services/$name") -PassThru -WindowStyle Hidden
    }
    $procs += Start-Process $Python -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory (Join-Path $Root "services/api-gateway") -PassThru -WindowStyle Hidden
    foreach ($p in $Services.Values) { if (-not (Wait-Health $p)) { throw "service on $p unhealthy" } }
    if (-not (Wait-Health 8000)) { throw "gateway unhealthy" }

    Write-Host "Assessing assets..." -ForegroundColor Cyan
    $assets = [System.Collections.Generic.List[object]]::new()

    $fixture = Get-Content (Join-Path $FixtureDir "network_enriched_ingest.json") -Raw | ConvertFrom-Json
    $assets.Add(@{ asset_name = "payments-api"; application = "payments"; assess = (Post "/api/assess" @{ asset_name = "payments-api"; application = "payments"; tls_metadata = $fixture.tls_metadata; risk_factors = $HIGH_RISK }) })
    $assets.Add(@{ asset_name = "legacy-vpn"; application = "network"; assess = (Post "/api/assess" @{ asset_name = "legacy-vpn"; application = "network"; tls_metadata = @{ certificate = @{ algorithms = @{ public_key = "RSA"; signature = "sha1WithRSAEncryption" }; key = @{ size_bits = 1024 } } }; risk_factors = $HIGH_RISK }) })
    $assets.Add(@{ asset_name = "modern-api"; application = "platform"; assess = (Post "/api/assess" @{ asset_name = "modern-api"; application = "platform"; algorithms = @("ML-KEM-768", "ML-DSA-65"); risk_factors = $MED_RISK }) })

    $environment = "local-fixtures"
    if ($WindowsEvidence) {
        $environment = "windows-host + fixtures"
        Write-Host "Collecting real Windows certificates..." -ForegroundColor Cyan
        $winOut = Join-Path $env:TEMP "qrp-report-win.json"
        & pwsh -NoProfile -File (Join-Path $Root "agents/windows-host-agent/collect.ps1") -OutFile $winOut -MaxCerts 30 2>&1 | Out-Null
        $win = Get-Content $winOut -Raw | ConvertFrom-Json
        $i = 0
        foreach ($c in (@($win.certificate_crypto_surface | Where-Object { $_.public_key_algorithm -and $_.public_key_size -gt 0 }) | Select-Object -First 6)) {
            $i++
            $a = Post "/api/assess" @{ asset_name = "win-cert-$i"; application = "windows-host"; tls_metadata = @{ certificate = @{ algorithms = @{ public_key = $c.public_key_algorithm; signature = $c.signature_algorithm }; key = @{ size_bits = $c.public_key_size } } }; risk_factors = $MED_RISK }
            $assets.Add(@{ asset_name = "win-cert-$i"; application = "windows-host"; assess = $a })
        }
    }

    $bundle = @{ generated_at = (Get-Date).ToUniversalTime().ToString("o"); environment = $environment; assets = @($assets) }
    $bundlePath = Join-Path $env:TEMP "qrp-assessment-bundle.json"
    [System.IO.File]::WriteAllText($bundlePath, ($bundle | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding($false)))

    & $Python (Join-Path $Root "tools/report/build_operator_report.py") --input $bundlePath --out $OutFile
    Write-Host "`n== Executive summary ==" -ForegroundColor Green
    Get-Content $OutFile | Select-Object -Skip 9 -First 12 | ForEach-Object { Write-Host $_ }
    Write-Host "`nReport: $OutFile" -ForegroundColor Cyan

} finally {
    foreach ($p in $procs) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "Services stopped."
}
