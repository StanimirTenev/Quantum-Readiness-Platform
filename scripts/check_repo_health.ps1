#requires -Version 7.0
<#
.SYNOPSIS
  Repository health / status checker for QRP.

.DESCRIPTION
  One command to catch the classes of problem that have bitten us:
    - wrong branch / detached HEAD / out of sync with remote
    - wrong checkout (CRLF autocrlf that breaks byte-hash tooling, dirty tree)
    - missing / unwired scripts (services referenced by start_all.sh that do
      not exist, README-referenced scripts that are gone, empty scripts)
    - stale reports (generated reports whose verdict is FAIL)

  Prints a PASS/WARN/FAIL table, writes reports/repo-health-report.md, and
  exits non-zero if any check is FAIL (WARN does not fail the run).

.PARAMETER ExpectedBranch
  Branch the working copy is expected to be on. Default: main.

.PARAMETER Fetch
  Run `git fetch` first so ahead/behind vs the remote is accurate.

.EXAMPLE
  pwsh scripts/check_repo_health.ps1
  pwsh scripts/check_repo_health.ps1 -Fetch
#>
[CmdletBinding()]
param(
    [string]$ExpectedBranch = "main",
    [switch]$Fetch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

# --- git resolution (fall back to Git for Windows if not on PATH) ---
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
$GitExe = if ($gitCmd) { $gitCmd.Source } else { $null }
if (-not $GitExe) {
    foreach ($c in @("C:\Program Files\Git\cmd\git.exe", "C:\Program Files\Git\bin\git.exe")) {
        if (Test-Path $c) { $GitExe = $c; break }
    }
}
function Git { param([Parameter(ValueFromRemainingArguments = $true)]$a) & $GitExe -C $Root @a 2>$null }

$script:Results = [System.Collections.Generic.List[object]]::new()
function Add-Result([string]$name, [string]$status, [string]$detail = "") {
    $script:Results.Add([pscustomobject]@{ Name = $name; Status = $status; Detail = $detail })
    $color = @{ PASS = "Green"; WARN = "Yellow"; FAIL = "Red"; INFO = "Gray" }[$status]
    Write-Host ("[{0,-4}] {1}{2}" -f $status, $name, ($(if ($detail) { " — $detail" } else { "" }))) -ForegroundColor $color
}

Write-Host "== QRP repository health ==" -ForegroundColor Cyan
Write-Host "root: $Root`n"

# ---------------------------------------------------------------------------
# Git / branch / checkout
# ---------------------------------------------------------------------------
if (-not $GitExe) {
    Add-Result "git available" "FAIL" "git executable not found"
} elseif (-not (Test-Path (Join-Path $Root ".git"))) {
    Add-Result "git repository" "FAIL" "no .git directory at repo root"
} else {
    Add-Result "git available" "PASS" (Split-Path $GitExe -Leaf)

    $head = (Git rev-parse --abbrev-ref HEAD)
    if ($head -eq "HEAD") {
        Add-Result "detached HEAD" "FAIL" "HEAD is detached; checkout a branch"
    } else {
        Add-Result "on a branch" "PASS" $head
        if ($head -ne $ExpectedBranch) {
            Add-Result "expected branch" "WARN" "on '$head', expected '$ExpectedBranch'"
        } else {
            Add-Result "expected branch" "PASS" $head
        }
    }

    if ($Fetch) { Git fetch --quiet | Out-Null }

    $dirty = @(Git status --porcelain)
    $tracked = @($dirty | Where-Object { $_ -notmatch '^\?\?' })
    $untracked = @($dirty | Where-Object { $_ -match '^\?\?' })
    if ($tracked.Count -gt 0) {
        Add-Result "working tree clean" "WARN" "$($tracked.Count) uncommitted change(s)"
    } else {
        Add-Result "working tree clean" "PASS"
    }
    if ($untracked.Count -gt 0) {
        Add-Result "no untracked files" "WARN" "$($untracked.Count) untracked file(s)"
    } else {
        Add-Result "no untracked files" "PASS"
    }

    $upstream = (Git rev-parse --abbrev-ref "@{upstream}")
    if ($upstream) {
        $counts = (Git rev-list --left-right --count "$upstream...HEAD")
        if ($counts) {
            $parts = $counts -split '\s+'
            $behind = [int]$parts[0]; $ahead = [int]$parts[1]
            if ($behind -gt 0 -or $ahead -gt 0) {
                Add-Result "in sync with $upstream" "WARN" "ahead $ahead, behind $behind$(if(-not $Fetch){' (run -Fetch for fresh)'})"
            } else {
                Add-Result "in sync with $upstream" "PASS"
            }
        }
    } else {
        Add-Result "upstream tracking" "INFO" "no upstream configured for $head"
    }

    $autocrlf = (Git config core.autocrlf)
    if ($autocrlf -eq "true") {
        Add-Result "line-ending safety" "WARN" "core.autocrlf=true — byte-hash tooling (evidence bundle) needs LF-normalized regeneration"
    } else {
        Add-Result "line-ending safety" "PASS" "core.autocrlf=$autocrlf"
    }
}

# ---------------------------------------------------------------------------
# Script / service wiring (missing script class)
# ---------------------------------------------------------------------------
$startAll = Join-Path $Root "scripts/start_all.sh"
if (Test-Path $startAll) {
    $content = Get-Content $startAll -Raw
    $rx = [regex]'start_service\s+"([^"]+)"\s+"\$ROOT/([^"]+)"\s+"(\d+)"\s+"([^"]+)"'
    $missing = @()
    foreach ($m in $rx.Matches($content)) {
        $svcDir = Join-Path $Root $m.Groups[2].Value
        $target = $m.Groups[4].Value                     # e.g. app.main:app or main:app
        $modulePath = ($target -split ':')[0] -replace '\.', '/'
        $moduleFile = Join-Path $svcDir "$modulePath.py"
        if (-not (Test-Path $svcDir)) { $missing += "$($m.Groups[1].Value): dir missing ($($m.Groups[2].Value))" }
        elseif (-not (Test-Path $moduleFile)) { $missing += "$($m.Groups[1].Value): entrypoint missing ($modulePath.py)" }
    }
    if ($missing.Count -gt 0) {
        Add-Result "start_all service wiring" "FAIL" ($missing -join "; ")
    } else {
        Add-Result "start_all service wiring" "PASS" "all referenced services present"
    }
} else {
    Add-Result "start_all.sh present" "WARN" "scripts/start_all.sh not found"
}

# scripts referenced in README that no longer exist
$readme = Join-Path $Root "README.md"
if (Test-Path $readme) {
    $text = Get-Content $readme -Raw
    $refs = [regex]::Matches($text, 'scripts/[\w./-]+\.(?:sh|ps1)') | ForEach-Object { $_.Value } | Sort-Object -Unique
    $gone = @($refs | Where-Object { -not (Test-Path (Join-Path $Root $_)) })
    if ($gone.Count -gt 0) {
        Add-Result "README script references" "WARN" "missing: $($gone -join ', ')"
    } else {
        Add-Result "README script references" "PASS" "$($refs.Count) referenced script(s) exist"
    }
}

# empty scripts
$emptyScripts = @(Get-ChildItem (Join-Path $Root "scripts") -File -Include *.sh, *.ps1 -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -eq 0 } | ForEach-Object { $_.Name })
if ($emptyScripts.Count -gt 0) {
    Add-Result "no empty scripts" "WARN" ($emptyScripts -join ', ')
} else {
    Add-Result "no empty scripts" "PASS"
}

# ---------------------------------------------------------------------------
# Stale reports (FAIL verdicts)
# ---------------------------------------------------------------------------
$reportsDir = Join-Path $Root "reports"
if (Test-Path $reportsDir) {
    $failReports = @()
    foreach ($f in Get-ChildItem $reportsDir -Recurse -File -Filter *.md -ErrorAction SilentlyContinue) {
        $c = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $c) { continue }
        $isFail = ($c -match '(?ms)^##\s*Result\s*\r?\n+\s*FAIL\b') -or
                  ($c -match '(?im)^\s*(overall\s+result|result|status)\s*:\s*FAIL\b')
        if ($isFail) { $failReports += $f.FullName.Substring($Root.Length + 1) }
    }
    if ($failReports.Count -gt 0) {
        Add-Result "no FAIL-verdict reports" "FAIL" ($failReports -join "; ")
    } else {
        Add-Result "no FAIL-verdict reports" "PASS"
    }
}

# ---------------------------------------------------------------------------
# Summary + report
# ---------------------------------------------------------------------------
$fail = @($script:Results | Where-Object Status -eq "FAIL").Count
$warn = @($script:Results | Where-Object Status -eq "WARN").Count
$pass = @($script:Results | Where-Object Status -eq "PASS").Count
$overall = if ($fail -gt 0) { "FAIL" } elseif ($warn -gt 0) { "WARN" } else { "PASS" }

Write-Host ""
Write-Host ("== Health: $overall ($pass PASS, $warn WARN, $fail FAIL) ==") -ForegroundColor $(@{ PASS = "Green"; WARN = "Yellow"; FAIL = "Red" }[$overall])

try {
    $lines = @("# Repository Health Report", "", "Generated: $((Get-Date).ToUniversalTime().ToString('u'))", "",
        "Overall: $overall ($pass PASS, $warn WARN, $fail FAIL)", "", "| Check | Status | Detail |", "| --- | --- | --- |")
    foreach ($r in $script:Results) { $lines += "| $($r.Name) | $($r.Status) | $($r.Detail) |" }
    $out = Join-Path $reportsDir "repo-health-report.md"
    New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null
    [System.IO.File]::WriteAllText($out, (($lines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Report: $out"
} catch { Write-Host "Report write failed: $($_.Exception.Message)" -ForegroundColor Yellow }

if ($fail -gt 0) { exit 1 }
