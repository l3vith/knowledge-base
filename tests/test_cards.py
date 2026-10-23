from dataclasses import replace
from pathlib import Path

import pytest

from kb.ingest.cards import (assign_sibling_groups, augment_topics, build_doc_card, build_page_cards,
                             extract_identifiers, normalize_issuer)
from kb.llm import FakeLLM, LLMError
from kb.models import BLANK_PAGE_SUMMARY, DocCard, PageCard, PageText, ParsedDoc


def _doc(pages: list[str], meta: dict | None = None) -> ParsedDoc:
    return ParsedDoc("d1", "x.pdf", len(pages), [PageText(i, t, False, []) for i, t in enumerate(pages, 1)],
                     [], meta or {})


def _card(issuer="Acme", label="", year=None, topics=None) -> DocCard:
    return DocCard("d1", "x.pdf", "Acme Report", "annual_report", issuer, [], label, year, None, "", topics or [],
                   "", 1)


def test_doc_card_parses_and_coerces(settings):
    doc = _doc(["Federal Register notice on capital rules for large banks.\n[FR Doc. 2026–05959 Filed 3-1-26] " * 2])
    llm = FakeLLM(lambda name, s, u: {"title": "Capital Rule", "doc_type": "proposed_rule", "issuer": "FDIC",
                                      "entities": ["FDIC"] * 15, "period_label": "2025", "period_year": "2025",
                                      "publication_date": None, "jurisdiction": "US", "topics": ["capital"],
                                      "summary": "s"})
    card = build_doc_card(llm, doc, settings)
    assert card.period_year == 2025 and card.title == "Capital Rule" and len(card.entities) == 10
    assert card.identifiers == ["FR Doc. 2026–05959"]
    name, _, user = llm.calls[0]
    assert name == "doc_card" and "do not trust it" in user and "FR Doc. 2026–05959" in user


def test_doc_card_fallback(settings):
    def boom(name, s, u):
        raise LLMError("down")
    doc = _doc(["\n# Acme Annual Report\nRevenue grew in 2024 and 2024 again, 2023 once. " + "x" * 60])
    card = build_doc_card(FakeLLM(boom), doc, settings)
    assert card.title == "Acme Annual Report" and card.doc_type == "other"
    assert card.period_year == 2024 and card.period_label == "2024"
    assert card.summary.startswith("--- page 1 ---")
    # non-dict output also falls back
    assert build_doc_card(FakeLLM(lambda *a: "not json"), doc, settings).doc_type == "other"


def test_extract_identifiers():
    doc = _doc(["FR Doc. 2026–05959 filed. RIN 3064–AF29 applies. See ASU 2016-13 and ASU 2016-13."])
    ids = extract_identifiers(doc)
    assert ids == ["FR Doc. 2026–05959", "RIN 3064–AF29", "ASU 2016-13"]


def test_page_cards_batching_blank_and_fallback(settings):
    settings = replace(settings, page_card_pages_per_call=3, page_cards_mode="llm")
    texts = [f"Page {i} discusses loan loss provisioning in detail for the year." for i in range(1, 6)]
    texts[1] = "  "
    doc = _doc(texts)

    def responder(name, s, u):
        if "=== page 5" in u:
            raise LLMError("fail")
        return {"pages": [{"page_no": 1, "summary": "one", "topics": ["a"]},
                          {"page_no": "3", "summary": "three"},
                          {"page_no": 99, "summary": "ignored"}]}
    llm = FakeLLM(responder)
    cards = build_page_cards(llm, doc, _card(), {1: "Intro", 5: "End"}, settings)
    assert [c.page_no for c in cards] == [1, 2, 3, 4, 5]
    assert cards[0].summary == "one" and cards[0].section == "Intro" and cards[0].topics == ["a"]
    assert cards[1].summary == BLANK_PAGE_SUMMARY
    assert cards[2].summary == "three"
    assert cards[3].summary == texts[3]          # missing from response -> fallback
    assert cards[4].summary == texts[4] and cards[4].section == "End"
    assert len(llm.calls) == 2 and all(c[0] == "page_card" for c in llm.calls)
    assert "=== page 2" not in "".join(c[2] for c in llm.calls)


def test_sibling_groups():
    assert normalize_issuer("Metal Coats (India) Limited") == "metal coats india"
    cards = assign_sibling_groups([_card("Metal Coats (India) Limited", "FY2025", 2025),
                                   _card("Metal Coats India Ltd.", "FY2026", 2026),
                                   _card("Other Bank", "FY2026", 2026), _card("", "", None)])
    assert [c.sibling_group for c in cards] == ["metal coats india", "metal coats india", None, None]
    same = assign_sibling_groups([_card("Acme", "FY2025", 2025), _card("Acme Inc", "FY2025", 2025)])
    assert [c.sibling_group for c in same] == [None, None]


def test_augment_topics():
    pcs = [PageCard("d1", i, "", "s", topics, [], []) for i, topics in
           enumerate([["Credit Risk", "Liquidity"], ["credit risk"], ["CAPITAL"], ["Liquidity"]], 1)]
    card = augment_topics(_card(topics=["capital"]), pcs)
    assert card.topics == ["capital", "Credit Risk", "Liquidity"]
    many = [PageCard("d1", 1, "", "s", [f"t{i}" for i in range(30)], [], [])]
    assert len(augment_topics(_card(topics=[f"x{i}" for i in range(10)]), many).topics) == 20


_DOCS = Path(__file__).resolve().parents[1] / "Train" / "Train" / "Documents"


@pytest.mark.slow
def test_identifiers_on_real_federal_register_docs():
    import pymupdf
    found = {}
    for name in ("91fr14952.pdf", "91fr14908.pdf"):
        pdf = pymupdf.open(_DOCS / name)
        pages = [PageText(i + 1, pdf[i].get_text(), False, []) for i in range(len(pdf))]
        found[name] = extract_identifiers(ParsedDoc("d", name, len(pdf), pages, [], {}))
        print(name, found[name])
    assert "FR Doc. 2026–05959" in found["91fr14952.pdf"]
    assert "FR Doc. 2026–05961" in found["91fr14908.pdf"]
    assert "FR Doc. 2026–05961" not in found["91fr14952.pdf"]


def test_extractive_page_cards_need_no_llm(settings):
    from dataclasses import replace as _replace

    from kb.ingest.cards import build_page_cards as _bpc
    from kb.llm import FakeLLM as _Fake
    from kb.models import PageText as _PT, ParsedDoc as _PD

    doc = _PD("d1", "f.pdf", 3, [
        _PT(1, "Gross NPA ratio rose to 3.1% in FY2025 as Alpha Bank Limited recognised stressed loans.", False, []),
        _PT(2, "", False, []),
        _PT(3, "| Item | FY26 |\n|---|---|\n| Total borrowings | 4,053.90 |\nLenders recalled all facilities of the company.",
            False, [])], [], {})

    def boom(n, s, u):
        raise AssertionError("no LLM in extractive mode")

    llm = _Fake(boom)
    cards = _bpc(llm, doc, None, {1: "Asset quality"}, _replace(settings, page_cards_mode="extractive"))
    assert [c.page_no for c in cards] == [1, 2, 3] and llm.calls == []
    assert cards[0].summary.startswith("Gross NPA ratio rose") and cards[0].section == "Asset quality"
    assert cards[1].summary == "(blank or image-only page)"
    assert any("4,053.90" in f for f in cards[2].figures) and "Alpha Bank Limited" in cards[0].entities
