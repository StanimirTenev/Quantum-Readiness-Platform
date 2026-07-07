from pathlib import Path

from detectors import is_ci_config_file, scan_repo


def test_scan_repo_detects_source_algorithms_and_signing_commands(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "crypto.py").write_text(
        "from Crypto.PublicKey import RSA\n"
        "import hashlib\n"
        "digest = hashlib.md5(b'x').hexdigest()\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "hash.go").write_text(
        'import "crypto/sha1"\n',
        encoding="utf-8",
    )

    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "release.yml").write_text(
        "steps:\n"
        "  - run: gpg --detach-sign artifact.tar.gz\n"
        "  - run: cosign sign my-image:latest\n",
        encoding="utf-8",
    )

    result = scan_repo(tmp_path)

    assert result["files_scanned"] == {"source": 2, "ci_config": 1}
    algorithms = {f["algorithm"] for f in result["source_code_findings"]}
    assert algorithms == {"RSA", "MD5", "SHA1"}

    command_types = {f["command_type"] for f in result["ci_pipeline_findings"]}
    assert command_types == {"gpg_sign", "cosign_sign"}


def test_scan_repo_excludes_vendor_and_git_dirs(tmp_path: Path):
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.py").write_text("from Crypto.PublicKey import RSA\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.py").write_text("hashlib.md5\n", encoding="utf-8")

    result = scan_repo(tmp_path)

    assert result["files_scanned"] == {"source": 0, "ci_config": 0}
    assert result["source_code_findings"] == []


def test_scan_repo_no_findings_in_clean_repo(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('hello world')\n", encoding="utf-8")

    result = scan_repo(tmp_path)

    assert result["files_scanned"] == {"source": 1, "ci_config": 0}
    assert result["source_code_findings"] == []
    assert result["ci_pipeline_findings"] == []
    assert result["detected_algorithms"] == []


def test_is_ci_config_file_recognizes_known_paths(tmp_path: Path):
    gh = tmp_path / ".github" / "workflows" / "ci.yml"
    gh.parent.mkdir(parents=True)
    gh.write_text("", encoding="utf-8")
    gitlab = tmp_path / ".gitlab-ci.yml"
    gitlab.write_text("", encoding="utf-8")
    regular = tmp_path / "main.py"
    regular.write_text("", encoding="utf-8")

    assert is_ci_config_file(gh, tmp_path) is True
    assert is_ci_config_file(gitlab, tmp_path) is True
    assert is_ci_config_file(regular, tmp_path) is False
