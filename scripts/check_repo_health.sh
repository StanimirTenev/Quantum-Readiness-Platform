#!/usr/bin/env bash
# Linux/CI-friendly port of check_repo_health.ps1.
#
# One command to catch the classes of problem that have bitten us:
#   - wrong branch / detached HEAD / out of sync with remote
#   - wrong checkout (CRLF autocrlf that breaks byte-hash tooling, dirty tree)
#   - missing / unwired scripts (services referenced by start_all.sh that do
#     not exist, README-referenced scripts that are gone, empty scripts)
#   - stale reports (generated reports whose verdict is FAIL)
#
# Prints a PASS/WARN/FAIL table, writes reports/repo-health-report.md, and
# exits non-zero if any check is FAIL (WARN does not fail the run).
#
# Usage:
#   bash scripts/check_repo_health.sh [--expected-branch main] [--fetch]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_BRANCH="main"
DO_FETCH=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --expected-branch) EXPECTED_BRANCH="$2"; shift 2 ;;
        --fetch) DO_FETCH=1; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

declare -a NAMES=()
declare -a STATUSES=()
declare -a DETAILS=()

add_result() {
    local name="$1" status="$2" detail="${3:-}"
    NAMES+=("$name")
    STATUSES+=("$status")
    DETAILS+=("$detail")
    if [[ -n "$detail" ]]; then
        echo "[$status] $name -- $detail"
    else
        echo "[$status] $name"
    fi
}

echo "== QRP repository health =="
echo "root: $ROOT"
echo ""

# ---------------------------------------------------------------------------
# Git / branch / checkout
# ---------------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
    add_result "git available" "FAIL" "git executable not found"
elif [[ ! -d "$ROOT/.git" ]]; then
    add_result "git repository" "FAIL" "no .git directory at repo root"
else
    add_result "git available" "PASS" "$(command -v git)"

    head="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")"
    if [[ "$head" == "HEAD" ]]; then
        add_result "detached HEAD" "FAIL" "HEAD is detached; checkout a branch"
    else
        add_result "on a branch" "PASS" "$head"
        if [[ "$head" != "$EXPECTED_BRANCH" ]]; then
            add_result "expected branch" "WARN" "on '$head', expected '$EXPECTED_BRANCH'"
        else
            add_result "expected branch" "PASS" "$head"
        fi
    fi

    if [[ "$DO_FETCH" -eq 1 ]]; then
        git -C "$ROOT" fetch --quiet >/dev/null 2>&1 || true
    fi

    tracked_count="$(git -C "$ROOT" status --porcelain 2>/dev/null | grep -vc '^??' || true)"
    untracked_count="$(git -C "$ROOT" status --porcelain 2>/dev/null | grep -c '^??' || true)"
    if [[ "$tracked_count" -gt 0 ]]; then
        add_result "working tree clean" "WARN" "$tracked_count uncommitted change(s)"
    else
        add_result "working tree clean" "PASS" ""
    fi
    if [[ "$untracked_count" -gt 0 ]]; then
        add_result "no untracked files" "WARN" "$untracked_count untracked file(s)"
    else
        add_result "no untracked files" "PASS" ""
    fi

    upstream="$(git -C "$ROOT" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || true)"
    if [[ -n "$upstream" ]]; then
        counts="$(git -C "$ROOT" rev-list --left-right --count "$upstream...HEAD" 2>/dev/null || true)"
        if [[ -n "$counts" ]]; then
            behind="$(echo "$counts" | awk '{print $1}')"
            ahead="$(echo "$counts" | awk '{print $2}')"
            if [[ "$behind" -gt 0 || "$ahead" -gt 0 ]]; then
                suffix=""
                [[ "$DO_FETCH" -eq 0 ]] && suffix=" (run --fetch for fresh)"
                add_result "in sync with $upstream" "WARN" "ahead $ahead, behind $behind$suffix"
            else
                add_result "in sync with $upstream" "PASS" ""
            fi
        fi
    else
        add_result "upstream tracking" "INFO" "no upstream configured for $head"
    fi

    autocrlf="$(git -C "$ROOT" config core.autocrlf 2>/dev/null || true)"
    if [[ "$autocrlf" == "true" ]]; then
        add_result "line-ending safety" "WARN" "core.autocrlf=true -- byte-hash tooling (evidence bundle) needs LF-normalized regeneration"
    else
        add_result "line-ending safety" "PASS" "core.autocrlf=${autocrlf:-unset}"
    fi
fi

# ---------------------------------------------------------------------------
# Script / service wiring (missing script class)
# ---------------------------------------------------------------------------
if [[ -f "$ROOT/scripts/start_all.sh" ]]; then
    wiring="$(python3 - "$ROOT" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
content = (root / "scripts" / "start_all.sh").read_text(encoding="utf-8")
pattern = re.compile(r'start_service\s+"([^"]+)"\s+"\$ROOT/([^"]+)"\s+"(\d+)"\s+"([^"]+)"')
missing = []
for name, svc_dir, _port, target in pattern.findall(content):
    module_path = target.split(":")[0].replace(".", "/")
    module_file = root / svc_dir / f"{module_path}.py"
    if not (root / svc_dir).is_dir():
        missing.append(f"{name}: dir missing ({svc_dir})")
    elif not module_file.is_file():
        missing.append(f"{name}: entrypoint missing ({module_path}.py)")
print("; ".join(missing))
PY
)"
    if [[ -n "$wiring" ]]; then
        add_result "start_all service wiring" "FAIL" "$wiring"
    else
        add_result "start_all service wiring" "PASS" "all referenced services present"
    fi
else
    add_result "start_all.sh present" "WARN" "scripts/start_all.sh not found"
fi

# scripts referenced in README that no longer exist
if [[ -f "$ROOT/README.md" ]]; then
    readme_check="$(python3 - "$ROOT" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
text = (root / "README.md").read_text(encoding="utf-8")
refs = sorted(set(re.findall(r'scripts/[\w./-]+\.(?:sh|ps1)', text)))
gone = [r for r in refs if not (root / r).exists()]
if gone:
    print("WARN")
    print(f"missing: {', '.join(gone)}")
else:
    print("PASS")
    print(f"{len(refs)} referenced script(s) exist")
PY
)"
    readme_status="$(echo "$readme_check" | sed -n '1p')"
    readme_detail="$(echo "$readme_check" | sed -n '2p')"
    add_result "README script references" "$readme_status" "$readme_detail"
fi

# empty scripts
empty_scripts="$(find "$ROOT/scripts" -maxdepth 1 -type f \( -name "*.sh" -o -name "*.ps1" \) -empty -printf '%f\n' 2>/dev/null | paste -sd ', ' -)"
if [[ -n "$empty_scripts" ]]; then
    add_result "no empty scripts" "WARN" "$empty_scripts"
else
    add_result "no empty scripts" "PASS" ""
fi

# ---------------------------------------------------------------------------
# Stale reports (FAIL verdicts)
# ---------------------------------------------------------------------------
if [[ -d "$ROOT/reports" ]]; then
    stale_check="$(python3 - "$ROOT" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
heading_re = re.compile(r'^##\s*Result\s*\r?\n+\s*FAIL\b', re.MULTILINE)
inline_re = re.compile(r'^\s*(overall\s+result|result|status)\s*:\s*FAIL\b', re.MULTILINE | re.IGNORECASE)
fail_reports = []
for f in sorted((root / "reports").rglob("*.md")):
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    if heading_re.search(content) or inline_re.search(content):
        fail_reports.append(str(f.relative_to(root)))
print("; ".join(fail_reports))
PY
)"
    if [[ -n "$stale_check" ]]; then
        add_result "no FAIL-verdict reports" "FAIL" "$stale_check"
    else
        add_result "no FAIL-verdict reports" "PASS" ""
    fi
fi

# ---------------------------------------------------------------------------
# Summary + report
# ---------------------------------------------------------------------------
fail_count=0
warn_count=0
pass_count=0
for status in "${STATUSES[@]}"; do
    case "$status" in
        FAIL) fail_count=$((fail_count + 1)) ;;
        WARN) warn_count=$((warn_count + 1)) ;;
        PASS) pass_count=$((pass_count + 1)) ;;
    esac
done
if [[ "$fail_count" -gt 0 ]]; then
    overall="FAIL"
elif [[ "$warn_count" -gt 0 ]]; then
    overall="WARN"
else
    overall="PASS"
fi

echo ""
echo "== Health: $overall ($pass_count PASS, $warn_count WARN, $fail_count FAIL) =="

mkdir -p "$ROOT/reports"
{
    echo "# Repository Health Report"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    echo "Overall: $overall ($pass_count PASS, $warn_count WARN, $fail_count FAIL)"
    echo ""
    echo "| Check | Status | Detail |"
    echo "| --- | --- | --- |"
    for i in "${!NAMES[@]}"; do
        echo "| ${NAMES[$i]} | ${STATUSES[$i]} | ${DETAILS[$i]} |"
    done
} > "$ROOT/reports/repo-health-report.md"
echo "Report: $ROOT/reports/repo-health-report.md"

[[ "$fail_count" -eq 0 ]]
