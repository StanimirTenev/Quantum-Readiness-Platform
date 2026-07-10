from pathlib import Path

from scanner import build_ingest_payload, main, post_ingest


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


def test_build_ingest_payload_includes_iac_and_embedded_key_findings():
    scan_result = {
        "files_scanned": {"source": 0, "ci_config": 0, "iac": 1},
        "source_code_findings": [],
        "ci_pipeline_findings": [],
        "iac_findings": [
            {"path": "main.tf", "line": 2, "algorithm": "ECDSA", "description": "...", "excerpt": "..."},
        ],
        "embedded_key_findings": [
            {"path": "k8s/tls-secret.yaml", "line": 6, "description": "...", "excerpt": "..."},
        ],
        "detected_algorithms": ["ECDSA"],
    }

    payload = build_ingest_payload(scan_result, "my-repo")

    assert payload["crypto_evidence"]["known_crypto_files"] == ["k8s/tls-secret.yaml", "main.tf"]
    assert payload["crypto_evidence"]["package_metadata"]["packages"] == [{"name": "ECDSA"}]


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


def test_post_ingest_passes_workspace_id_as_query_param(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"created": 1, "workspace_id": "ws-789"}

    def fake_post(url, json=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)

    result = post_ingest("http://127.0.0.1:8001", {"source": "repo"}, workspace_id="ws-789")

    assert captured["params"] == {"workspace_id": "ws-789"}
    assert result["workspace_id"] == "ws-789"


def test_post_ingest_omits_params_without_workspace_id(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"created": 1}

    def fake_post(url, json=None, params=None, timeout=None):
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)

    post_ingest("http://127.0.0.1:8001", {"source": "repo"})

    assert captured["params"] is None
