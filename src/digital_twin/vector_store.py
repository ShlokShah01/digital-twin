"""Self-contained vector store built on LanceDB (no server). Rows are chunks
with their dense embeddings plus keywords, so a query can mix dense + sparse
scoring locally for small corpora."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class VectorStore:
    def __init__(self, path: str | Path, dim: int = 384, table: str = "chunks"):
        self.path = Path(path)
        self.dim = dim
        self.table_name = table
        self._db = None

    def _connect(self):
        if self._db is None:
            import lancedb
            self.path.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.path))
        return self._db

    @staticmethod
    def _collect_table_names(rows) -> list[str]:
        names: list[str] = []
        for r in rows:
            if isinstance(r, str):
                names.append(r)
            elif isinstance(r, (tuple, list)):
                for v in r:
                    if isinstance(v, str):
                        names.append(v)
                    elif isinstance(v, list):
                        names.extend(x for x in v if isinstance(x, str))
        return names

    def _table_names(self) -> list[str]:
        db = self._connect()
        names: list[str] = []
        try:
            names = self._collect_table_names(db.list_tables())
        except Exception:
            pass
        if not names:
            try:
                names = list(db.table_names())
            except Exception:
                pass
        return names

    def exists(self) -> bool:
        return self.table_name in self._table_names()

    def _table(self):
        return self._connect().open_table(self.table_name)

    def drop(self) -> None:
        db = self._connect()
        if self.table_name in self._table_names():
            db.drop_table(self.table_name)

    def count(self) -> int:
        if not self.exists():
            return 0
        return self._table().count_rows()

    def add(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        db = self._connect()
        if not self.exists():
            db.create_table(self.table_name, data=rows)
        else:
            self._table().add(rows)

    def search(self, query_vec: np.ndarray, limit: int = 256) -> list[dict[str, Any]]:
        """Raw ANN search. LanceDB returns rows by L2 distance; cosine similarity
        is computed by the caller so ranking stays metric-agnostic."""
        if not self.exists():
            return []
        q = np.asarray(query_vec, dtype=np.float32).flatten()
        try:
            return self._table().search(q).limit(limit).to_list()
        except Exception:
            return []

    def all_rows(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        return self._table().to_arrow().to_pylist()

    def hybrid_search(self, query_vec: np.ndarray, query_terms: list[str],
                      idf_map: dict[str, float], limit: int,
                      candidate_limit: int = 256, alpha: float = 0.72) -> list[dict[str, Any]]:
        """Dense ANN to gather candidates, then rescore a bounded set with
        cosine + idf-weighted sparse keyword overlap. Returns {'chunk_id',
        'text', 'source', 'title', 'keywords', 'score'} sorted desc."""
        hits = self.search(query_vec, limit=candidate_limit)
        qwords = set(query_terms)
        scored = []
        for h in hits:
            vec = np.asarray(h.get("vector"), dtype=np.float32)
            cos = cosine(query_vec, vec)
            kw = h.get("keywords") or []
            overlap = 0.0
            if qwords:
                for t in qwords:
                    if t in kw:
                        overlap += idf_map.get(t, 1.0)
            score = alpha * cos + (1 - alpha) * math.tanh(overlap)
            scored.append({
                "chunk_id": h.get("chunk_id", h.get("id", "")),
                "text": h.get("text", ""),
                "source": h.get("source", ""),
                "title": h.get("title", ""),
                "keywords": kw,
                "score": score,
            })
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:limit]