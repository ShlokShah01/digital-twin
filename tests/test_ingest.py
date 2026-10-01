from digital_twin.ingest import chunk_documents, load_directory, load_file
from digital_twin import demo


def test_loaders_cover_all_kinds(tmp_path):
    demo.generate(tmp_path)
    docs = load_directory(tmp_path)
    kinds = {d.kind for d in docs}
    assert kinds >= {"text", "json", "csv", "markdown"}
    assert len(docs) >= 4


def test_load_file_returns_documents(tmp_path):
    demo.generate(tmp_path)
    md = load_file(tmp_path / "journal.md")
    assert md and md[0].kind == "markdown"
    assert len(md[0].text) > 100


def test_chunk_documents_word_sorted(tmp_path):
    demo.generate(tmp_path)
    docs = load_directory(tmp_path)
    chunks = chunk_documents(docs, chunk_words=150, overlap=30)
    assert chunks
    assert all(c.text for c in chunks)
    assert all(isinstance(c.n_tokens, int) for c in chunks)
    ids = [c.id for c in chunks]
    assert len(set(ids)) == len(ids)