"""OCR for image-only PDF pages (RapidOCR, ONNX, CPU-only).

RapidOCR's recogniser (PP-OCRv4) often drops the spaces between English words on tightly set scans
("SaudiArabianMonetaryAuthority"). We restore them from the page pixels: inside each detected line,
blank pixel columns wider than a quarter of the ink height are word gaps; each gap becomes a space at
the nearest character boundary (character positions come from RapidOCR's return_word_box).
"""
import functools
import logging
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)

WORD_GAP_FRAC = 0.25  # blank run >= this x ink height (and >= 2x the line's median gap) = word space


class OCREngine(Protocol):
    def image_to_text(self, png_bytes: bytes) -> str: ...


def _word_gaps(bw: np.ndarray, box) -> list[float]:
    """Centres (page x) of word-sized blank column runs inside one line box of a binary ink image."""
    pts = np.asarray(box, dtype=float)
    x0, y0 = np.floor(pts.min(0)).astype(int)
    x1, y1 = np.ceil(pts.max(0)).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0)
    crop = bw[y0:y1, x0:x1]
    if crop.size == 0:
        return []
    rows = np.flatnonzero(crop.any(1))
    ink = np.flatnonzero(crop.any(0))
    if len(rows) == 0 or len(ink) < 2:
        return []
    height = rows[-1] - rows[0] + 1
    blank = ~crop.any(0)[ink[0]:ink[-1] + 1]
    runs, start = [], None
    for x, b in enumerate(blank):
        if b and start is None:
            start = x
        elif not b and start is not None:
            runs.append((start, x - start))
            start = None
    if not runs:
        return []
    thr = max(WORD_GAP_FRAC * height, 2.0 * float(np.median([w for _, w in runs])))
    return [x0 + ink[0] + s + w / 2 for s, w in runs if w >= thr]


def _respace(text: str, chars: list, char_boxes: list, gaps: list[float]) -> str:
    """Insert a space at the character boundary nearest each word gap."""
    if not gaps or len(chars) < 2 or len(chars) != len(char_boxes):
        return text
    xs = [(min(p[0] for p in b), max(p[0] for p in b)) for b in char_boxes]
    order = sorted(range(len(chars)), key=lambda i: xs[i][0])
    chars = [str(chars[i]) for i in order]
    xs = [xs[i] for i in order]
    bounds = [(xs[i][1] + xs[i + 1][0]) / 2 for i in range(len(xs) - 1)]
    split = {int(np.argmin([abs(b - g) for b in bounds])) for g in gaps}
    out = []
    for i, c in enumerate(chars):
        out.append(c)
        if i in split and c != " " and i + 1 < len(chars) and chars[i + 1] != " ":
            out.append(" ")
    return "".join(out)


class RapidOCREngine:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()

    def image_to_text(self, png_bytes: bytes) -> str:
        import cv2

        result, _ = self._ocr(png_bytes, return_word_box=True)
        if not result:
            return ""
        gray = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        bw = None
        if gray is not None:
            _, bw = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            bw = bw.astype(bool)
        lines = []
        # item: [box (4 points, top-left first), text, score, char_boxes, chars, char_scores]
        for item in sorted(result, key=lambda r: (round(r[0][0][1] / 10), r[0][0][0])):
            text = str(item[1])
            if bw is not None and len(item) >= 5:
                try:
                    text = _respace(text, list(item[4]), list(item[3]), _word_gaps(bw, item[0]))
                except Exception:  # space recovery is best-effort; keep the raw line
                    pass
            text = " ".join(text.split())
            if text:
                lines.append(text)
        return "\n".join(lines)


@functools.lru_cache(maxsize=1)
def get_ocr_engine() -> OCREngine | None:
    """One engine per process; None (with one warning) when RapidOCR cannot load."""
    try:
        return RapidOCREngine()
    except Exception as e:  # import or model-init failure
        log.warning("OCR unavailable: %s", e)
        return None
