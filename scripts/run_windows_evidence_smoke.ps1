#requires -Version 7.0
<#
.SYNOPSIS
  Windows/PowerShell smoke test for the Windows-evidence -> inventory vertical:
  persist a Windows host document and prove the persisted aggregate signals drive
  the risk score.

.DESCRIPTION
  Starts risk-engine, inventory-service (on an isolated temporary database) and
  the api-gateway, then drives the committed Windows evidence fixture (and a few
  in-memory variants of it) through `POST /api/scans/windows`. Asserts that:
    - the document persists as source=host with a single asset,
    - the aggregate normalized signals are stored on the scan,
    - the persisted risk reflects the Windows-aware factors (domain role ->
      blast radius / dependencies; certificate volume + weak/expired ->
      migration difficulty),
    - no raw identifiers leak.
  Uses the fixture (not the live host) so it is deterministic and CI-friendly.
  Writes reports/windows-evidence-smoke-report.md and exits non-zero on failure.

.PARAMETER Python
  Python executable to launch uvicorn with. Default: "python".

.PARAMETER KeepRunning
  Leave the services running after the checks (skip cleanup).

.EXAMPLE
  pwsh scripts/run_windows_evidence_smoke.ps1
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$KeepRunning
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
$GatewayBase = "http://127.0.0.1:8000"
$InventoryBase = "http://127.0.0.1:8001"
$FixturePath = Join-Path $Root "services/inventory-service/tests/fixtures/stage2_evidence/windows_enriched_ingest_example.json"

$Services = [ordered]@{
    "risk-engine"       = @{ dir = "services/risk-engine";       port = 8002 }
    "inventory-service" = @{ dir = "services/inventory-service"; port = 8001 }
    "api-gateway"       = @{ dir = "services/api-gateway";       port = 8000; target = "main:app" }
}

$script:Procs = @()
$script:Results = [System.Collections.Generic.List[object]]::new()

function Assert($condition, $message) {
    if (-not $condition) { throw $message }
}

function Check($name, [scriptblock]$test) {
    try {
        & $test
        $script:Results.Add([pscustomobject]@{ Name = $name; Result = "PASS"; Detail = "" })
        Write-Host "[PASS] $name" -ForegroundColor Green
    } catch {
        $script:Results.Add([pscustomobject]@{ Name = $name; Result = "FAIL"; Detail = $_.Exception.Message })
        Write-Host "[FAIL] $name -> $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Wait-Health($port, $timeoutSec = 30) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 2
            if ($r.status -eq "ok") { return $true }
        } catch { Start-Sleep -Milliseconds 400 }
    }
    return $false
}

# Persist a Windows evidence document through the gateway proxy and return the
# stored scan detail (scan + risks) read back from inventory.
function Persist-Windows($document) {
    $body = $document | ConvertTo-Json -Depth 12
    $resp = Invoke-RestMethod "$GatewayBase/api/scans/windows" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 15
    Assert ($resp.created -eq 1) "expected created=1, got $($resp.created)"
    Assert ($resp.source -eq "host") "expected source=host, got $($resp.source)"
    Assert ([string]::IsNullOrEmpty($resp.scan_id) -eq $false) "missing scan_id"
    return Invoke-RestMethod "$InventoryBase/scans/$($resp.scan_id)" -TimeoutSec 10
}

function Set-CertStore($doc, $count, $expired, $weak) {
    $doc.windows_evidence.certificate_store_indicators.certificates_observed_count = $count
    $doc.windows_evidence.certificate_store_indicators.expired_certificates_count = $expired
    $doc.windows_evidence.certificate_store_indicators.weak_signature_indicators_count = $weak
}

try {
    Write-Host "== Starting services ==" -ForegroundColor Cyan

    # Wire gateway upstreams + isolate the inventory database (child inherits env).
    $env:RISK_ENGINE_URL = "http://127.0.0.1:8002"
    $env:INVENTORY_SERVICE_URL = "http://127.0.0.1:8001"
    $env:INVENTORY_DB_PATH = Join-Path $env:TEMP "qrp-windows-smoke-inventory.db"
    if (Test-Path $env:INVENTORY_DB_PATH) { Remove-Item $env:INVENTORY_DB_PATH -Force -ErrorAction SilentlyContinue }

    foreach ($name in $Services.Keys) {
        $svc = $Services[$name]
        $target = if ($svc.ContainsKey("target")) { $svc.target } else { "app.main:app" }
        $p = Start-Process -FilePath $Python `
            -ArgumentList "-m", "uvicorn", $target, "--host", "127.0.0.1", "--port", "$($svc.port)" `
            -WorkingDirectory (Join-Path $Root $svc.dir) -PassThru -WindowStyle Hidden
        $script:Procs += $p
        Write-Host "  started $name (PID $($p.Id), port $($svc.port))"
    }

    Write-Host "== Waiting for health ==" -ForegroundColor Cyan
    foreach ($name in $Services.Keys) {
        if (-not (Wait-Health $Services[$name].port)) { throw "Service '$name' did not become healthy" }
        Write-Host "  healthy: $name"
    }

    Write-Host "== Running checks ==" -ForegroundColor Cyan

    if (-not (Test-Path $FixturePath)) { throw "fixture not found: $FixturePath" }

    Check "fixture persists as a host scan with a single asset" {
        $doc = Get-Content $FixturePath -Raw | ConvertFrom-Json
        $detail = Persist-Windows $doc
        Assert ($detail.scan.source -eq "host") "source=$($detail.scan.source)"
    }

    Check "stored scan carries the aggregate normalized signals" {
        $doc = Get-Content $FixturePath -Raw | ConvertFrom-Json
        $detail = Persist-Windows $doc
        $sig = $detail.scan.crypto_evidence.windows_normalized_signals
        Assert ($sig.certificates_observed_count -eq 12) "certs=$($sig.certificates_observed_count)"
        Assert ($sig.domain_joined -eq $true) "domain_joined=$($sig.domain_joined)"
        Assert ($sig.private_keys_exported -eq $false) "private_keys_exported=$($sig.private_keys_exported)"
    }

    Check "no raw identifiers leak into the persisted scan" {
        $doc = Get-Content $FixturePath -Raw | ConvertFrom-Json
        $detail = Persist-Windows $doc
        # asset name stays redacted; host_inventory keeps no raw hostname/ips.
        $assets = Invoke-RestMethod "$InventoryBase/assets" -TimeoutSec 10
        Assert (@($assets | Where-Object { $_.name -eq "redacted-windows-host" }).Count -ge 1) "redacted asset missing"
        Assert ([string]::IsNullOrEmpty($detail.scan.host_inventory.hostname)) "hostname leaked: $($detail.scan.host_inventory.hostname)"
        Assert (@($detail.scan.host_inventory.ips).Count -eq 0) "ips leaked"
    }

    Check "domain-joined host widens blast radius and migration difficulty" {
        # Fixture: domain_joined=true, endpoint, 12 certs, 1 expired, 0 weak.
        $doc = Get-Content $FixturePath -Raw | ConvertFrom-Json
        $detail = Persist-Windows $doc
        $r = $detail.risks[0]
        Assert ($null -ne $r) "no risk persisted"
        Assert ($r.rationale.blast_radius -eq 4) "blast_radius=$($r.rationale.blast_radius)"
        # host base 3 + (>=10 certs) 1 + (expired present) 1 = 5.
        Assert ($r.rationale.migration_difficulty -eq 5) "migration_difficulty=$($r.rationale.migration_difficulty)"
    }

    Check "domain controller maximizes blast radius" {
        $doc = Get-Content $FixturePath -Raw | ConvertFrom-Json
        $doc.asset.asset_type = "server"
        $doc.windows_evidence.machine_role_indicators.domain_controller_role_observed = $true
        Set-CertStore $doc 80 3 2
        $detail = Persist-Windows $doc
        $r = $detail.risks[0]
        Assert ($r.rationale.blast_radius -eq 5) "blast_radius=$($r.rationale.blast_radius)"
        Assert ($r.rationale.migration_difficulty -eq 5) "migration_difficulty=$($r.rationale.migration_difficulty)"
    }

    Check "standalone host with a small clean store keeps base factors" {
        $doc = Get-Content $FixturePath -Raw | ConvertFrom-Json
        $doc.windows_evidence.domain_membership_indicators.domain_joined = $false
        $doc.windows_evidence.machine_role_indicators.domain_controller_role_observed = $false
        Set-CertStore $doc 3 0 0
        $detail = Persist-Windows $doc
        $r = $detail.risks[0]
        Assert ($r.rationale.blast_radius -eq 3) "blast_radius=$($r.rationale.blast_radius)"
        Assert ($r.rationale.migration_difficulty -eq 3) "migration_difficulty=$($r.rationale.migration_difficulty)"
    }

} finally {
    $passed = @($script:Results | Where-Object Result -eq "PASS").Count
    $failed = @($script:Results | Where-Object Result -eq "FAIL").Count
    $overall = if ($failed -eq 0 -and $passed -gt 0) { "PASS" } else { "FAIL" }

    try {
        Write-Host ""
        Write-Host "== Summary: $overall ($passed passed, $failed failed) ==" -ForegroundColor ($(if ($overall -eq "PASS") { "Green" } else { "Red" }))

        $reportDir = Join-Path $Root "reports"
        New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
        $lines = @()
        $lines += "# Windows Evidence Smoke Report"
        $lines += ""
        $lines += "Generated: $((Get-Date).ToUniversalTime().ToString('u'))"
        $lines += ""
        $lines += "Scope: Windows evidence -> inventory persistence + Windows-aware risk"
        $lines += "scoring, exercised through api-gateway with an isolated database."
        $lines += ""
        $lines += "| Check | Result |"
        $lines += "| --- | --- |"
        foreach ($r in $script:Results) {
            $detail = if ($r.Result -eq "FAIL") { " -- $($r.Detail)" } else { "" }
            $lines += "| $($r.Name)$detail | $($r.Result) |"
        }
        $lines += ""
        $lines += "Result: $overall"
        $reportPath = Join-Path $reportDir "windows-evidence-smoke-report.md"
        Set-Content -Path $reportPath -Value ($lines -join "`n") -Encoding UTF8
        Write-Host "Report: $reportPath"
    } catch {
        Write-Host "Report generation failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    if (-not $KeepRunning) {
        foreach ($p in $script:Procs) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
        if ($env:INVENTORY_DB_PATH -and (Test-Path $env:INVENTORY_DB_PATH)) {
            Remove-Item $env:INVENTORY_DB_PATH -Force -ErrorAction SilentlyContinue
        }
        Write-Host "Services stopped."
    } else {
        Write-Host "Services left running (--KeepRunning)."
    }

    if ($overall -ne "PASS") { exit 1 }
}
