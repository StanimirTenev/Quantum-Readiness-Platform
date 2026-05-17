import hashlib
from pathlib import Path

from tools.evidence_pack.build_trl6_demo_bundle import build_index, build_markdown


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_index_handles_present_missing_and_stable_json_shape(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl6/trl6-readiness-report.md", "Overall Result: PASS\n")
    _write(tmp_path / "reports/trl6/operator-review-summary.md", "Overall Result: FAIL\n")

    index = build_index(tmp_path)

    assert set(index.keys()) == {"generated_at_utc", "purpose", "summary", "artifacts"}
    assert index["summary"]["total_artifacts"] == 16
    assert index["summary"]["present"] == 2
    assert index["summary"]["missing"] == 14


def test_sha256_and_known_limitations_contextual_fail_word_is_unknown(tmp_path: Path) -> None:
    sample_path = tmp_path / "reports/trl6/known-limitations.md"
    content = "Any required command failure results in FAIL in related reports.\n"
    _write(sample_path, content)

    index = build_index(tmp_path)
    artifact = next(a for a in index["artifacts"] if a["artifact_id"] == "trl6_known_limitations")

    assert artifact["exists"] is True
    assert artifact["sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert artifact["status_hint"] == "UNKNOWN"


def test_status_hint_explicit_fail_result_is_fail(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl6/operator-demo-checklist.md", "Overall Result: FAIL\n")
    index = build_index(tmp_path)
    checklist = next(a for a in index["artifacts"] if a["artifact_id"] == "trl6_operator_checklist")
    assert checklist["status_hint"] == "FAIL"


def test_status_hint_explicit_pass_result_is_pass(tmp_path: Path) -> None:
    _write(tmp_path / "docs/trl6-readiness-plan.md", "Overall Result: PASS\n")
    index = build_index(tmp_path)
    plan = next(a for a in index["artifacts"] if a["artifact_id"] == "trl6_readiness_plan")
    assert plan["status_hint"] == "PASS"


def test_status_hint_plain_checkpoint_doc_is_unknown(tmp_path: Path) -> None:
    _write(tmp_path / "docs/repository-checkpoint-current-status.md", "checkpoint notes with no explicit result\n")
    index = build_index(tmp_path)
    checkpoint = next(a for a in index["artifacts"] if a["artifact_id"] == "repository_checkpoint_status")
    assert checkpoint["status_hint"] == "UNKNOWN"


def test_markdown_contains_required_boundary_statements(tmp_path: Path) -> None:
    md = build_markdown(build_index(tmp_path))
    assert "This bundle supports TRL6 demo/operator review only." in md
    assert "TRL 6 achieved is not claimed by this bundle." in md
    assert "Production readiness is not claimed by this bundle." in md
    assert "This bundle does not run tests, start services, or regenerate evidence." in md


def test_input_files_not_modified(tmp_path: Path) -> None:
    source = tmp_path / "reports/evidence-pack/evidence-pack-index.md"
    _write(source, "Overall Result: PASS\n")
    before = source.read_bytes()
    build_index(tmp_path)
    after = source.read_bytes()
    assert before == after
