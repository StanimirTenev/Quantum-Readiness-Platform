import hashlib
from pathlib import Path

from tools.evidence_pack.build_trl7_operational_evidence_bundle import build_index, build_markdown


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_index_shape_and_missing_counts(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/trl7-operational-readiness-report.md", "Overall Result: PASS\n")
    index = build_index(tmp_path)
    assert set(index.keys()) == {"generated_at_utc", "purpose", "summary", "artifacts"}
    assert index["summary"]["total_artifacts"] == 8
    assert index["summary"]["present"] == 1
    assert index["summary"]["required_missing"] == 6
    assert "review_required_count" in index["summary"]


def test_required_dry_run_report_status_and_hash(tmp_path: Path) -> None:
    content = "Overall Result: PASS\n"
    _write(tmp_path / "reports/trl7/trl7-operational-dry-run-report.md", content)
    index = build_index(tmp_path)
    artifact = next(a for a in index["artifacts"] if a["artifact_id"] == "trl7_operational_dry_run_report")
    assert artifact["exists"] is True
    assert artifact["present"] is True
    assert artifact["status_hint"] == "PASS"
    assert artifact["sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_markdown_contains_boundary_statements(tmp_path: Path) -> None:
    md = build_markdown(build_index(tmp_path))
    assert "TRL 7 achieved is not claimed by this bundle." in md
    assert "Production readiness is not claimed by this bundle." in md
    assert "This bundle supports TRL7 operational pilot preparation only." in md
    assert "This bundle does not run tests, start services, regenerate evidence, or perform remediation." in md


def test_safety_scan_artifacts_configured_and_status_pass(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/operational-evidence-safety-scan-report.md", "Result: PASS\nHIGH=0 MEDIUM=0 LOW=0\n")
    _write(tmp_path / "reports/trl7/operational-evidence-safety-scan-report.json", "{\n  \"result\": \"PASS\"\n}\n")
    index = build_index(tmp_path)
    md_artifact = next(a for a in index["artifacts"] if a["artifact_id"] == "operational_evidence_safety_scan_report_md")
    json_artifact = next(a for a in index["artifacts"] if a["artifact_id"] == "operational_evidence_safety_scan_report_json")
    assert md_artifact["category"] == "safety_scan"
    assert json_artifact["category"] == "safety_scan"
    assert md_artifact["required_for_trl7_review"] is True
    assert md_artifact["contains_secrets_expected"] is False
    assert md_artifact["reviewed_by_operator"] is False
    assert md_artifact["status_hint"] == "PASS"
    assert index["summary"]["review_required_count"] >= 0
