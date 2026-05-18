import json
from pathlib import Path

from tools.evidence_pack.validate_trl7_evidence_bundle_consistency import compute_sha256, render_markdown, validate


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bundle(tmp_path: Path, *, required_missing: int = 0, present=True, sha_ok=True, smoke_pass=True, direct_claim=False):
    md = "TRL 7 achieved is not claimed by this bundle.\nProduction readiness is not claimed by this bundle.\n"
    if direct_claim:
        md += "This bundle is production-ready.\n"
    _write(tmp_path / "reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.md", md)
    smoke = "Result: PASS\n" if smoke_pass else "Result: REVIEW_REQUIRED\n"
    _write(tmp_path / "reports/trl7/operational-evidence/trl7-operational-evidence-bundle-smoke-report.md", smoke)
    _write(tmp_path / "reports/trl7/operational-evidence-safety-scan-report.md", "Result: REVIEW_REQUIRED\n")
    _write(tmp_path / "reports/trl7/operational-evidence-safety-scan-report.json", '{"result": "REVIEW_REQUIRED"}\n')

    art_path = tmp_path / "reports/trl7/alpha.md"
    if present:
        _write(art_path, "hello")
    digest = compute_sha256(art_path) if present else ""
    if not sha_ok and present:
        digest = "0" * 64

    artifacts = [{
        "path": "reports/trl7/alpha.md",
        "exists": present,
        "present": present,
        "size_bytes": art_path.stat().st_size if present else None,
        "sha256": digest if present else None,
        "required_for_trl7_review": True,
    }, {
        "path": "reports/trl7/operational-evidence-safety-scan-report.md",
        "exists": True,
        "present": True,
        "size_bytes": (tmp_path / "reports/trl7/operational-evidence-safety-scan-report.md").stat().st_size,
        "sha256": compute_sha256(tmp_path / "reports/trl7/operational-evidence-safety-scan-report.md"),
        "required_for_trl7_review": True,
    }, {
        "path": "reports/trl7/operational-evidence-safety-scan-report.json",
        "exists": True,
        "present": True,
        "size_bytes": (tmp_path / "reports/trl7/operational-evidence-safety-scan-report.json").stat().st_size,
        "sha256": compute_sha256(tmp_path / "reports/trl7/operational-evidence-safety-scan-report.json"),
        "required_for_trl7_review": True,
    }]
    index = {
        "generated_at_utc": "2026-01-01T00:00:00+00:00",
        "artifacts": artifacts,
        "summary": {
            "total_artifacts": len(artifacts), "present": sum(1 for a in artifacts if a["present"]), "missing": 0,
            "required_present": sum(1 for a in artifacts if a["present"]), "required_missing": required_missing,
            "pass_hint_count": 1, "fail_hint_count": 0, "unknown_hint_count": 0, "review_required_count": 1,
        },
    }
    _write(tmp_path / "reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.json", json.dumps(index))


def test_pass_for_valid_bundle(tmp_path: Path):
    _bundle(tmp_path)
    report = validate(tmp_path)
    assert report["result"] == "PASS"


def test_fail_when_required_missing_non_zero(tmp_path: Path):
    _bundle(tmp_path, required_missing=1)
    assert validate(tmp_path)["result"] == "FAIL"


def test_fail_when_required_artifact_missing_path(tmp_path: Path):
    _bundle(tmp_path, present=False)
    assert validate(tmp_path)["result"] == "FAIL"


def test_fail_when_sha_mismatch(tmp_path: Path):
    _bundle(tmp_path, sha_ok=False)
    assert validate(tmp_path)["result"] == "FAIL"


def test_fail_when_smoke_not_pass(tmp_path: Path):
    _bundle(tmp_path, smoke_pass=False)
    assert validate(tmp_path)["result"] == "FAIL"


def test_pass_forbidden_wording_in_non_claim_boundary_context(tmp_path: Path):
    _bundle(tmp_path)
    assert validate(tmp_path)["result"] == "PASS"


def test_fail_forbidden_wording_direct_claim(tmp_path: Path):
    _bundle(tmp_path, direct_claim=True)
    assert validate(tmp_path)["result"] == "FAIL"


def test_report_structure_and_markdown(tmp_path: Path):
    _bundle(tmp_path)
    report = validate(tmp_path)
    assert {"generated_at_utc", "result", "checks", "summary"}.issubset(report.keys())
    md = render_markdown(report)
    assert "# TRL7 Evidence Bundle Consistency Report" in md
    assert "This consistency check validates local TRL7 evidence-bundle integrity only." in md


def test_input_files_not_modified(tmp_path: Path):
    _bundle(tmp_path)
    p = tmp_path / "reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.json"
    before = p.read_text(encoding="utf-8")
    _ = validate(tmp_path)
    after = p.read_text(encoding="utf-8")
    assert before == after
