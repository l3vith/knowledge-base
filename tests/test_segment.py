import json
import statistics
from pathlib import Path

import pytest

from kb.ingest.segment import mark_boilerplate, segment_document
from kb.models import Element, ParsedDoc, PageText

PARA = ("The company maintains a conservative capital structure with low leverage, "
        "strong liquidity buffers and a disciplined approach to allocating free cash flow.")


def _doc(pages: list[str], outline=None, doc_id="d1") -> ParsedDoc:
    return ParsedDoc(doc_id=doc_id, file_name=f"{doc_id}.pdf", page_count=len(pages),
                     pages=[PageText(i + 1, md, False, []) for i, md in enumerate(pages)],
                     outline=outline or [], pdf_metadata={})


def test_heading_prefixed_and_section():
    els, sections = segment_document(_doc([f"# Risk Management\n\n{PARA}"]))
    assert len(els) == 1
    e = els[0]
    assert e.text.startswith("# Risk Management\n")
    assert e.section == "Risk Management" and sections[1] == "Risk Management"
    assert e.element_id == "d1:p0001:e000" and e.idx == 0 and e.kind == "text"


def test_short_line_becomes_table_caption():
    md = "(Rs in crore)\n\n| Item | FY26 | FY25 |\n|---|---|---|\n| Debt | 10 | 12 |"
    els, _ = segment_document(_doc([md]))
    assert len(els) == 1
    assert els[0].kind == "table"
    assert els[0].text.startswith("Caption: (Rs in crore)\n| Item")


def test_long_table_split_repeats_header():
    rows = "\n".join(f"| row {i} | {'value ' * 4}{i} | {i * 7} |" for i in range(200))
    md = f"| H1 | H2 | H3 |\n|---|---|---|\n{rows}"
    els, _ = segment_document(_doc([md]))
    assert len(els) > 1
    for e in els:
        assert e.kind == "table"
        assert e.text.startswith("| H1 | H2 | H3 |\n|---|---|---|\n")
        assert len(e.text) <= 4300
    assert [e.idx for e in els] == list(range(len(els)))


def test_long_paragraph_split_on_sentence():
    els, _ = segment_document(_doc([" ".join(["This is a sentence about capital ratios."] * 80)]))
    assert len(els) >= 2
    assert all(len(e.text) <= 1800 for e in els)
    assert all(e.text.endswith(".") for e in els[:-1])


def test_outline_sections_carry_across_pages():
    _, sections = segment_document(_doc([PARA, PARA], outline=[(1, "Notes", 1), (2, "Borrowings", 2)]))
    assert sections == {1: "Notes", 2: "Notes > Borrowings"}


def test_markdown_headings_refine_page_only_with_outline():
    doc = _doc([f"## Term loans\n\n{PARA}", PARA], outline=[(1, "Notes", 1)])
    els, sections = segment_document(doc)
    assert els[0].section == "Notes > Term loans"
    assert sections == {1: "Notes > Term loans", 2: "Notes"}


def test_page_number_noise_dropped():
    els, _ = segment_document(_doc([f"12\n\n---\n\n{PARA}"]))
    assert len(els) == 1 and els[0].text == PARA


def test_short_blocks_merge_and_table_gets_heading_caption():
    table = "| Asset | Value |\n|---|---|\n| Cash | 2 |"
    md = f"Short intro.\n\n{PARA}\n\n## Debt\n\nAside.\n\n{PARA}\n\n{table}\n\nTail."
    els, _ = segment_document(_doc([md]))
    assert [e.kind for e in els] == ["text", "text", "table"]
    assert els[0].text == f"Short intro.\n\n{PARA}"
    assert els[1].text.startswith("## Debt\nAside.\n\n")
    assert els[2].text == f"Caption: Debt\n{table}\n\nTail."


def test_boilerplate_marked(settings):
    footer = "Integrated Annual Report 2025-26 | Infosys\n{}"   # page-number line differs; normalised away
    footers = [Element(f"d1:p{i:04d}:e001", "d1", i, 1, "text", "", footer.format(i)) for i in range(1, 11)]
    uniques = [Element(f"d1:p{i:04d}:e000", "d1", i, 0, "text", "", f"Unique paragraph {i}. {PARA}")
               for i in range(1, 11)]
    n = mark_boilerplate(footers + uniques, 10, settings)
    assert n == 10
    assert all(f.flags == ["boilerplate"] for f in footers)
    assert all(u.flags == [] for u in uniques)


INFOSYS = Path(__file__).resolve().parents[1] / "Train" / "Train" / "Documents" / "infosys-ar-26.pdf"


@pytest.mark.slow
@pytest.mark.skipif(not INFOSYS.exists(), reason="training corpus not present")
def test_real_infosys_segmentation(settings):
    import pymupdf
    import pymupdf4llm

    pdf = pymupdf.open(INFOSYS)
    chunks = pymupdf4llm.to_markdown(pdf, page_chunks=True, show_progress=False, use_ocr=False,
                                     header=False, footer=False)
    doc = ParsedDoc("infosys", INFOSYS.name, pdf.page_count,
                    [PageText(c["metadata"]["page_number"], c["text"], False, []) for c in chunks],
                    [tuple(t) for t in pdf.get_toc(simple=True) if t[2] >= 1], {})
    els, _ = segment_document(doc)
    mark_boilerplate(els, doc.page_count, settings)
    median = statistics.median(len(e.text) for e in els)
    print(json.dumps({"elements": len(els), "median_chars": median,
                      "boilerplate": sum("boilerplate" in e.flags for e in els)}))
    assert 250 <= median <= 900
    assert any("Sundaram" in e.text for e in els if e.page_no == 108)
