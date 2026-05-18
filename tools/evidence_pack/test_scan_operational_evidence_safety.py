from pathlib import Path

from tools.evidence_pack.scan_operational_evidence_safety import build_markdown, run_scan


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _single_line_report(tmp_path: Path, line: str) -> dict:
    _write(tmp_path / "reports/trl7/sample.md", line + "\n")
    return run_scan(tmp_path)


def test_high_medium_low_count_self_reporting_lines_are_ignored(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "HIGH findings: 0")
    assert report["finding_counts"]["LOW"] == 0

    report = _single_line_report(tmp_path, "MEDIUM findings: 0")
    assert report["finding_counts"]["LOW"] == 0


def test_low_findings_reviewer_awareness_line_is_ignored(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "LOW findings require reviewer awareness")
    assert report["finding_counts"]["LOW"] == 0


def test_blocking_credential_private_key_findings_none_is_ignored(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "blocking credential/private-key findings: none")
    assert report["finding_counts"]["LOW"] == 0


def test_credential_indicators_are_scanned_is_ignored(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "credential indicators are scanned")
    assert report["finding_counts"]["LOW"] == 0


def test_private_key_findings_not_detected_is_ignored(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "private-key findings were not detected")
    assert report["finding_counts"]["LOW"] == 0


def test_medium_for_credential_like_key_with_non_empty_value(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "password: supersecret123")
    assert report["finding_counts"]["MEDIUM"] == 1
    assert report["result"] == "FAIL"


def test_redacted_password_value_produces_no_medium(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "password: <redacted>")
    assert report["finding_counts"]["MEDIUM"] == 0


def test_high_for_pem_private_key_marker(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "-----BEGIN PRIVATE KEY-----")
    assert report["finding_counts"]["HIGH"] >= 1


def test_high_for_bearer_token_like_value(tmp_path: Path) -> None:
    report = _single_line_report(tmp_path, "Authorization: Bearer abcdefghijklmnopqrstuvwxyzz1234567890")
    assert report["finding_counts"]["HIGH"] >= 1


def test_json_report_structure_stable(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/a.md", "hello\n")
    report = run_scan(tmp_path)
    assert set(report.keys()) == {"generated_at_utc", "scanned_roots", "files_scanned", "files_skipped", "finding_counts", "result", "findings"}


def test_markdown_contains_boundary_statements(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/a.md", "hello\n")
    md = build_markdown(run_scan(tmp_path))
    assert "This scan checks local evidence/report artifacts only." in md
    assert "This scan does not modify evidence." in md
    assert "TRL 7 achieved is not claimed by this scan." in md
    assert "Production readiness is not claimed by this scan." in md


def test_input_files_are_not_modified(tmp_path: Path) -> None:
    target = tmp_path / "reports/trl7/source.md"
    _write(target, "token policy mention only\n")
    before = target.read_text(encoding="utf-8")
    _ = run_scan(tmp_path)
    after = target.read_text(encoding="utf-8")
    assert before == after
