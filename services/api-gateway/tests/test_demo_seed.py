from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))
import demo_seed


def test_load_demo_scan_payloads_reads_real_fixtures_and_repo_payload():
    payloads = demo_seed.load_demo_scan_payloads()
    sources = [p[0] for p in payloads]
    asset_names = [p[1] for p in payloads]
    assert sources == ["host", "network", "repo"]
    assert asset_names == demo_seed.DEMO_ASSET_NAMES

    host_payload = payloads[0][2]
    assert host_payload["crypto_evidence"]["openssl_available"] is True

    repo_payload = payloads[2][2]
    assert repo_payload["crypto_evidence"]["repo_scan"]["detected_algorithms"] == ["RSA", "SHA1"]


def test_write_demo_doc_index_writes_expected_shape(tmp_path):
    target = tmp_path / "doc-index.json"
    result_path = demo_seed.write_demo_doc_index(target)
    assert result_path == target
    import json
    data = json.loads(target.read_text())
    assert data["document_count"] == 1
    assert data["documents"][0]["doc_id"] == demo_seed.DEMO_DOC_ID
    assert "ML-KEM" in data["documents"][0]["chunks"][0]["text"]


def _repo_relative_target():
    # build_demo_graph_snapshot passes relative paths to the subprocess (cwd=REPO_ROOT)
    # so the snapshot doesn't bake in a machine-specific absolute path -- the target
    # must therefore live under REPO_ROOT, unlike pytest's tmp_path.
    target = demo_seed.REPO_ROOT / "reports" / "graph" / "_test_tmp" / "graph-snapshot.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def test_build_demo_graph_snapshot_success():
    target = _repo_relative_target()
    try:
        fake_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("demo_seed.subprocess.run", return_value=fake_result) as run:
            ok, message = demo_seed.build_demo_graph_snapshot(target)
        assert ok is True
        assert "built" in message
        args = run.call_args.args[0]
        assert "--host" in args and "--network" in args
    finally:
        target.unlink(missing_ok=True)
        target.parent.rmdir()


def test_build_demo_graph_snapshot_reports_failure():
    target = _repo_relative_target()
    try:
        fake_result = MagicMock(returncode=1, stdout="", stderr="boom")
        with patch("demo_seed.subprocess.run", return_value=fake_result):
            ok, message = demo_seed.build_demo_graph_snapshot(target)
        assert ok is False
        assert "boom" in message
    finally:
        target.parent.rmdir()
