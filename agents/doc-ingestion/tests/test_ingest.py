from pathlib import Path

from ingest import chunk_text, ingest_directory, ingest_document


def test_chunk_text_splits_on_paragraph_boundaries():
    text = "Para one." + "\n\n" + "Para two." + "\n\n" + "Para three."
    chunks = chunk_text(text, max_chars=15)
    assert chunks == ["Para one.", "Para two.", "Para three."]


def test_chunk_text_merges_short_paragraphs_under_limit():
    text = "Short one." + "\n\n" + "Short two."
    chunks = chunk_text(text, max_chars=1000)
    assert len(chunks) == 1
    assert "Short one." in chunks[0]
    assert "Short two." in chunks[0]


def test_chunk_text_empty_string_returns_no_chunks():
    assert chunk_text("") == []


def test_ingest_document_md(tmp_path: Path):
    doc = tmp_path / "runbook.md"
    doc.write_text("# Title\n\nThis is a runbook describing certificate rotation.", encoding="utf-8")

    result = ingest_document(doc, doc_id="runbook.md")

    assert result["doc_id"] == "runbook.md"
    assert result["format"] == "md"
    assert result["chunk_count"] >= 1
    assert "certificate rotation" in result["chunks"][0]["text"]
    assert result["chunks"][0]["page"] is None


def _build_minimal_pdf(text: str) -> bytes:
    """Assemble a minimal single-page PDF with a correct xref table so pypdf
    can parse it, containing the given text via a simple content stream."""
    content = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 300 150]/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length " + str(len(content)).encode() + b">>\nstream\n" + content + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj".encode() + body + b"endobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\n".encode()
    out += f"startxref\n{xref_offset}\n%%EOF".encode()
    return bytes(out)


def test_ingest_document_pdf(tmp_path: Path):
    pdf_path = tmp_path / "vendor-roadmap.pdf"
    pdf_path.write_bytes(_build_minimal_pdf("Hello PQC Roadmap"))

    result = ingest_document(pdf_path, doc_id="vendor-roadmap.pdf")

    assert result["format"] == "pdf"
    assert result["chunk_count"] == 1
    assert "Hello PQC Roadmap" in result["chunks"][0]["text"]
    assert result["chunks"][0]["page"] == 1


def test_ingest_directory_walks_supported_files_and_skips_others(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("plain text notes about vendor X.", encoding="utf-8")
    (tmp_path / "ignored.json").write_text("{}", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "policy.md").write_text("Policy: rotate keys every 90 days.", encoding="utf-8")

    index = ingest_directory(tmp_path)

    assert index["document_count"] == 2
    doc_ids = {d["doc_id"] for d in index["documents"]}
    assert doc_ids == {"notes.txt", "sub/policy.md"}
    assert index["errors"] == []


def test_ingest_directory_records_errors_without_aborting(tmp_path: Path, monkeypatch):
    good = tmp_path / "good.txt"
    good.write_text("fine", encoding="utf-8")
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a real pdf")

    index = ingest_directory(tmp_path)

    assert index["document_count"] == 1
    assert len(index["errors"]) == 1
    assert index["errors"][0]["source_path"] == "bad.pdf"
