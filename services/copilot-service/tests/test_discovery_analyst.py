from app.discovery_analyst import build_discovery_summary


def _host_scan(scan_id="s1", openssl_version="3.0.13", packages=None, windows_signals=None):
    crypto_evidence = {"openssl_available": True, "openssl_version": openssl_version}
    if packages is not None:
        crypto_evidence["package_metadata"] = {"packages": packages}
    if windows_signals is not None:
        crypto_evidence["windows_normalized_signals"] = windows_signals
    return {"id": scan_id, "source": "host", "crypto_evidence": crypto_evidence, "tls_evidence": None}


def _network_scan(scan_id="s2", algorithm="RSA", size=2048):
    return {
        "id": scan_id, "source": "network", "crypto_evidence": None,
        "tls_evidence": {"certificate": {"public_key_algorithm": algorithm, "public_key_size": size}},
    }


def _repo_scan(scan_id="s3", algorithms=None, ci_findings=None):
    return {
        "id": scan_id, "source": "repo",
        "crypto_evidence": {"repo_scan": {"detected_algorithms": algorithms or [], "ci_pipeline_findings": ci_findings or []}},
        "tls_evidence": None,
    }


def test_explicit_findings_from_host_scan():
    result = build_discovery_summary([_host_scan(packages=[{"name": "openssl"}])], [], None, [])
    sources = {f["source"] for f in result["explicit_findings"]}
    assert "host" in sources
    assert any("OpenSSL available" in f["finding"] for f in result["explicit_findings"])
    assert any("openssl" in f["finding"] for f in result["explicit_findings"])


def test_explicit_findings_from_network_scan():
    result = build_discovery_summary([_network_scan()], [], None, [])
    assert any("RSA (2048-bit)" in f["finding"] for f in result["explicit_findings"])


def test_explicit_findings_from_repo_scan():
    result = build_discovery_summary(
        [_repo_scan(algorithms=["RSA", "SHA1"], ci_findings=[{"command_type": "gpg_sign"}])], [], None, [],
    )
    findings_text = " ".join(f["finding"] for f in result["explicit_findings"])
    assert "RSA" in findings_text and "SHA1" in findings_text
    assert "gpg_sign" in findings_text


def test_explicit_findings_from_documents():
    documents = [{"doc_id": "vendor.md", "chunks": [{"chunk_index": 0, "text": "Our roadmap covers ML-KEM and RSA phase-out."}]}]
    result = build_discovery_summary([], documents, None, [])
    doc_findings = [f for f in result["explicit_findings"] if f["source"] == "doc"]
    assert len(doc_findings) == 1
    assert "ML-KEM" in doc_findings[0]["finding"]
    assert "RSA" in doc_findings[0]["finding"]


def test_document_keyword_matching_respects_word_boundaries():
    # "DES" and "DH" are common substrings of ordinary words (includes, width)
    # -- must not false-positive as crypto findings.
    documents = [{"doc_id": "notes.md", "chunks": [{"chunk_index": 0, "text": "This roadmap includes a width adjustment, nothing crypto-related."}]}]
    result = build_discovery_summary([], documents, None, [])
    assert result["explicit_findings"] == []


def test_inferred_context_from_domain_controller():
    result = build_discovery_summary([_host_scan(windows_signals={"domain_controller_role_observed": True})], [], None, [])
    assert any("PKI trust anchor" in note["note"] for note in result["inferred_context"])


def test_inferred_context_from_repo_signing_without_pipeline_evidence():
    result = build_discovery_summary([_repo_scan(ci_findings=[{"command_type": "gpg_sign"}])], [], None, [])
    assert any("pipeline trust as unverified" in note["note"] for note in result["inferred_context"])


def test_inferred_context_from_graph_blast_radius():
    graph_snapshot = {
        "nodes": [{"id": "cert:root", "type": "Certificate", "label": "root-ca"}],
        "edges": [
            {"from": "asset:a", "to": "cert:root", "type": "SIGNED_BY"},
            {"from": "asset:b", "to": "cert:root", "type": "SIGNED_BY"},
        ],
    }
    result = build_discovery_summary([], [], graph_snapshot, [])
    assert any("root-ca" in note["note"] and "2 dependent" in note["note"] for note in result["inferred_context"])


def test_evidence_gaps_for_missing_source_types():
    result = build_discovery_summary([_host_scan()], [], None, [])
    gap_sources = {g.get("source") for g in result["evidence_gaps"]}
    assert "network" in gap_sources
    assert "repo" in gap_sources
    assert "doc" in gap_sources
    assert "host" not in gap_sources


def test_evidence_gaps_for_risk_without_supporting_evidence():
    scans = [{"id": "s1", "source": "manual", "crypto_evidence": None, "tls_evidence": None}]
    risks = [{"scan_id": "s1", "asset_name": "bare-asset"}]
    result = build_discovery_summary(scans, [], None, risks)
    assert any(g.get("asset_name") == "bare-asset" for g in result["evidence_gaps"])


def test_narrative_mentions_counts():
    result = build_discovery_summary([_host_scan(packages=[{"name": "openssl"}])], [], None, [])
    assert "Discovered" in result["narrative"]
    assert "evidence gap" in result["narrative"]


def test_empty_inputs_produce_no_crash_and_full_gaps():
    result = build_discovery_summary([], [], None, [])
    assert result["explicit_findings"] == []
    assert result["inferred_context"] == []
    assert len(result["evidence_gaps"]) == 4  # host, network, repo, doc
