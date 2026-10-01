"""Embeddings via fastembed (ONNX, CPU-friendly). Downloads the model once to
the system cache, then embeds lazily."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import numpy as np


@lru_cache(maxsize=1)
def _backend(model_name: str):
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=model_name)


class Embedder:
    """Thin, cached wrapper around fastembed with numpy-array output."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name

    def _model(self):
        return _backend(self.model_name)

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        texts = list(texts)
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        return np.array(list(self._model().embed(texts)), dtype=np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    def dim(self) -> int:
        try:
            return int(self._model().dim)
        except AttributeError:
            pass
        if getattr(self, "_dim_cache", None) is None:
            self._dim_cache = int(self.embed_one("dimension probe").shape[0])
        return self._dim_cache