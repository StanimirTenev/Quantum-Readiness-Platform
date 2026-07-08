from app.vendor_intelligence_analyst import build_vendor_intelligence_summary


def _doc(doc_id, texts):
    return {"doc_id": doc_id, "chunks": [{"chunk_index": i, "text": t} for i, t in enumerate(texts)]}


def test_certain_claim_is_classified_pqc_ready_and_certain():
    result = build_vendor_intelligence_summary([_doc("vendor-a.md", ["Our appliance now supports ML-KEM-768 encryption."])])
    claim = result["claims"][0]
    assert claim["claimed_readiness"] == "pqc_ready"
    assert claim["confidence"] == "certain"
    assert claim["is_migration_blocker"] is False


def test_roadmap_claim_is_classified_uncertain():
    result = build_vendor_intelligence_summary([_doc("vendor-b.md", ["We plan to add post-quantum support by Q3 2026."])])
    claim = result["claims"][0]
    assert claim["confidence"] == "uncertain"


def test_hybrid_claim_is_classified_hybrid_capable():
    result = build_vendor_intelligence_summary([_doc("vendor-c.md", ["The gateway now supports hybrid post-quantum key exchange."])])
    claim = result["claims"][0]
    assert claim["claimed_readiness"] == "hybrid_capable"


def test_blocker_claim_is_classified_vendor_blocked():
    result = build_vendor_intelligence_summary([_doc("vendor-d.md", ["This product does not support post-quantum cryptography and there are no plans to add it."])])
    claim = result["claims"][0]
    assert claim["claimed_readiness"] == "vendor_blocked"
    assert claim["is_migration_blocker"] is True


def test_chunk_without_pqc_terms_produces_no_claim():
    result = build_vendor_intelligence_summary([_doc("vendor-e.md", ["This document discusses general firewall configuration."])])
    assert result["claims"] == []


def test_product_hint_derived_from_doc_id():
    result = build_vendor_intelligence_summary([_doc("vendor-acme_firewall-roadmap.md", ["We now support post-quantum cryptography."])])
    assert result["claims"][0]["product_hint"] == "Vendor Acme Firewall Roadmap"


def test_readiness_matrix_prefers_certain_claims_and_flags_blockers():
    documents = [_doc("vendor-f.md", [
        "We plan to add post-quantum support eventually.",
        "This feature does not support post-quantum cryptography today.",
    ])]
    result = build_vendor_intelligence_summary(documents)
    matrix_entry = result["readiness_matrix"][0]
    assert matrix_entry["has_migration_blocker"] is True
    assert matrix_entry["claimed_readiness"] == "vendor_blocked"
    assert matrix_entry["claim_count"] == 2


def test_readiness_matrix_confidence_reflects_the_blocker_claim_not_an_unrelated_certain_one():
    # A doc can have a *certain* positive claim about one module and a
    # *separate* blocker about another -- the matrix's confidence must
    # describe the blocker verdict, not borrow certainty from the unrelated
    # positive statement.
    documents = [_doc("vendor-j.md", [
        "Our appliance now supports hybrid post-quantum key exchange in the current firmware release.",
        "Our legacy VPN module does not support post-quantum cryptography and there are no plans to add it.",
    ])]
    result = build_vendor_intelligence_summary(documents)
    matrix_entry = result["readiness_matrix"][0]
    assert matrix_entry["claimed_readiness"] == "vendor_blocked"
    assert matrix_entry["confidence"] != "certain"


def test_readiness_matrix_groups_by_document():
    documents = [
        _doc("vendor-g.md", ["Our appliance now supports ML-KEM for key exchange in the latest release."]),
        _doc("vendor-h.md", ["We plan to add ML-DSA signature support in a future release."]),
    ]
    result = build_vendor_intelligence_summary(documents)
    doc_ids = {entry["doc_id"] for entry in result["readiness_matrix"]}
    assert doc_ids == {"vendor-g.md", "vendor-h.md"}


def test_narrative_mentions_counts():
    result = build_vendor_intelligence_summary([_doc("vendor-i.md", ["We now support post-quantum cryptography."])])
    assert "Extracted 1 PQC readiness claim" in result["narrative"]


def test_empty_documents_produce_empty_summary():
    result = build_vendor_intelligence_summary([])
    assert result["claims"] == []
    assert result["readiness_matrix"] == []
    assert "No PQC-relevant claims" in result["narrative"]
