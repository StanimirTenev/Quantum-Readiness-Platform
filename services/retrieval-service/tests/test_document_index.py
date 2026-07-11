from app.document_index import load_document_index, search_documents


def _doc(doc_id, chunks):
    return {"doc_id": doc_id, "source_path": f"/docs/{doc_id}", "chunks": chunks}


def test_search_documents_matches_case_insensitive_substring():
    documents = [_doc("vendor-a.pdf", [{"chunk_index": 0, "page": 1, "text": "Our PQC Roadmap targets Q3 2026."}])]
    matches = search_documents("pqc roadmap", documents)
    assert len(matches) == 1
    assert matches[0]["doc_id"] == "vendor-a.pdf"
    assert matches[0]["source_path"] == "/docs/vendor-a.pdf"
    assert matches[0]["chunk_index"] == 0
    assert matches[0]["page"] == 1


def test_search_documents_no_match_returns_empty():
    documents = [_doc("vendor-a.pdf", [{"chunk_index": 0, "text": "Unrelated content."}])]
    assert search_documents("kyber", documents) == []


def test_search_documents_empty_query_returns_empty():
    documents = [_doc("vendor-a.pdf", [{"chunk_index": 0, "text": "anything"}])]
    assert search_documents("   ", documents) == []


def test_search_documents_matches_across_multiple_chunks_and_docs():
    documents = [
        _doc("a.md", [{"chunk_index": 0, "text": "rotate certificates every 90 days"}]),
        _doc("b.md", [{"chunk_index": 0, "text": "nothing here"}, {"chunk_index": 1, "text": "certificate rotation runbook"}]),
    ]
    matches = search_documents("certificate", documents)
    assert len(matches) == 2
    assert {m["doc_id"] for m in matches} == {"a.md", "b.md"}


def test_search_documents_matches_synonym_pqc_to_post_quantum():
    documents = [_doc("vendor-a.pdf", [{"chunk_index": 0, "text": "Our roadmap covers post-quantum key exchange."}])]
    matches = search_documents("PQC", documents)
    assert len(matches) == 1
    assert matches[0]["doc_id"] == "vendor-a.pdf"


def test_search_documents_matches_synonym_hndl_to_harvest_now_decrypt_later():
    documents = [_doc("vendor-b.pdf", [{"chunk_index": 0, "text": "Data is exposed to harvest now decrypt later attacks."}])]
    matches = search_documents("HNDL", documents)
    assert len(matches) == 1


def test_search_documents_does_not_cross_contaminate_unrelated_synonym_groups():
    """kyber (ML-KEM family) and dilithium (ML-DSA family) share no synonym
    group; a query for one must not pull in the other's group phrases just
    because both group names happen to start with "ml-" (regression test for
    a real bug: an earlier token-level synonym expansion let "ml" bridge the
    two unrelated groups)."""
    documents = [_doc("dilithium-only.pdf", [{"chunk_index": 0, "text": "We support dilithium for signing."}])]
    matches = search_documents("kyber", documents)
    assert matches == []


def test_search_documents_ranks_more_relevant_chunk_first():
    documents = [
        _doc("a.md", [{"chunk_index": 0, "text": "quantum key exchange is mentioned once here"}]),
        _doc("b.md", [{"chunk_index": 0, "text": "quantum key exchange quantum key exchange quantum key exchange"}]),
    ]
    matches = search_documents("quantum key exchange", documents)
    assert len(matches) == 2
    assert matches[0]["doc_id"] == "b.md"
    assert matches[0]["score"] > matches[1]["score"]


def test_search_documents_matches_plural_variant():
    documents = [_doc("vendor-c.pdf", [{"chunk_index": 0, "text": "Rotate certificates on schedule."}])]
    matches = search_documents("certificate", documents)
    assert len(matches) == 1


def test_load_document_index_missing_file_returns_empty(monkeypatch):
    monkeypatch.setenv("DOC_INDEX_PATH", "/nonexistent/path/doc-index.json")
    assert load_document_index() == {"documents": []}


def test_load_document_index_rejects_remote_url(monkeypatch):
    monkeypatch.setenv("DOC_INDEX_PATH", "https://example.com/doc-index.json")
    assert load_document_index() == {"documents": []}


def test_load_document_index_reads_real_file(tmp_path, monkeypatch):
    import json

    index_path = tmp_path / "doc-index.json"
    index_path.write_text(json.dumps({"documents": [{"doc_id": "x.md", "chunks": []}]}), encoding="utf-8")
    monkeypatch.setenv("DOC_INDEX_PATH", str(index_path))

    result = load_document_index()
    assert result["documents"] == [{"doc_id": "x.md", "chunks": []}]
