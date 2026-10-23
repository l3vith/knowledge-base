import re
import zipfile
from dataclasses import replace

import pytest

from kb.errors import KBError
from kb.ingest.pipeline import index_collection, safe_extract
from kb.llm import FakeLLM
from kb.registry import Registry
from kb.store import Store
from kb.testing import HashEmbedder, make_pdf


def card_responder(name, system, user):
    if name == "doc_card":
        return {"title": "Alpha Bank Annual Report", "doc_type": "annual_report", "issuer": "Alpha Bank",
                "entities": ["Alpha Bank"], "period_label": "FY2025", "period_year": 2025, "publication_date": None,
                "jurisdiction": "India", "topics": ["capital"], "summary": "Annual report."}
    pages = [int(n) for n in re.findall(r"=== page (\d+)", user)]
    return {"pages": [{"page_no": n, "summary": f"card for page {n}", "topics": ["capital"], "entities": [],
                       "figures": []} for n in pages]}


def _zip(tmp_path, files: dict[str, bytes], name="in.zip"):
    z = tmp_path / name
    with zipfile.ZipFile(z, "w") as f:
        for member, data in files.items():
            f.writestr(member, data)
    return z


def _pdf_bytes(tmp_path, pages, name="a.pdf"):
    return make_pdf(tmp_path / "src" / name, pages).read_bytes()


@pytest.fixture
def s1(settings):
    return replace(settings, parse_workers=1, page_cards_mode="llm")


def test_safe_extract_rejects_traversal(tmp_path, s1):
    z = _zip(tmp_path, {"../evil.pdf": b"%PDF", "ok.pdf": b"%PDF"})
    with pytest.raises(KBError) as e:
        safe_extract(z, tmp_path / "out", s1)
    assert e.value.code == "INVALID_ARCHIVE"
    assert not (tmp_path / "evil.pdf").exists()


def test_safe_extract_skips_junk_and_keeps_dup_basenames(tmp_path, s1):
    z = _zip(tmp_path, {"a/x.pdf": b"%PDF-1", "b/x.pdf": b"%PDF-2", "c/y.PDF": b"%PDF-3",
                        "__MACOSX/a/._x.pdf": b"junk", "notes.txt": b"hi", ".DS_Store": b""})
    files, warnings = safe_extract(z, tmp_path / "out", s1)
    assert sorted(d for _, d in files) == ["a/x.pdf", "b/x.pdf", "y.PDF"]
    assert warnings == ["skipped non-PDF file: notes.txt"]
    assert all(p.is_file() for p, _ in files)


def test_safe_extract_errors(tmp_path, s1):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(KBError) as e:
        safe_extract(bad, tmp_path / "o1", s1)
    assert e.value.code == "INVALID_ARCHIVE"
    with pytest.raises(KBError) as e:
        safe_extract(_zip(tmp_path, {"a.txt": b"x"}, "n.zip"), tmp_path / "o2", s1)
    assert e.value.code == "NO_DOCUMENTS"
    with pytest.raises(KBError) as e:
        safe_extract(_zip(tmp_path, {"a.pdf": b"x" * 100}, "big.zip"), tmp_path / "o3", replace(s1, max_archive_bytes=10))
    assert e.value.code == "ARCHIVE_TOO_LARGE"


def test_index_end_to_end(tmp_path, s1):
    pdf = _pdf_bytes(tmp_path, ["Alpha bank capital ratio was 14.2 percent in FY2025 under the framework.",
                                "Liquidity coverage ratio stayed above the regulatory minimum all year."])
    z = _zip(tmp_path, {"docs/a.pdf": pdf, "docs/copy_of_a.pdf": pdf})
    out = index_collection(z, "c1", settings=s1, llm=FakeLLM(card_responder), embedder=HashEmbedder(), use_ocr=False)
    assert out["status"] == "ready" and out["documents"] == 1 and out["pages"] == 2 and out["elements"] >= 2
    assert any("duplicate of" in w for w in out["warnings"])
    assert out["llm_usage"]["calls"] == 2  # one doc card + one page-card batch
    gen_id, gen_dir = Registry(s1).active_dir("c1")
    assert gen_id == out["generation_id"] and not (gen_dir / "src").exists()
    store = Store.open(gen_dir)
    try:
        card = store.docs()[0]
        assert card.file_name in ("a.pdf", "copy_of_a.pdf") and card.period_year == 2025
        assert store.search_pages(["liquidity"], None, 1)[0][1] == 2
        assert store.dense_pages(HashEmbedder().embed(["card for page 2"]), None, 1)[0][1] == 2
        assert store.dense_elements(HashEmbedder().embed(["capital"]), None, 1) == []  # embed_elements off
        assert any("14.2" in e.text for e in store.elements_for_pages(card.doc_id, [1]))
    finally:
        store.close()


def test_failed_reindex_keeps_old_generation(tmp_path, s1):
    z = _zip(tmp_path, {"a.pdf": _pdf_bytes(tmp_path, ["Alpha bank capital ratio was 14.2 percent in FY2025."])})
    first = index_collection(z, "c1", settings=s1, llm=FakeLLM(card_responder), embedder=HashEmbedder(), use_ocr=False)

    class Boom:
        def embed(self, texts):
            raise RuntimeError("embedder down")

    with pytest.raises(RuntimeError):  # cache off, otherwise cached vectors would skip the embedder entirely
        index_collection(z, "c1", settings=replace(s1, use_cache=False), llm=FakeLLM(card_responder),
                         embedder=Boom(), use_ocr=False)
    gen_id, gen_dir = Registry(s1).active_dir("c1")
    assert gen_id == first["generation_id"]
    assert [d.name for d in (gen_dir.parent).iterdir()] == [gen_id]  # failed staging was discarded


def test_reindex_hits_cache_and_skips_parse_llm_embed(tmp_path, s1, monkeypatch):
    import kb.ingest.pipeline as pl

    z = _zip(tmp_path, {"a.pdf": _pdf_bytes(tmp_path, ["Alpha bank capital ratio was 14.2 percent in FY2025.",
                                                       "Liquidity coverage ratio stayed above the minimum."])})
    first = index_collection(z, "c1", settings=s1, llm=FakeLLM(card_responder), embedder=HashEmbedder(), use_ocr=False)
    assert first["cache_hits"] == {"parse": 0, "cards": 0, "embeddings": 0}

    def no_parse(*a, **k):
        raise AssertionError("parse_pages must not run on a cache hit")

    class NoEmbed:
        def embed(self, texts):
            raise AssertionError("embedder must not run on a cache hit")

    monkeypatch.setattr(pl, "parse_pages", no_parse)
    llm = FakeLLM(card_responder)
    second = index_collection(z, "c2", settings=s1, llm=llm, embedder=NoEmbed(), use_ocr=False)
    assert second["cache_hits"] == {"parse": 1, "cards": 1, "embeddings": 1}
    assert llm.calls == [] and second["elements"] == first["elements"]
    store = Store.open(Registry(s1).active_dir("c2")[1])
    try:
        assert store.search_pages(["liquidity"], None, 1)[0][1] == 2
        assert store.docs()[0].period_year == 2025
    finally:
        store.close()


def test_failed_llm_cards_are_not_cached(tmp_path, s1):
    from kb.llm import LLMError

    z = _zip(tmp_path, {"a.pdf": _pdf_bytes(tmp_path, ["Alpha bank capital ratio was 14.2 percent in FY2025."])})

    def failing(name, system, user):
        raise LLMError("no key")

    index_collection(z, "c1", settings=s1, llm=FakeLLM(failing), embedder=HashEmbedder(), use_ocr=False)
    llm = FakeLLM(card_responder)
    out = index_collection(z, "c2", settings=s1, llm=llm, embedder=HashEmbedder(), use_ocr=False)
    assert out["cache_hits"]["parse"] == 1 and out["cache_hits"]["cards"] == 0 and out["cache_hits"]["embeddings"] == 0
    assert any(c[0] == "doc_card" for c in llm.calls)  # cards rebuilt with the working LLM


def test_bad_name(tmp_path, s1):
    with pytest.raises(KBError) as e:
        index_collection(tmp_path / "z.zip", "bad name!", settings=s1, llm=FakeLLM(card_responder),
                         embedder=HashEmbedder(), use_ocr=False)
    assert e.value.code == "INVALID_COLLECTION_NAME" and e.value.http_status == 422


@pytest.mark.slow
def test_process_pool_parse(tmp_path, settings):
    """Real spawn-based worker pool on this OS (page_job_size=2 forces several jobs)."""
    pages = [f"Page {i} discusses capital buffers and leverage in detail for testing purposes." for i in range(1, 6)]
    z = _zip(tmp_path, {"a.pdf": _pdf_bytes(tmp_path, pages)})
    s = replace(settings, parse_workers=2, page_job_size=2)
    out = index_collection(z, "pool", settings=s, llm=FakeLLM(card_responder), embedder=HashEmbedder(), use_ocr=False)
    assert out["pages"] == 5
    store = Store.open(Registry(s).active_dir("pool")[1])
    try:
        assert [pc.page_no for pc in store.page_cards(store.docs()[0].doc_id)] == [1, 2, 3, 4, 5]
    finally:
        store.close()
