from pathlib import Path

from tools.evidence_pack.scan_operational_evidence_safety import build_markdown, run_scan


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_pass_for_safe_boundary_text(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/safe.md", "There are no secrets and no private keys in this report.\n")
    report = run_scan(tmp_path)
    assert report["result"] == "PASS"


def test_low_for_policy_reference_without_value(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/policy.md", "Policy section: token handling requirements are documented.\n")
    report = run_scan(tmp_path)
    assert report["finding_counts"]["LOW"] >= 1
    assert report["result"] == "REVIEW_REQUIRED"


def test_medium_for_credential_like_key_with_non_empty_value(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/cred.md", "password: supersecret\n")
    report = run_scan(tmp_path)
    assert report["finding_counts"]["MEDIUM"] == 1
    assert report["result"] == "FAIL"


def test_high_for_pem_private_key_marker(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/key.pem", "-----BEGIN PRIVATE KEY-----\n")
    report = run_scan(tmp_path)
    assert report["finding_counts"]["HIGH"] >= 1


def test_high_for_bearer_token_like_value(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl7/token.md", "Authorization: Bearer abcdefghijklmnopqrstuvwxyzz1234567890\n")
    report = run_scan(tmp_path)
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
