import pymupdf4llm
import pytest

from kb.ingest import parse
from kb.ingest.parse import doc_id_for, parse_pages, parse_pdf, read_pdf_info
from kb.testing import make_pdf

LONG = "Capital adequacy ratios are reported quarterly to the board of directors."


class StubOCR:
    def __init__(self):
        self.calls = 0

    def image_to_text(self, png_bytes: bytes) -> str:
        self.calls += 1
        return "OCR TEXT"


def _blank_image_page(monkeypatch, page_no=2):
    real = pymupdf4llm.to_markdown

    def fake(doc, **kw):
        chunks = real(doc, **kw)
        for c in chunks:
            if c["metadata"]["page_number"] == page_no:
                c["text"] = ""
        return chunks

    monkeypatch.setattr(pymupdf4llm, "to_markdown", fake)


def test_pages_one_based_and_text(tmp_path, settings):
    pdf = make_pdf(tmp_path / "a.pdf", [LONG, "Second page " + LONG])
    doc = parse_pdf(pdf, settings)
    assert [p.page_no for p in doc.pages] == [1, 2]
    assert "Capital adequacy" in doc.pages[0].markdown
    assert "Second page" in doc.pages[1].markdown
    assert not any(p.is_ocr for p in doc.pages)
    assert len(doc.doc_id) == 10 and doc.doc_id == doc_id_for(pdf)
    assert doc.file_name == "a.pdf" and doc.page_count == 2 and doc.ocr_unavailable_pages == 0


def test_outline_and_toc_titles(tmp_path, settings):
    pdf = make_pdf(tmp_path / "t.pdf", [LONG] * 3, toc=[[1, "Intro", 1], [1, "Risk", 2], [2, "Credit", 3]])
    doc_id, count, outline, meta = read_pdf_info(pdf)
    assert count == 3 and isinstance(meta, dict)
    assert outline == [(1, "Intro", 1), (1, "Risk", 2), (2, "Credit", 3)]
    doc = parse_pdf(pdf, settings)
    assert doc.outline == outline
    assert doc.pages[2].toc_titles == ["Credit"]
    assert doc.pages[0].toc_titles == ["Intro"]


def test_image_only_page_uses_ocr(tmp_path, settings, monkeypatch):
    pdf = make_pdf(tmp_path / "i.pdf", [LONG, "CAPITAL BUFFER"], image_only_pages={1})
    _blank_image_page(monkeypatch)
    stub = StubOCR()
    monkeypatch.setattr(parse, "get_ocr_engine", lambda: stub)
    doc = parse_pdf(pdf, settings)
    assert doc.pages[1].is_ocr and doc.pages[1].markdown == "OCR TEXT"
    assert not doc.pages[0].is_ocr
    assert stub.calls == 1 and doc.ocr_unavailable_pages == 0


def test_image_only_page_without_engine(tmp_path, settings, monkeypatch):
    pdf = make_pdf(tmp_path / "i.pdf", [LONG, "CAPITAL BUFFER"], image_only_pages={1})
    _blank_image_page(monkeypatch)
    monkeypatch.setattr(parse, "get_ocr_engine", lambda: None)
    pages, unavailable = parse_pages(pdf, 1, 2, settings, use_ocr=True)
    assert pages[1].markdown == "" and not pages[1].is_ocr
    assert unavailable == 1


def test_use_ocr_false_skips_ocr(tmp_path, settings, monkeypatch):
    pdf = make_pdf(tmp_path / "i.pdf", [LONG, "CAPITAL BUFFER"], image_only_pages={1})
    stub = StubOCR()
    monkeypatch.setattr(parse, "get_ocr_engine", lambda: stub)
    pages, unavailable = parse_pages(pdf, 1, 2, settings, use_ocr=False)
    assert pages[1].markdown == "" and stub.calls == 0 and unavailable == 0


def test_to_markdown_failure_falls_back_to_plain_text(tmp_path, settings, monkeypatch):
    pdf = make_pdf(tmp_path / "f.pdf", [LONG])

    def boom(*a, **kw):
        raise RuntimeError("layout failed")

    monkeypatch.setattr(pymupdf4llm, "to_markdown", boom)
    pages, _ = parse_pages(pdf, 1, 1, settings, use_ocr=False)
    assert "Capital adequacy" in pages[0].markdown


def test_parse_pages_range(tmp_path, settings):
    pdf = make_pdf(tmp_path / "r.pdf", [f"Page {i} " + LONG for i in range(1, 6)])
    pages, unavailable = parse_pages(pdf, 2, 4, settings, use_ocr=False)
    assert [p.page_no for p in pages] == [2, 3, 4]
    assert "Page 3" in pages[1].markdown and unavailable == 0


@pytest.mark.slow
def test_rapidocr_reads_text(tmp_path, settings):
    from kb.ingest.ocr import RapidOCREngine

    pdf = make_pdf(tmp_path / "o.pdf", ["CAPITAL BUFFER 2.5 PERCENT"], image_only_pages={0})
    import pymupdf

    with pymupdf.open(pdf) as doc:
        text = RapidOCREngine().image_to_text(doc[0].get_pixmap(dpi=settings.ocr_dpi).tobytes("png"))
    assert "BUFFER" in text.upper()
    assert "CAPITAL BUFFER" in text.upper()  # word spacing kept
