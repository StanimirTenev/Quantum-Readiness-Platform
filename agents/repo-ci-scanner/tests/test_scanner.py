from pathlib import Path

from scanner import build_ingest_payload, main


def test_build_ingest_payload_shape():
    scan_result = {
        "files_scanned": {"source": 1, "ci_config": 1},
        "source_code_findings": [
            {"path": "app/crypto.py", "line": 1, "algorithm": "RSA", "description": "RSA usage", "excerpt": "..."},
        ],
        "ci_pipeline_findings": [
            {"path": ".github/workflows/release.yml", "line": 2, "command_type": "gpg_sign", "excerpt": "..."},
        ],
        "detected_algorithms": ["RSA"],
    }

    payload = build_ingest_payload(scan_result, "my-repo")

    assert payload["source"] == "repo"
    assert payload["assets"] == [{"asset_type": "other", "name": "my-repo"}]
    assert payload["crypto_evidence"]["known_crypto_files"] == [
        ".github/workflows/release.yml",
        "app/crypto.py",
    ]
    assert payload["crypto_evidence"]["repo_scan"] == scan_result
    assert payload["crypto_evidence"]["package_metadata"]["packages"] == [{"name": "RSA"}]


def test_main_writes_output_file(tmp_path: Path):
    (tmp_path / "crypto.py").write_text("from Crypto.PublicKey import RSA\n", encoding="utf-8")
    out_file = tmp_path / "out.json"

    exit_code = main(["--repo-path", str(tmp_path), "--out", str(out_file)])

    assert exit_code == 0
    assert out_file.exists()
    assert "RSA" in out_file.read_text(encoding="utf-8")


def test_main_errors_on_missing_repo_path(tmp_path: Path, capsys):
    missing = tmp_path / "does-not-exist"

    exit_code = main(["--repo-path", str(missing)])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err
