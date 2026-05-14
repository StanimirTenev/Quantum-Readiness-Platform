from pathlib import Path

from tools.evidence_pack.build_evidence_pack_index import build_index, build_markdown


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_index_builder_handles_existing_and_missing_artifacts_and_hash_and_structure(tmp_path: Path) -> None:
    _write(tmp_path / "reports/trl-validation-report.md", "PASS\n")
    _write(tmp_path / "reports/stage2-e2e-smoke-report.md", "FAIL\n")
    _write(tmp_path / "docs/operator-validation-checklist.md", "notes\n")

    index = build_index(tmp_path)

    assert index["summary"]["total_artifacts"] == 11
    assert index["summary"]["present"] == 3
    assert index["summary"]["missing"] == 8
    assert {"generated_at_utc", "summary", "artifacts"}.issubset(index.keys())

    trl = next(a for a in index["artifacts"] if a["artifact_id"] == "trl_validation")
    e2e = next(a for a in index["artifacts"] if a["artifact_id"] == "stage2_e2e_smoke")
    missing = next(a for a in index["artifacts"] if a["artifact_id"] == "graph_projection")

    assert trl["exists"] is True
    assert len(trl["sha256"]) == 64
    assert trl["status_hint"] == "PASS"
    assert "size_bytes" in trl

    assert e2e["status_hint"] == "FAIL"

    assert missing["exists"] is False
    assert "sha256" not in missing


def test_status_hint_unknown_and_markdown_boundaries_and_no_input_modification(tmp_path: Path) -> None:
    artifact = tmp_path / "docs/repository-checkpoint-current-status.md"
    _write(artifact, "NEUTRAL\n")
    before = artifact.read_bytes()

    index = build_index(tmp_path)
    md = build_markdown(index)

    status_doc = next(a for a in index["artifacts"] if a["artifact_id"] == "repository_checkpoint_status")
    assert status_doc["status_hint"] == "UNKNOWN"

    assert "This evidence pack index only summarizes existing local artifacts." in md
    assert "It does not run tests, call services, regenerate reports, or modify source evidence." in md
    assert "It does not imply production readiness." in md

    after = artifact.read_bytes()
    assert before == after
