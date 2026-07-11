"""Discovery Analyst: the second deterministic Copilot subagent. Synthesizes
"what crypto dependencies have we found, and where is evidence missing"
across host/network/repo scans, indexed documents, the dependency graph, and
persisted risk records. No LLM call, no writes -- read-only synthesis over
already-collected evidence, same safety boundary as Risk Narrator (see
app/risk_narrator.py)."""

from __future__ import annotations

import re
from typing import Any

DOC_CRYPTO_KEYWORDS = [
    "RSA", "ECDSA", "ECDH", "DSA", "DH", "MD5", "SHA-1", "SHA1", "RC4", "DES",
    "ML-KEM", "ML-DSA", "SLH-DSA", "PQC", "post-quantum", "Kyber", "Dilithium",
]

# Word-boundary matching -- short acronyms like "DES"/"DH" are common
# substrings of ordinary English words ("includes", "width") and would false
# -positive under a naive substring search.
_DOC_KEYWORD_PATTERNS = [(kw, re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)) for kw in DOC_CRYPTO_KEYWORDS]


def _package_names(crypto_evidence: dict[str, Any]) -> list[str]:
    packages = (crypto_evidence.get("package_metadata") or {}).get("packages") or []
    names = {p.get("name") for p in packages if isinstance(p, dict) and p.get("name")}
    return sorted(names)


def _explicit_findings_from_scans(scans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for scan in scans:
        source = scan.get("source")
        scan_id = scan.get("id")
        crypto_evidence = scan.get("crypto_evidence") or {}

        if source == "host":
            if crypto_evidence.get("openssl_available"):
                version = crypto_evidence.get("openssl_version")
                detail = f"OpenSSL available ({version})" if version else "OpenSSL available"
                findings.append({"source": "host", "scan_id": scan_id, "finding": detail})
            names = _package_names(crypto_evidence)
            if names:
                findings.append({"source": "host", "scan_id": scan_id, "finding": f"Crypto-relevant packages observed: {', '.join(names[:5])}"})

        elif source == "network":
            certificate = (scan.get("tls_evidence") or {}).get("certificate") or {}
            algorithm = certificate.get("public_key_algorithm")
            if algorithm:
                size = certificate.get("public_key_size")
                detail = f"TLS certificate uses {algorithm} ({size}-bit)" if size else f"TLS certificate uses {algorithm}"
                findings.append({"source": "network", "scan_id": scan_id, "finding": detail})

            ssh_evidence = scan.get("ssh_evidence") or {}
            if ssh_evidence.get("collected"):
                host_key_algorithms = ssh_evidence.get("server_host_key_algorithms") or []
                if host_key_algorithms:
                    findings.append({
                        "source": "network", "scan_id": scan_id,
                        "finding": f"SSH host key algorithms offered: {', '.join(host_key_algorithms)}",
                    })
                kex_algorithms = ssh_evidence.get("kex_algorithms") or []
                if kex_algorithms:
                    findings.append({
                        "source": "network", "scan_id": scan_id,
                        "finding": f"SSH key exchange algorithms offered: {', '.join(kex_algorithms)}",
                    })

        elif source == "repo":
            repo_scan = crypto_evidence.get("repo_scan") or {}
            algorithms = repo_scan.get("detected_algorithms") or []
            if algorithms:
                findings.append({"source": "repo", "scan_id": scan_id, "finding": f"Source code references: {', '.join(algorithms)}"})

            iac_findings = repo_scan.get("iac_findings") or []
            if iac_findings:
                iac_algorithms = sorted({f.get("algorithm") for f in iac_findings if f.get("algorithm")})
                findings.append({"source": "repo", "scan_id": scan_id, "finding": f"IaC-declared key algorithms: {', '.join(iac_algorithms)}"})

            embedded_key_findings = repo_scan.get("embedded_key_findings") or []
            if embedded_key_findings:
                paths = sorted({f.get("path") for f in embedded_key_findings if f.get("path")})
                findings.append({
                    "source": "repo", "scan_id": scan_id,
                    "finding": f"Embedded private key material found in: {', '.join(paths)}",
                })

            ci_findings = repo_scan.get("ci_pipeline_findings") or []
            if ci_findings:
                commands = sorted({f.get("command_type") for f in ci_findings if f.get("command_type")})
                findings.append({"source": "repo", "scan_id": scan_id, "finding": f"CI signing commands detected: {', '.join(commands)}"})

    return findings


def _explicit_findings_from_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for doc in documents:
        doc_id = doc.get("doc_id")
        for chunk in doc.get("chunks") or []:
            text = chunk.get("text") or ""
            matched = sorted({kw for kw, pattern in _DOC_KEYWORD_PATTERNS if pattern.search(text)})
            if matched:
                findings.append({
                    "source": "doc",
                    "doc_id": doc_id,
                    "chunk_index": chunk.get("chunk_index"),
                    "finding": f"Document mentions: {', '.join(matched)}",
                })
    return findings


def _inferred_context(scans: list[dict[str, Any]], graph_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    inferred: list[dict[str, Any]] = []

    for scan in scans:
        windows_signals = (scan.get("crypto_evidence") or {}).get("windows_normalized_signals")
        if isinstance(windows_signals, dict) and windows_signals.get("domain_controller_role_observed"):
            inferred.append({
                "note": "A domain-controller host was observed -- it is a PKI trust anchor for the domain; "
                        "certificates issued through it inherit its trust chain, even though no direct CA scan exists.",
            })

    repo_signing_scans = [
        s for s in scans
        if s.get("source") == "repo" and ((s.get("crypto_evidence") or {}).get("repo_scan") or {}).get("ci_pipeline_findings")
    ]
    if repo_signing_scans:
        inferred.append({
            "note": f"CI signing activity was found in {len(repo_signing_scans)} repo scan(s), but no independent "
                    "pipeline/CA evidence has been collected -- treat pipeline trust as unverified.",
        })

    if graph_snapshot:
        nodes = {n.get("id"): n for n in graph_snapshot.get("nodes", [])}
        dependents: dict[str, int] = {}
        for edge in graph_snapshot.get("edges", []):
            target = edge.get("to")
            if target:
                dependents[target] = dependents.get(target, 0) + 1
        for node_id, count in sorted(dependents.items(), key=lambda item: -item[1]):
            if count < 2:
                continue
            label = nodes.get(node_id, {}).get("label", node_id)
            inferred.append({
                "note": f"'{label}' has {count} dependent object(s) in the dependency graph -- compromising it "
                        "would have a wider blast radius than its own risk score alone suggests.",
            })

    return inferred


def _evidence_gaps(scans: list[dict[str, Any]], documents: list[dict[str, Any]], risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    sources_present = {s.get("source") for s in scans}
    for expected_source in ("host", "network", "repo"):
        if expected_source not in sources_present:
            gaps.append({"source": expected_source, "detail": f"No {expected_source} evidence has been collected yet."})

    if not documents:
        gaps.append({"source": "doc", "detail": "No vendor/runbook documents have been indexed yet."})

    scans_by_id = {s.get("id"): s for s in scans}
    for risk in risks:
        scan = scans_by_id.get(risk.get("scan_id"))
        if scan is not None and not scan.get("crypto_evidence") and not scan.get("tls_evidence"):
            gaps.append({
                "asset_name": risk.get("asset_name"),
                "detail": "A risk score was computed, but no supporting crypto evidence was ingested for this scan.",
            })

    return gaps


def build_discovery_summary(
    scans: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    graph_snapshot: dict[str, Any] | None,
    risks: list[dict[str, Any]],
) -> dict[str, Any]:
    explicit_findings = _explicit_findings_from_scans(scans) + _explicit_findings_from_documents(documents)
    inferred_context = _inferred_context(scans, graph_snapshot)
    evidence_gaps = _evidence_gaps(scans, documents, risks)

    source_types = sorted({s.get("source") for s in scans if s.get("source")})
    narrative_parts = [
        f"Discovered {len(explicit_findings)} explicit crypto finding(s) across "
        f"{len(source_types)} evidence source type(s) ({', '.join(source_types) or 'none'}) plus indexed documents.",
    ]
    if inferred_context:
        narrative_parts.append(
            f"{len(inferred_context)} inferred dependency/context note(s) were derived from aggregate signals "
            "(domain role, dependency graph) that explicit scanners don't state directly."
        )
    if evidence_gaps:
        narrative_parts.append(f"{len(evidence_gaps)} evidence gap(s) were identified -- see evidence_gaps for what's still missing.")
    else:
        narrative_parts.append("No evidence gaps identified across the checked source types.")

    return {
        "narrative": " ".join(narrative_parts),
        "explicit_findings": explicit_findings,
        "inferred_context": inferred_context,
        "evidence_gaps": evidence_gaps,
    }
