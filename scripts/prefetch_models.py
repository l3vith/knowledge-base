"""Download the CPU models into FASTEMBED_CACHE_PATH at build time (no download on every cold start).

    FASTEMBED_CACHE_PATH=./models python scripts/prefetch_models.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kb.config import get_settings  # noqa: E402

if __name__ == "__main__":
    from fastembed import TextEmbedding
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    s = get_settings()
    print("cache:", os.environ.get("FASTEMBED_CACHE_PATH", "(fastembed default)"))
    TextEmbedding(s.embed_model).embed(["warm up"])
    if s.use_reranker:
        list(TextCrossEncoder(s.rerank_model).rerank("warm", ["up"]))
    print("models ready")
