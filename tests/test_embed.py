import time

import numpy as np
import pytest

from kb.config import get_settings
from kb.embed import FastEmbedder, FastReranker, get_embedder, get_reranker


def test_get_reranker_none_when_model_fails(monkeypatch):
    import kb.embed as embed

    def boom(name):
        raise RuntimeError("no model")

    monkeypatch.setattr(embed, "FastReranker", boom)
    monkeypatch.setattr(embed, "_cache", {})
    assert get_reranker(get_settings(rerank_model="bogus/model")) is None


@pytest.mark.slow
def test_fast_models_load_and_score():
    s = get_settings()
    emb = get_embedder(s)
    assert get_embedder(s) is emb
    v = emb.embed(["capital adequacy ratio", "weather today"])
    assert v.shape == (2, 384) and v.dtype == np.float32
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    assert emb.embed([]).shape == (0, 384)
    rr = get_reranker(s)
    q = "What is the minimum common equity tier 1 capital ratio?"
    rel = "Banks must maintain a minimum common equity tier 1 capital ratio of 4.5 percent of risk-weighted assets."
    irr = "The cafeteria serves lunch from noon until two in the afternoon."
    a, b = rr.score(q, [rel, irr])
    c, d = rr.score(q, [irr, rel])  # scores follow input order
    assert a > b and d > c and abs(a - d) < 1e-4


@pytest.mark.slow
def test_measure_throughput(capsys):
    text = ("The allowance for credit losses under the current expected credit loss model reflects lifetime "
            "expected losses on financial assets measured at amortised cost, including loans and held-to-maturity "
            "securities. ") * 4
    texts = [f"{i} {text}"[:800] for i in range(512)]
    emb, rr = FastEmbedder("BAAI/bge-small-en-v1.5"), FastReranker("Xenova/ms-marco-MiniLM-L-6-v2")
    emb.embed(texts[:8])
    t0 = time.perf_counter()
    emb.embed(texts)
    tps = 512 / (time.perf_counter() - t0)
    pairs = [t[:700] for t in (texts * 2)[:1000]]
    t0 = time.perf_counter()
    rr.score("How is the CECL allowance measured?", pairs)
    pps = 1000 / (time.perf_counter() - t0)
    with capsys.disabled():
        print(f"\nFastEmbedder {tps:.1f} texts/s; FastReranker {pps:.1f} pairs/s")
