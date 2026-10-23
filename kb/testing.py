"""Test doubles shared by every module: synthetic PDFs, deterministic embedder/reranker, in-memory store."""
import hashlib
from pathlib import Path

import numpy as np

from kb.models import BLANK_PAGE_SUMMARY, DocCard, Element, Embedder, PageCard
from kb.textutil import tokens


def make_pdf(path: Path, pages: list[str], toc: list[list] | None = None,
             image_only_pages: set[int] = frozenset()) -> Path:
    """Write a PDF. Pages whose 0-based index is in image_only_pages carry the text only as an image (no text layer)."""
    import pymupdf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    for i, text in enumerate(pages):
        page = doc.new_page()
        if i in image_only_pages:
            scratch = pymupdf.open()
            sp = scratch.new_page()
            sp.insert_text((72, 72), text, fontsize=14)
            pix = sp.get_pixmap(dpi=150)
            page.insert_image(page.rect, stream=pix.tobytes("png"))
            scratch.close()
        else:
            y = 72
            for line in text.split("\n"):
                page.insert_text((72, y), line, fontsize=11)
                y += 14
    if toc:
        doc.set_toc(toc)
    doc.save(str(path))
    doc.close()
    return path


class HashEmbedder:
    """Deterministic bag-of-tokens embedding (md5-hashed buckets), L2-normalised."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in tokens(text):
                out[i, int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class FakeReranker:
    def score(self, query: str, texts: list[str]) -> list[float]:
        q = set(tokens(query))
        return [len(q & set(tokens(t))) / max(1, len(q)) for t in texts]


class MemoryStore:
    """Pure-python StoreProtocol implementation for tests. Lexical score = number of query tokens present."""

    def __init__(self, cards: list[DocCard], page_texts: dict[tuple[str, int], str], page_cards: list[PageCard],
                 elements: list[Element], embedder: Embedder | None = None):
        self._cards = {c.doc_id: c for c in cards}
        self._order = [c.doc_id for c in cards]
        self._page_texts = dict(page_texts)
        self._page_cards = {(pc.doc_id, pc.page_no): pc for pc in page_cards}
        self._elements = sorted(elements, key=lambda e: (self._order.index(e.doc_id), e.page_no, e.idx))
        self._by_id = {e.element_id: e for e in self._elements}
        self._embedder = embedder or HashEmbedder()
        self._page_keys = sorted(self._page_texts, key=lambda k: (self._order.index(k[0]), k[1]))
        self._page_vecs = self._embedder.embed([self._page_body(k) for k in self._page_keys]) if self._page_keys else None
        self._el_vecs = self._embedder.embed([e.text for e in self._elements]) if self._elements else None

    def _page_body(self, key) -> str:
        pc = self._page_cards.get(key)
        extra = f"\n{pc.summary} {' '.join(pc.topics)} {' '.join(pc.figures)}" if pc else ""
        return self._page_texts[key] + extra

    def docs(self) -> list[DocCard]:
        return [self._cards[d] for d in self._order]

    def doc(self, doc_id: str) -> DocCard:
        return self._cards[doc_id]

    def page_cards(self, doc_id: str, page_nos: list[int] | None = None) -> list[PageCard]:
        out = [pc for (d, p), pc in self._page_cards.items() if d == doc_id and (page_nos is None or p in page_nos)]
        return sorted(out, key=lambda pc: pc.page_no)

    def nonblank_pages(self, doc_id: str) -> list[int]:
        return [pc.page_no for pc in self.page_cards(doc_id) if pc.summary != BLANK_PAGE_SUMMARY]

    def elements_for_pages(self, doc_id: str, page_nos: list[int], include_boilerplate: bool = False) -> list[Element]:
        wanted = set(page_nos)
        return [e for e in self._elements if e.doc_id == doc_id and e.page_no in wanted
                and (include_boilerplate or "boilerplate" not in e.flags)]

    def elements_by_ids(self, element_ids: list[str]) -> list[Element]:
        return [self._by_id[i] for i in element_ids if i in self._by_id]

    @staticmethod
    def _lex(terms: list[str], text: str) -> float:
        q = tokens(" ".join(terms))
        have = set(tokens(text))
        return float(sum(1 for t in q if t in have))

    def search_pages(self, terms, doc_ids, limit):
        hits = [(d, p, self._lex(terms, self._page_body((d, p)))) for d, p in self._page_keys
                if doc_ids is None or d in doc_ids]
        hits = [h for h in hits if h[2] > 0]
        return sorted(hits, key=lambda h: -h[2])[:limit]

    def dense_pages(self, query_vecs, doc_ids, limit):
        if self._page_vecs is None:
            return []
        rows = [i for i, (d, _) in enumerate(self._page_keys) if doc_ids is None or d in doc_ids]
        if not rows:
            return []
        scores = (self._page_vecs[rows] @ np.asarray(query_vecs).T).max(axis=1)
        order = np.argsort(-scores)[:limit]
        return [(*self._page_keys[rows[i]], float(scores[i])) for i in order]

    def search_elements(self, terms, doc_ids, limit):
        hits = [(e.element_id, self._lex(terms, f"{e.section} {e.text}")) for e in self._elements
                if (doc_ids is None or e.doc_id in doc_ids) and "boilerplate" not in e.flags]
        hits = [h for h in hits if h[1] > 0]
        return sorted(hits, key=lambda h: -h[1])[:limit]

    def dense_elements(self, query_vecs, doc_ids, limit):
        if self._el_vecs is None:
            return []
        rows = [i for i, e in enumerate(self._elements)
                if (doc_ids is None or e.doc_id in doc_ids) and "boilerplate" not in e.flags]
        if not rows:
            return []
        scores = (self._el_vecs[rows] @ np.asarray(query_vecs).T).max(axis=1)
        order = np.argsort(-scores)[:limit]
        return [(self._elements[rows[i]].element_id, float(scores[i])) for i in order]


def memory_store_from_texts(docs: dict[str, list[str]], card_overrides: dict[str, dict] | None = None) -> MemoryStore:
    card_overrides = card_overrides or {}
    cards, page_texts, page_cards, elements = [], {}, [], []
    for doc_id, pages in docs.items():
        fields = dict(doc_id=doc_id, file_name=f"{doc_id}.pdf", title=doc_id, doc_type="other", issuer=doc_id,
                      entities=[], period_label="", period_year=None, publication_date=None, jurisdiction="",
                      topics=[], summary="", page_count=len(pages))
        fields.update(card_overrides.get(doc_id, {}))
        cards.append(DocCard(**fields))
        for page_no, text in enumerate(pages, start=1):
            page_texts[(doc_id, page_no)] = text
            summary = text[:200] if text.strip() else BLANK_PAGE_SUMMARY
            page_cards.append(PageCard(doc_id, page_no, "", summary, [], [], []))
            blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
            for idx, block in enumerate(blocks):
                elements.append(Element(f"{doc_id}:p{page_no:04d}:e{idx:03d}", doc_id, page_no, idx, "text", "", block))
    return MemoryStore(cards, page_texts, page_cards, elements)
