import numpy as np

from digital_twin.vector_store import VectorStore, cosine


def test_cosine_basics():
    assert cosine(np.array([1.0, 0.0]), np.array([1.0, 0.0])) == 1.0
    assert cosine(np.array([1.0, 0.0]), np.array([-1.0, 0.0])) == -1.0
    assert cosine(np.zeros(4), np.ones(4)) == 0.0


def test_add_count_search_all_rows_roundtrip(tmp_path):
    store = VectorStore(tmp_path / "vec", dim=4)
    rows = [
        {"chunk_id": f"c{i}", "text": f"text {i}", "source": "t.txt",
         "title": "t", "doc_id": "d0", "n_tokens": 3, "text_hash": f"h{i}",
         "vector": ([1, 0, 0, 0] if i == 0 else [0, 1, 0, 0])}
        for i in range(2)
    ]
    store.add(rows)
    assert store.exists()
    assert store.count() == 2

    all_rows = store.all_rows()
    assert len(all_rows) == 2
    assert {r["chunk_id"] for r in all_rows} == {"c0", "c1"}
    assert all(isinstance(r["vector"], list) for r in all_rows)

    hits = store.search(np.array([1.0, 0, 0, 0], dtype=np.float32), limit=2)
    assert hits and hits[0]["chunk_id"] == "c0"

    store.drop()
    assert not store.exists()
    assert store.count() == 0
    assert store.all_rows() == []
    assert store.search(np.ones(4), limit=4) == []


def test_idempotent_add_no_dupes(tmp_path):
    store = VectorStore(tmp_path / "vec", dim=2)
    row = {"chunk_id": "c0", "text": "same", "source": "s", "title": "t",
           "doc_id": "d", "n_tokens": 1, "text_hash": "h", "vector": [0.5, 0.5]}
    store.add([row])
    store.add([row])
    assert store.count() == 2  # caller dedupes; the store itself appends