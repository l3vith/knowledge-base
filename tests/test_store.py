import numpy as np
import pytest

from kb.errors import CollectionNotFound
from kb.models import BLANK_PAGE_SUMMARY, DocCard, Element, PageCard, PageText
from kb.store import Store, fts_query
from kb.testing import HashEmbedder


def _card(doc_id, pages=2):
    return DocCard(doc_id, f"{doc_id}.pdf", doc_id, "other", doc_id, [], "", None, None, "", [], "", pages)


def _add(store, doc_id, page_texts, boiler_footer=None):
    pages, cards, els = [], [], []
    for p, text in enumerate(page_texts, start=1):
        pages.append(PageText(p, text, False, []))
        cards.append(PageCard(doc_id, p, "", text[:200] or BLANK_PAGE_SUMMARY, [], [], []))
        blocks = [b for b in text.split("\n\n") if b]
        if boiler_footer:
            blocks.append(boiler_footer)
        for i, b in enumerate(blocks):
            flags = ["boilerplate"] if b == boiler_footer else []
            els.append(Element(f"{doc_id}:p{p:04d}:e{i:03d}", doc_id, p, i, "text", "Notes", b, flags))
    store.add_document(_card(doc_id, len(page_texts)), pages, cards, els)
    return els


def test_roundtrip_and_ordering(tmp_path):
    s = Store.create(tmp_path / "g")
    _add(s, "d1", ["alpha intro\n\nbeta para", "gamma credit risk", ""], boiler_footer="Company footer")
    assert [d.doc_id for d in s.docs()] == ["d1"] and s.doc("d1").file_name == "d1.pdf"
    with pytest.raises(KeyError):
        s.doc("nope")
    els = s.elements_for_pages("d1", [2, 1])
    assert [(e.page_no, e.idx) for e in els] == [(1, 0), (1, 1), (2, 0)]
    assert all("boilerplate" not in e.flags for e in els)
    assert len(s.elements_for_pages("d1", [1, 2], include_boilerplate=True)) == 5
    assert [pc.page_no for pc in s.page_cards("d1")] == [1, 2, 3]
    assert [pc.page_no for pc in s.page_cards("d1", [3, 1])] == [1, 3]
    assert s.nonblank_pages("d1") == [1, 2]
    ids = ["d1:p0002:e000", "missing", "d1:p0001:e000"]
    assert [e.element_id for e in s.elements_by_ids(ids)] == ["d1:p0002:e000", "d1:p0001:e000"]
    s.close()
    s2 = Store.open(tmp_path / "g")
    assert s2.elements_by_ids(["d1:p0001:e001"])[0].text == "beta para"
    s2.close()


def test_fts_sanitizes_operators():
    assert fts_query(['"NEAR" AND 10-K*', "asc 326-20: ₹"]) == '"10" OR "asc" OR "326" OR "20"'
    assert fts_query(["AND OR NOT"]) == ""


def test_search_pages_and_elements(tmp_path):
    s = Store.create(tmp_path / "g")
    _add(s, "d1", ["liquidity coverage ratio overview", "Allowance under ASC 326-20 per the 10-K filing"],
         boiler_footer="ASC 326-20 footer")
    pages = s.search_pages(['ASC 326-20 "10-K"'], None, 5)
    assert pages[0][:2] == ("d1", 2) and pages[0][2] > 0
    els = s.search_elements(['ASC 326-20 "10-K"'], ["d1"], 5)
    assert els[0][0] == "d1:p0002:e000"
    assert all(not e.endswith("e001") for e, _ in els)  # boilerplate footer never searchable
    assert s.search_pages(["AND OR NOT"], None, 5) == []
    assert s.search_elements(["asc"], ["other"], 5) == [] and s.search_elements(["asc"], [], 5) == []


def test_dense_scoped_to_docs(tmp_path):
    emb = HashEmbedder()
    s = Store.create(tmp_path / "g")
    e1 = _add(s, "d1", ["capital buffer requirement", "other"])
    e2 = _add(s, "d2", ["unrelated text about weather", "rainfall"])
    els = e1 + e2
    s.set_vectors("element", [e.element_id for e in els], emb.embed([e.text for e in els]))
    s.set_vectors("page", [[e.doc_id, e.page_no] for e in els], emb.embed([e.text for e in els]))
    q = emb.embed(["capital buffer requirement"])
    assert s.dense_elements(q, None, 1)[0][0] == "d1:p0001:e000"
    scoped = s.dense_elements(q, ["d2"], 10)
    assert scoped and all(eid.startswith("d2:") for eid, _ in scoped)
    assert s.dense_pages(q, None, 1)[0][:2] == ("d1", 1)
    assert all(d == "d2" for d, _, _ in s.dense_pages(q, ["d2"], 10))
    s.close()
    s2 = Store.open(tmp_path / "g")  # vectors reload from disk
    assert s2.dense_elements(q, ["d1"], 1)[0][0] == "d1:p0001:e000"
    s2.close()


def test_dense_elements_empty_without_vectors(tmp_path):
    s = Store.create(tmp_path / "g")
    _add(s, "d1", ["text"])
    assert s.dense_elements(np.ones((1, 8), np.float32), None, 5) == []
    assert s.dense_pages(np.ones((1, 8), np.float32), None, 5) == []


def test_open_missing_raises(tmp_path):
    with pytest.raises(CollectionNotFound):
        Store.open(tmp_path / "nothing")
