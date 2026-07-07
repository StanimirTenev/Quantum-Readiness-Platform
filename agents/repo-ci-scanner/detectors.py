"""Detection patterns for classical crypto usage and CI signing commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SOURCE_EXTENSIONS = {".py", ".go", ".js", ".ts", ".java", ".rb", ".php", ".c", ".cpp", ".cs", ".sh"}

EXCLUDED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "vendor", "dist", "build", ".tox", "target",
}

CI_CONFIG_FILENAMES = {".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml"}

# (algorithm, description, compiled regex matched against a single source line)
ALGORITHM_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("RSA", "RSA usage", re.compile(
        r"Crypto\.PublicKey\.RSA|Crypto\.PublicKey\s+import\s+RSA|"
        r"hazmat\.primitives\.asymmetric\.rsa|crypto/rsa|"
        r"KeyPairGenerator\.getInstance\(\s*[\"']RSA[\"']|openssl\s+genrsa|-newkey\s+rsa",
        re.IGNORECASE,
    )),
    ("DSA", "DSA usage", re.compile(
        r"Crypto\.PublicKey\s+import\s+DSA|"
        r"hazmat\.primitives\.asymmetric\.dsa|crypto/dsa|"
        r"KeyPairGenerator\.getInstance\(\s*[\"']DSA[\"']|openssl\s+dsaparam",
        re.IGNORECASE,
    )),
    ("ECDSA", "ECDSA usage", re.compile(r"crypto/ecdsa|\bECDSA\b", re.IGNORECASE)),
    ("EC", "Elliptic curve usage", re.compile(
        r"hazmat\.primitives\.asymmetric\.ec\b|crypto/elliptic|"
        r"KeyPairGenerator\.getInstance\(\s*[\"']EC[\"']|openssl\s+ecparam",
        re.IGNORECASE,
    )),
    ("DH", "Diffie-Hellman usage", re.compile(
        r"hazmat\.primitives\.asymmetric\.dh\b|crypto/dh\b|Diffie[- ]?Hellman", re.IGNORECASE,
    )),
    ("MD5", "MD5 usage", re.compile(
        r"hashlib\.md5|crypto/md5|MessageDigest\.getInstance\(\s*[\"']MD5[\"']|"
        r"createHash\(\s*[\"']md5[\"']|openssl\s+dgst\s+-md5",
        re.IGNORECASE,
    )),
    ("SHA1", "SHA-1 usage", re.compile(
        r"hashlib\.sha1|crypto/sha1|MessageDigest\.getInstance\(\s*[\"']SHA-?1[\"']|"
        r"createHash\(\s*[\"']sha1[\"']|openssl\s+dgst\s+-sha1",
        re.IGNORECASE,
    )),
    ("RC4", "RC4 usage", re.compile(r"crypto/rc4|\bRC4\b", re.IGNORECASE)),
    ("DES", "DES/3DES usage", re.compile(r"crypto/des\b|DESede|3DES|TripleDES", re.IGNORECASE)),
]

# (command_type, compiled regex) for signing commands found in CI/build configs.
SIGNING_COMMAND_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("gpg_sign", re.compile(r"\bgpg\s+(--detach-sign|--sign|-s)\b")),
    ("openssl_sign", re.compile(r"\bopenssl\s+(dgst|smime|cms)\b.*-sign\b")),
    ("cosign_sign", re.compile(r"\bcosign\s+sign\b")),
    ("signtool_sign", re.compile(r"\bsigntool\s+sign\b", re.IGNORECASE)),
    ("jarsigner", re.compile(r"\bjarsigner\b")),
    ("codesign", re.compile(r"\bcodesign\b")),
]


def iter_repo_files(repo_path: Path):
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(repo_path).parts):
            continue
        yield path


def is_ci_config_file(path: Path, repo_path: Path) -> bool:
    rel = path.relative_to(repo_path).as_posix()
    if rel.startswith(".github/workflows/") and path.suffix in {".yml", ".yaml"}:
        return True
    if rel.startswith(".circleci/") and path.suffix in {".yml", ".yaml"}:
        return True
    return path.name in CI_CONFIG_FILENAMES


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []


def scan_source_file(path: Path, rel_path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(_read_lines(path), start=1):
        for algorithm, description, pattern in ALGORITHM_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "path": rel_path,
                    "line": line_no,
                    "algorithm": algorithm,
                    "description": description,
                    "excerpt": line.strip()[:200],
                })
    return findings


def scan_ci_file(path: Path, rel_path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(_read_lines(path), start=1):
        for command_type, pattern in SIGNING_COMMAND_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "path": rel_path,
                    "line": line_no,
                    "command_type": command_type,
                    "excerpt": line.strip()[:200],
                })
    return findings


def scan_repo(repo_path: Path) -> dict[str, Any]:
    source_findings: list[dict[str, Any]] = []
    ci_findings: list[dict[str, Any]] = []
    files_scanned = {"source": 0, "ci_config": 0}

    for path in iter_repo_files(repo_path):
        rel_path = path.relative_to(repo_path).as_posix()
        if is_ci_config_file(path, repo_path):
            files_scanned["ci_config"] += 1
            ci_findings.extend(scan_ci_file(path, rel_path))
        elif path.suffix in SOURCE_EXTENSIONS:
            files_scanned["source"] += 1
            source_findings.extend(scan_source_file(path, rel_path))

    return {
        "files_scanned": files_scanned,
        "source_code_findings": source_findings,
        "ci_pipeline_findings": ci_findings,
        "detected_algorithms": sorted({f["algorithm"] for f in source_findings}),
    }
