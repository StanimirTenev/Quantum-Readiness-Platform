#requires -Version 7.0
<#
.SYNOPSIS
  Windows/PowerShell end-to-end smoke test for the QRP services that were turned
  from placeholders into working prototypes, exercised through the API Gateway.

.DESCRIPTION
  Starts crypto-fingerprint-service, evidence-normalizer, scenario-engine,
  integration-service and api-gateway locally, waits for health, then runs a
  set of assertions against the gateway routes:
    /health, /api/algorithms, /api/fingerprint, /api/normalize,
    /api/scenarios/run, /api/integrations, /api/integrations/dry-run
  Writes reports/new-services-smoke-report.md and exits non-zero on any failure.

.PARAMETER Python
  Python executable to launch uvicorn with. Default: "python".

.PARAMETER KeepRunning
  Leave the services running after the checks (skip cleanup).

.EXAMPLE
  pwsh scripts/run_full_smoke.ps1
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
$FixtureDir = Join-Path $Root "services/inventory-service/tests/fixtures/stage2_evidence"

# name -> @{ dir; port; target }
$Services = [ordered]@{
    "risk-engine"                = @{ dir = "services/risk-engine";                port = 8002 }
    "crypto-fingerprint-service" = @{ dir = "services/crypto-fingerprint-service"; port = 8003 }
    "evidence-normalizer"        = @{ dir = "services/evidence-normalizer";        port = 8009 }
    "scenario-engine"            = @{ dir = "services/scenario-engine";            port = 8006 }
    "integration-service"        = @{ dir = "services/integration-service";        port = 8011 }
    "pqc-readiness-service"      = @{ dir = "services/pqc-readiness-service";      port = 8012 }
    "graph-service"              = @{ dir = "services/graph-service";              port = 8013 }
    "finding-attribution-service" = @{ dir = "services/finding-attribution-service"; port = 8014 }
    "api-gateway"                = @{ dir = "services/api-gateway";                port = 8000; target = "main:app" }
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

function Post($path, $body) {
    return Invoke-RestMethod "$GatewayBase$path" -Method Post -Body ($body | ConvertTo-Json -Depth 8) -ContentType "application/json" -TimeoutSec 10
}

function Get-Json($path) {
    return Invoke-RestMethod "$GatewayBase$path" -TimeoutSec 10
}

try {
    Write-Host "== Starting services ==" -ForegroundColor Cyan

    # Wire gateway upstreams before it starts (child inherits parent env).
    $env:CRYPTO_FINGERPRINT_URL = "http://127.0.0.1:8003"
    $env:EVIDENCE_NORMALIZER_URL = "http://127.0.0.1:8009"
    $env:SCENARIO_ENGINE_URL = "http://127.0.0.1:8006"
    $env:INTEGRATION_SERVICE_URL = "http://127.0.0.1:8011"
    $env:PQC_READINESS_URL = "http://127.0.0.1:8012"
    $env:GRAPH_SERVICE_URL = "http://127.0.0.1:8013"
    $env:FINDING_ATTRIBUTION_URL = "http://127.0.0.1:8014"
    $env:RISK_ENGINE_URL = "http://127.0.0.1:8002"

    foreach ($name in $Services.Keys) {
        $svc = $Services[$name]
        $target = if ($svc.ContainsKey("target")) { $svc.target } else { "app.main:app" }
        $workdir = Join-Path $Root $svc.dir
        $p = Start-Process -FilePath $Python `
            -ArgumentList "-m", "uvicorn", $target, "--host", "127.0.0.1", "--port", "$($svc.port)" `
            -WorkingDirectory $workdir -PassThru -WindowStyle Hidden
        $script:Procs += $p
        Write-Host "  started $name (PID $($p.Id), port $($svc.port))"
    }

    Write-Host "== Waiting for health ==" -ForegroundColor Cyan
    foreach ($name in $Services.Keys) {
        $port = $Services[$name].port
        if (-not (Wait-Health $port) ) {
            throw "Service '$name' did not become healthy on port $port"
        }
        Write-Host "  healthy: $name"
    }

    Write-Host "== Running checks ==" -ForegroundColor Cyan

    Check "gateway health" {
        $r = Get-Json "/health"
        Assert ($r.status -eq "ok") "expected status ok, got $($r.status)"
    }

    Check "GET /api/algorithms lists known families" {
        $r = Get-Json "/api/algorithms"
        $families = $r.algorithms | ForEach-Object { $_.family }
        Assert ($families -contains "RSA") "RSA not in algorithm list"
        Assert ($families -contains "ML-KEM") "ML-KEM not in algorithm list"
    }

    Check "POST /api/fingerprint classical+pqc mix is hybrid_partial" {
        $r = Post "/api/fingerprint" @{ asset_name = "smoke"; algorithms = @("RSA", "ECDSA", "ML-KEM-768") }
        Assert ($r.summary.pqc_readiness -eq "hybrid_partial") "readiness=$($r.summary.pqc_readiness)"
        Assert ($r.summary.quantum_vulnerable_count -ge 2) "vuln count=$($r.summary.quantum_vulnerable_count)"
        Assert ($r.summary.pqc_ready_count -ge 1) "pqc count=$($r.summary.pqc_ready_count)"
        Assert ($r.summary.hndl_exposure -eq $true) "expected hndl exposure"
    }

    Check "POST /api/fingerprint flags weak RSA key as critical" {
        $body = @{ asset_name = "smoke"; tls_metadata = @{ certificate = @{ algorithms = @{ public_key = "RSA" }; key = @{ size_bits = 1024 } } } }
        $r = Post "/api/fingerprint" $body
        $finding = $r.findings[0]
        Assert ($finding.weak_key -eq $true) "expected weak_key"
        Assert ($finding.severity -eq "critical") "severity=$($finding.severity)"
    }

    Check "POST /api/normalize canonicalizes nested certificate" {
        $body = Get-Content (Join-Path $FixtureDir "network_enriched_ingest.json") -Raw
        $r = Invoke-RestMethod "$GatewayBase/api/normalize" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
        Assert ($r.network_evidence.certificate.signature_algorithm -eq "RSA-PSS-SHA256") "sig=$($r.network_evidence.certificate.signature_algorithm)"
        Assert ($r.network_evidence.tls_version -eq "TLS 1.3") "tls=$($r.network_evidence.tls_version)"
    }

    Check "POST /api/normalize extracts host packages" {
        $body = Get-Content (Join-Path $FixtureDir "host_enriched_ingest.json") -Raw
        $r = Invoke-RestMethod "$GatewayBase/api/normalize" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
        Assert ($r.host_evidence.package_manager -eq "dnf") "pkg mgr=$($r.host_evidence.package_manager)"
        Assert ($r.host_evidence.packages[0].name -eq "openssl") "first pkg=$($r.host_evidence.packages[0].name)"
    }

    Check "POST /api/scenarios/run applies multiplier and ranks" {
        $body = @{ scenario = "hidden_capability"; assets = @(
                @{ asset_name = "high"; base_score = 3.2 },
                @{ asset_name = "low"; base_score = 1.0 }
            ) }
        $r = Post "/api/scenarios/run" $body
        Assert ($r.scenario_multiplier -eq 1.35) "mult=$($r.scenario_multiplier)"
        Assert ($r.results[0].asset_name -eq "high") "top=$($r.results[0].asset_name)"
        Assert ($r.highest_rating -eq "critical") "highest=$($r.highest_rating)"
    }

    Check "POST /api/assess chains fingerprint -> pqc-readiness" {
        $r = Post "/api/assess" @{ asset_name = "smoke"; algorithms = @("RSA", "ML-KEM-768") }
        Assert ($r.fingerprint.summary.pqc_readiness -eq "hybrid_partial") "fp=$($r.fingerprint.summary.pqc_readiness)"
        Assert ($r.pqc_readiness.readiness -eq "hybrid_capable") "readiness=$($r.pqc_readiness.readiness)"
        Assert ($null -eq $r.risk) "expected no risk without risk_factors"
        Assert ($r.pipeline.Count -eq 3) "pipeline=$($r.pipeline -join ',')"
    }

    Check "POST /api/assess includes risk when risk_factors given" {
        $body = @{
            asset_name = "smoke"; algorithms = @("RSA")
            risk_factors = @{ criticality = 5; confidentiality_lifetime = 4; quantum_exposure = 3; blast_radius = 4; vendor_lock_in = 3; migration_difficulty = 3 }
        }
        $r = Post "/api/assess" $body
        Assert ($null -ne $r.risk) "expected risk block"
        Assert ($null -ne $r.risk.rating) "expected risk.rating"
        Assert ($r.pipeline -contains "risk-engine") "risk-engine not in pipeline"
    }

    Check "POST /api/attribute builds the vuln->location->service->asset->cert chain" {
        $body = @{
            asset_name = "payments-api"; application = "payments"
            findings = @(@{ source = "tls_certificate"; location = "tls_metadata.certificate.public_key"; algorithm_family = "RSA"; classification = "classical_vulnerable"; severity = "high"; quantum_vulnerable = $true; raw_value = "RSA" })
            network_evidence = @{ target = "api.example.internal"; port = 443; certificate = @{ subject = "CN=api.example.internal"; fingerprint_sha256 = "abc123" } }
        }
        $r = Post "/api/attribute" $body
        $f = $r.attributed_findings[0]
        Assert ($f.location.value -eq "api.example.internal:443") "location=$($f.location.value)"
        Assert ($f.attribution.crypto_object.kind -eq "certificate") "crypto_object=$($f.attribution.crypto_object.kind)"
        Assert ($f.chain[3] -eq "asset:payments-api") "chain asset=$($f.chain[3])"
        Assert ($f.chain[-1] -eq "certificate:CN=api.example.internal") "chain tail=$($f.chain[-1])"
    }

    Check "POST /api/assess includes finding attribution" {
        $r = Post "/api/assess" @{ asset_name = "demo"; algorithms = @("RSA") }
        Assert ($null -ne $r.attribution) "expected attribution block"
        Assert ($r.pipeline -contains "finding-attribution-service") "attribution not in pipeline"
    }

    Check "GET /api/readiness-states lists five states" {
        $r = Get-Json "/api/readiness-states"
        $states = $r.states | ForEach-Object { $_.state }
        foreach ($s in @("classical_only", "hybrid_capable", "pqc_ready", "vendor_blocked", "unknown")) {
            Assert ($states -contains $s) "missing readiness state $s"
        }
    }

    Check "POST /api/pqc-readiness classifies classical-only" {
        $r = Post "/api/pqc-readiness" @{ asset_name = "smoke"; findings = @(@{ classification = "classical_vulnerable" }) }
        Assert ($r.readiness -eq "classical_only") "readiness=$($r.readiness)"
    }

    Check "POST /api/pqc-readiness classifies hybrid and vendor_blocked" {
        $hybrid = Post "/api/pqc-readiness" @{ asset_name = "smoke"; findings = @(@{ classification = "classical_vulnerable" }, @{ classification = "pqc_ready" }) }
        Assert ($hybrid.readiness -eq "hybrid_capable") "hybrid=$($hybrid.readiness)"
        $blocked = Post "/api/pqc-readiness" @{ asset_name = "smoke"; findings = @(@{ classification = "pqc_ready" }); vendor_blocked = $true }
        Assert ($blocked.readiness -eq "vendor_blocked") "blocked=$($blocked.readiness)"
    }

    $graphSnap = @{
        graph_schema_version = "0.1"
        nodes = @(
            @{ id = "asset:a"; type = "Asset"; label = "asset-a" },
            @{ id = "service:s"; type = "Service"; label = "svc" },
            @{ id = "cert:leaf"; type = "Certificate"; label = "leaf" },
            @{ id = "cert:root"; type = "Certificate"; label = "root-ca" }
        )
        edges = @(
            @{ from = "asset:a"; to = "service:s"; type = "RUNS" },
            @{ from = "service:s"; to = "cert:leaf"; type = "USES_CERTIFICATE" },
            @{ from = "cert:leaf"; to = "cert:root"; type = "SIGNED_BY" }
        )
        warnings = @()
    }

    Check "GET /api/graph/queries lists traversal queries" {
        $r = Get-Json "/api/graph/queries"
        $names = $r.queries | ForEach-Object { $_.name }
        foreach ($n in @("blast-radius", "trust-chain", "neighbors")) {
            Assert ($names -contains $n) "missing graph query $n"
        }
    }

    Check "POST /api/graph/blast-radius reaches the dependent asset" {
        $r = Post "/api/graph/blast-radius" @{ node_id = "cert:root"; snapshot = $graphSnap }
        Assert ($r.affected_count -eq 3) "affected=$($r.affected_count)"
        Assert ($r.affected_node_ids -contains "asset:a") "asset not in blast radius"
    }

    Check "POST /api/graph/trust-chain follows SIGNED_BY to root" {
        $r = Post "/api/graph/trust-chain" @{ node_id = "cert:leaf"; snapshot = $graphSnap }
        Assert ($r.root -eq "cert:root") "root=$($r.root)"
        Assert ($r.length -eq 2) "length=$($r.length)"
    }

    Check "POST /api/graph/evidence-path builds vuln->service->asset->cert chain" {
        $evSnap = @{
            graph_schema_version = "0.1"
            nodes = @(
                @{ id = "asset:a"; type = "Asset"; label = "host-a" },
                @{ id = "service:s"; type = "Service"; label = "api:443" },
                @{ id = "cert:leaf"; type = "Certificate"; label = "CN=api" },
                @{ id = "finding:v"; type = "CryptoFinding"; label = "quantum-vulnerable public key (RSA)" }
            )
            edges = @(
                @{ from = "asset:a"; to = "service:s"; type = "RUNS" },
                @{ from = "service:s"; to = "cert:leaf"; type = "USES_CERTIFICATE" },
                @{ from = "service:s"; to = "finding:v"; type = "SERVICE_HAS_FINDING" }
            )
            warnings = @()
        }
        $r = Post "/api/graph/evidence-path" @{ node_id = "finding:v"; snapshot = $evSnap }
        $roles = $r.chain | ForEach-Object { $_.role }
        Assert (($roles -join ',') -eq "vulnerability,service,asset,crypto_object") "roles=$($roles -join ',')"
        Assert ($r.chain[-1].node_id -eq "cert:leaf") "tail=$($r.chain[-1].node_id)"
    }

    Check "GET /api/integrations reports everything disabled" {
        $r = Get-Json "/api/integrations"
        Assert ($r.mode -eq "dry_run_disabled") "mode=$($r.mode)"
        Assert ($r.executed_changes_supported -eq $false) "expected executed_changes_supported false"
    }

    Check "POST /api/integrations/dry-run never executes when approved" {
        $body = @{ action = "rotate_certificate"; target_type = "ca"; asset_name = "smoke"; approved = $true; approvals_provided = @("security_review", "change_approval") }
        $r = Post "/api/integrations/dry-run" $body
        Assert ($r.executed -eq $false) "expected executed false"
        Assert ($r.would_execute_if_enabled -eq $true) "expected would_execute_if_enabled true"
        Assert ($r.blocked_reasons -contains "integration_execution_disabled") "missing execution-disabled block"
    }

    Check "POST /api/integrations/dry-run rejects secret material" {
        $body = @{ action = "rotate_key"; target_type = "hsm"; asset_name = "smoke"; parameters = @{ private_key = "-----BEGIN" } }
        $r = Post "/api/integrations/dry-run" $body
        Assert ($r.blocked_reasons -contains "sensitive_material_rejected") "secret not rejected"
        Assert (@($r.parameter_keys).Count -eq 0) "secret keys echoed back"
    }

} finally {
    $passed = @($script:Results | Where-Object Result -eq "PASS").Count
    $failed = @($script:Results | Where-Object Result -eq "FAIL").Count
    $overall = if ($failed -eq 0 -and $passed -gt 0) { "PASS" } else { "FAIL" }

    # ----- Report (never let report errors skip cleanup) -----
    try {
        Write-Host ""
        Write-Host "== Summary: $overall ($passed passed, $failed failed) ==" -ForegroundColor ($(if ($overall -eq "PASS") { "Green" } else { "Red" }))

        $reportDir = Join-Path $Root "reports"
        New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
        $lines = @()
        $lines += "# New Services Smoke Report"
        $lines += ""
        $lines += "Generated: $((Get-Date).ToUniversalTime().ToString('u'))"
        $lines += ""
        $lines += "Scope: crypto-fingerprint-service, evidence-normalizer, scenario-engine,"
        $lines += "integration-service (dry-run), web-ui gateway routes -- exercised through api-gateway."
        $lines += ""
        $lines += "| Check | Result |"
        $lines += "| --- | --- |"
        foreach ($r in $script:Results) {
            $detail = if ($r.Result -eq "FAIL") { " -- $($r.Detail)" } else { "" }
            $lines += "| $($r.Name)$detail | $($r.Result) |"
        }
        $lines += ""
        $lines += "Result: $overall"
        $reportPath = Join-Path $reportDir "new-services-smoke-report.md"
        Set-Content -Path $reportPath -Value ($lines -join "`n") -Encoding UTF8
        Write-Host "Report: $reportPath"
    } catch {
        Write-Host "Report generation failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    # ----- Cleanup (always) -----
    if (-not $KeepRunning) {
        foreach ($p in $script:Procs) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
        Write-Host "Services stopped."
    } else {
        Write-Host "Services left running (--KeepRunning)."
    }

    if ($overall -ne "PASS") { exit 1 }
}
