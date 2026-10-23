"""PDF -> per-page markdown (pymupdf4llm layout mode) with OCR for image-only pages.

OCR variant (acceptance check on a fully scanned 92-page corpus PDF, pages 1 and 29, mean whitespace-token length):
pymupdf4llm's built-in RapidOCR loses word spaces (p29: 13.4 at 200 dpi, 12.7 at 300 dpi). Our RapidOCREngine
restores spaces from pixel gaps (p29: 5.25 at 200 and 300 dpi). So to_markdown always runs with use_ocr=False
and image-only pages are OCRed here with RapidOCREngine at settings.ocr_dpi.
"""
import hashlib
import logging
import re
from pathlib import Path

import pymupdf
import pymupdf4llm

from kb.config import Settings
from kb.ingest.ocr import get_ocr_engine
from kb.models import PageText, ParsedDoc

log = logging.getLogger(__name__)

_IMAGE_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def doc_id_for(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:10]


def _outline(doc) -> list[tuple[int, str, int]]:
    return [(int(lvl), str(title), int(page)) for lvl, title, page, *_ in doc.get_toc(simple=True) if page >= 1]


def read_pdf_info(path: Path) -> tuple[str, int, list[tuple[int, str, int]], dict]:
    with pymupdf.open(path) as doc:
        return doc_id_for(path), doc.page_count, _outline(doc), dict(doc.metadata or {})


def _clean(md: str) -> str:
    return _IMAGE_LINK.sub("", md or "").strip()


def _markdown(doc, idx: list[int], settings: Settings, name: str, drop_margins: bool) -> dict[int, str]:
    """{1-based page: markdown} for 0-based page indexes idx; plain text if the markdown parser raises."""
    try:
        # Classic markdown by default: the layout AI renders + runs ONNX per page and measured ~3.8x slower
        # under 6 workers (65 vs 162-182 ms/page). header/footer/use_ocr kwargs are ignored by the classic path.
        pymupdf4llm.use_layout(settings.parse_layout)
        chunks = pymupdf4llm.to_markdown(
            doc, pages=idx, page_chunks=True, show_progress=False, write_images=False, embed_images=False,
            use_ocr=False, ocr_dpi=settings.ocr_dpi, header=not drop_margins, footer=not drop_margins)
        # layout mode names the 1-based page "page_number"; classic mode names it "page" (also 1-based, verified)
        return {int(c["metadata"].get("page_number") or c["metadata"]["page"]): c.get("text") or "" for c in chunks}
    except Exception as e:
        log.warning("to_markdown failed for %s (%d pages from p%d): %s; using plain text", name, len(idx), idx[0] + 1, e)
        return {i + 1: doc[i].get_text("text") for i in idx}


def parse_pages(path: Path, start: int, end: int, settings: Settings, use_ocr: bool) -> tuple[list[PageText], int]:
    """Pages start..end inclusive (1-based). Returns (pages, ocr_unavailable_count). Top-level for process pools."""
    path = Path(path)
    pages: list[PageText] = []
    unavailable = 0
    with pymupdf.open(path) as doc:
        end = min(end, doc.page_count)
        if start > end:
            return [], 0
        titles: dict[int, list[str]] = {}
        for _, title, page in _outline(doc):
            titles.setdefault(page, []).append(title)
        md_by_page = _markdown(doc, list(range(start - 1, end)), settings, path.name, drop_margins=True)
        # The layout model can classify a page's only text as running header/footer; never lose a text page.
        lost = [p - 1 for p, md in md_by_page.items()
                if not _clean(md) and len(doc[p - 1].get_text().strip()) >= settings.min_text_chars]
        if lost:
            md_by_page.update(_markdown(doc, lost, settings, path.name, drop_margins=False))

        for page_no in range(start, end + 1):
            page = doc[page_no - 1]
            md = _clean(md_by_page.get(page_no, ""))
            is_ocr = False
            if use_ocr and len(page.get_text().strip()) < settings.min_text_chars and page.get_image_info():
                engine = get_ocr_engine()
                text = ""
                if engine is not None:
                    try:
                        text = _clean(engine.image_to_text(page.get_pixmap(dpi=settings.ocr_dpi).tobytes("png")))
                    except Exception as e:
                        log.warning("OCR failed on %s p%d: %s", path.name, page_no, e)
                if len(text) > len(md):
                    md, is_ocr = text, True
                if not md:
                    unavailable += 1
            pages.append(PageText(page_no=page_no, markdown=md, is_ocr=is_ocr, toc_titles=titles.get(page_no, [])))
    return pages, unavailable


def parse_pdf(path: Path, settings: Settings, use_ocr: bool = True) -> ParsedDoc:
    path = Path(path)
    doc_id, page_count, outline, metadata = read_pdf_info(path)
    pages, unavailable = parse_pages(path, 1, page_count, settings, use_ocr)
    return ParsedDoc(doc_id=doc_id, file_name=path.name, page_count=page_count, pages=pages, outline=outline,
                     pdf_metadata=metadata, ocr_unavailable_pages=unavailable)
