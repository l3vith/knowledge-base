"""CPU models via fastembed (ONNX): bge-small embeddings and the MiniLM cross-encoder, cached per process."""
import logging
import threading

import numpy as np

from kb.models import Embedder, Reranker

log = logging.getLogger(__name__)
_cache: dict[tuple[str, str], object] = {}
_cache_lock = threading.Lock()


class FastEmbedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name)
        self.dim = self.model.embedding_size

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        out = np.asarray(list(self.model.embed(list(texts), batch_size=64)), dtype=np.float32)
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class FastReranker:
    def __init__(self, model_name: str):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model = TextCrossEncoder(model_name)

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        return [float(s) for s in self.model.rerank(query, list(texts), batch_size=64)]  # input order


def get_embedder(settings) -> Embedder:
    key = ("embed", settings.embed_model)
    with _cache_lock:
        if key not in _cache:
            _cache[key] = FastEmbedder(settings.embed_model)
        return _cache[key]


def get_reranker(settings) -> Reranker | None:
    if not getattr(settings, "use_reranker", True):
        return None  # KB_RERANKER=0: saves ~100 MB RAM on small hosts; triage then sends everything to the LLM band
    key = ("rerank", settings.rerank_model)
    with _cache_lock:
        if key not in _cache:
            try:
                _cache[key] = FastReranker(settings.rerank_model)
            except Exception:
                log.warning("cross-encoder %s failed to load; triage runs without it", settings.rerank_model, exc_info=True)
                _cache[key] = None
        return _cache[key]
