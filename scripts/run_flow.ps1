#requires -Version 7.0
<#
.SYNOPSIS
  Run the whole QRP analysis flow locally, end to end.

.DESCRIPTION
  Starts the analysis stack + API Gateway, projects the dependency graph from the
  Stage 2 fixtures, then drives real evidence through the pipeline via the gateway:

    normalize evidence
      -> assess (fingerprint -> pqc-readiness -> attribution -> risk)
      -> scenario re-scoring
      -> graph: evidence-path + blast-radius
      -> integration dry-run (disabled)

  Prints a readable narrative, writes reports/flow-run-report.md, and stops the
  services. This is a demonstration runner (not an assertion suite — see
  scripts/run_full_smoke.ps1 for that).

.PARAMETER Python
  Python executable used to launch uvicorn. Default: python.

.PARAMETER KeepRunning
  Leave the services running after the flow.

.EXAMPLE
  pwsh scripts/run_flow.ps1
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$KeepRunning
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
$Gateway = "http://127.0.0.1:8000"
$FixtureDir = Join-Path $Root "services/inventory-service/tests/fixtures/stage2_evidence"

$Services = [ordered]@{
    "risk-engine"                 = @{ dir = "services/risk-engine";                 port = 8002 }
    "crypto-fingerprint-service"  = @{ dir = "services/crypto-fingerprint-service";  port = 8003 }
    "evidence-normalizer"         = @{ dir = "services/evidence-normalizer";         port = 8009 }
    "scenario-engine"             = @{ dir = "services/scenario-engine";             port = 8006 }
    "integration-service"         = @{ dir = "services/integration-service";         port = 8011 }
    "pqc-readiness-service"       = @{ dir = "services/pqc-readiness-service";       port = 8012 }
    "graph-service"               = @{ dir = "services/graph-service";               port = 8013 }
    "finding-attribution-service" = @{ dir = "services/finding-attribution-service"; port = 8014 }
    "api-gateway"                 = @{ dir = "services/api-gateway";                 port = 8000; target = "main:app" }
}

$script:Procs = @()
$script:Narrative = [System.Collections.Generic.List[string]]::new()

function Say([string]$text, [string]$color = "Gray") { Write-Host $text -ForegroundColor $color; $script:Narrative.Add($text) }
function Wait-Health($port, $timeout = 30) {
    $deadline = (Get-Date).AddSeconds($timeout)
    while ((Get-Date) -lt $deadline) {
        try { if ((Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 2).status -eq "ok") { return $true } } catch { Start-Sleep -Milliseconds 400 }
    }
    return $false
}
function Post($path, $body) { Invoke-RestMethod "$Gateway$path" -Method Post -Body ($body | ConvertTo-Json -Depth 12) -ContentType "application/json" -TimeoutSec 15 }

try {
    Write-Host "== QRP flow ==" -ForegroundColor Cyan

    # 0. Wire gateway upstreams + start the stack.
    $env:CRYPTO_FINGERPRINT_URL = "http://127.0.0.1:8003"
    $env:EVIDENCE_NORMALIZER_URL = "http://127.0.0.1:8009"
    $env:SCENARIO_ENGINE_URL = "http://127.0.0.1:8006"
    $env:INTEGRATION_SERVICE_URL = "http://127.0.0.1:8011"
    $env:PQC_READINESS_URL = "http://127.0.0.1:8012"
    $env:GRAPH_SERVICE_URL = "http://127.0.0.1:8013"
    $env:FINDING_ATTRIBUTION_URL = "http://127.0.0.1:8014"
    $env:RISK_ENGINE_URL = "http://127.0.0.1:8002"
    $env:GRAPH_SNAPSHOT_PATH = Join-Path $Root "reports/graph/latest/graph-snapshot.json"

    foreach ($name in $Services.Keys) {
        $svc = $Services[$name]
        $target = if ($svc.ContainsKey("target")) { $svc.target } else { "app.main:app" }
        $script:Procs += Start-Process -FilePath $Python `
            -ArgumentList "-m", "uvicorn", $target, "--host", "127.0.0.1", "--port", "$($svc.port)" `
            -WorkingDirectory (Join-Path $Root $svc.dir) -PassThru -WindowStyle Hidden
    }
    Write-Host "Starting $($Services.Count) services..." -ForegroundColor Cyan
    foreach ($name in $Services.Keys) {
        if (-not (Wait-Health $Services[$name].port)) { throw "$name did not become healthy" }
    }
    Say ""
    Say "All services healthy."

    # 1. Project the dependency graph from the Stage 2 fixtures.
    Say ""
    Say "== 1. Discovery -> graph projection ==" "Cyan"
    & $Python (Join-Path $Root "tools/graph_projection/project_stage2_fixtures.py") `
        --host (Join-Path $FixtureDir "host_enriched_ingest.json") `
        --network (Join-Path $FixtureDir "network_enriched_ingest.json") `
        --snapshot-out $env:GRAPH_SNAPSHOT_PATH `
        --report-out (Join-Path $Root "reports/graph/latest/graph-projection-report.md") | Out-Null
    $snap = Get-Content $env:GRAPH_SNAPSHOT_PATH -Raw | ConvertFrom-Json
    Say ("Projected snapshot: {0} nodes, {1} edges." -f $snap.nodes.Count, $snap.edges.Count)

    # 2. Normalize the network evidence.
    Say ""
    Say "== 2. Evidence normalization ==" "Cyan"
    $fixture = Get-Content (Join-Path $FixtureDir "network_enriched_ingest.json") -Raw | ConvertFrom-Json
    $norm = Post "/api/normalize" $fixture
    $cert = $norm.network_evidence.certificate
    Say ("Canonical certificate: subject={0}, sig={1}, pubkey={2}, tls={3}" -f $cert.subject, $cert.signature_algorithm, $cert.public_key_algorithm, $norm.network_evidence.tls_version)

    # 3. Assess: fingerprint -> pqc-readiness -> attribution -> risk.
    Say ""
    Say "== 3. Assessment pipeline ==" "Cyan"
    $assess = Post "/api/assess" @{
        asset_name   = "payments-api"
        application  = "payments"
        tls_metadata = $fixture.tls_metadata
        risk_factors = @{ criticality = 5; confidentiality_lifetime = 4; quantum_exposure = 4; blast_radius = 4; vendor_lock_in = 3; migration_difficulty = 3 }
    }
    Say ("Pipeline ran: {0}" -f ($assess.pipeline -join " -> "))
    Say ("Fingerprint readiness: {0} (q-vulnerable {1}, pqc-ready {2}, HNDL {3})" -f $assess.fingerprint.summary.pqc_readiness, $assess.fingerprint.summary.quantum_vulnerable_count, $assess.fingerprint.summary.pqc_ready_count, $assess.fingerprint.summary.hndl_exposure)
    Say ("PQC readiness: {0} (confidence {1})" -f $assess.pqc_readiness.readiness, $assess.pqc_readiness.confidence)
    Say ("Risk: {0} (normalized {1})" -f $assess.risk.rating, $assess.risk.normalized_score_100)
    if ($assess.attribution.attributed_findings.Count -gt 0) {
        Say ("Attribution chain: {0}" -f ($assess.attribution.attributed_findings[0].chain -join " -> "))
    }

    # 4. Scenario re-scoring.
    Say ""
    Say "== 4. Scenario re-scoring (hidden_capability) ==" "Cyan"
    $baseScore = [math]::Round(($assess.risk.normalized_score_100 / 100.0) * 5.0, 2)
    $scenario = Post "/api/scenarios/run" @{ scenario = "hidden_capability"; assets = @(@{ asset_name = "payments-api"; base_score = $baseScore }) }
    $sr = $scenario.results[0]
    Say ("payments-api under {0} (x{1}): normalized {2} -> {3}" -f $scenario.scenario, $scenario.scenario_multiplier, $sr.base_score, "$($sr.normalized_score_100) ($($sr.rating))")

    # 5. Graph attribution + blast radius.
    Say ""
    Say "== 5. Graph traversal ==" "Cyan"
    $finding = ($snap.nodes | Where-Object { $_.type -eq "CryptoFinding" } | Select-Object -First 1)
    if ($finding) {
        $ep = Post "/api/graph/evidence-path" @{ node_id = $finding.id }
        Say ("Evidence path: {0}" -f (($ep.chain | ForEach-Object { "$($_.role)=$($_.label)" }) -join " -> "))
    }
    $rootCa = ($snap.nodes | Where-Object { $_.type -eq "Certificate" -and $_.label -notmatch "internal$" } | Select-Object -First 1)
    $anyCert = ($snap.nodes | Where-Object { $_.type -eq "Certificate" } | Select-Object -Last 1)
    $target = if ($rootCa) { $rootCa.id } else { $anyCert.id }
    $blast = Post "/api/graph/blast-radius" @{ node_id = $target }
    Say ("Blast radius of {0}: {1} affected -> {2}" -f (($snap.nodes | Where-Object { $_.id -eq $target }).label), $blast.affected_count, (($blast.affected | ForEach-Object { $_.node.type }) -join ", "))

    # 6. Controlled execution boundary (dry-run only).
    Say ""
    Say "== 6. Integration dry-run (Trust Zone 4) ==" "Cyan"
    $dry = Post "/api/integrations/dry-run" @{ action = "rotate_certificate"; target_type = "ca"; asset_name = "payments-api"; approved = $true; approvals_provided = @("security_review", "change_approval") }
    Say ("rotate_certificate: executed={0}, would_execute_if_enabled={1}, blocked={2}" -f $dry.executed, $dry.would_execute_if_enabled, ($dry.blocked_reasons -join ","))

    Say ""
    Say "== Flow complete ==" "Green"

} finally {
    try {
        $reportDir = Join-Path $Root "reports"
        New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
        $fence = ([string][char]0x60) * 3
        $lines = @("# QRP Flow Run", "", "Generated: $((Get-Date).ToUniversalTime().ToString('u'))", "", $fence) + $script:Narrative + @($fence, "")
        [System.IO.File]::WriteAllText((Join-Path $reportDir "flow-run-report.md"), (($lines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
        Write-Host "`nReport: $(Join-Path $reportDir 'flow-run-report.md')"
    } catch { Write-Host "Report write failed: $($_.Exception.Message)" -ForegroundColor Yellow }

    if (-not $KeepRunning) {
        foreach ($p in $script:Procs) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
        Write-Host "Services stopped."
    } else {
        Write-Host "Services left running (--KeepRunning)."
    }
}
