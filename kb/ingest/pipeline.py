"""ZIP -> validated generation: extract, parse (page-parallel), segment, cards, embed, store, promote."""
import json
import logging
import os
import re
import shutil
import stat
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path, PurePosixPath

import numpy as np

from kb.config import Settings
from kb.errors import KBError
from kb.ingest.cards import (assign_sibling_groups, augment_topics, build_doc_card, build_page_cards,
                             element_embedding_text, page_embedding_text)
from kb.ingest.parse import parse_pages, read_pdf_info
from kb.ingest.segment import mark_boilerplate, segment_document
from kb.llm import LLM, parallel_map
from kb.models import BLANK_PAGE_SUMMARY, Embedder, ParsedDoc
from kb.registry import Registry
from kb.store import Store

log = logging.getLogger("kb.ingest")
COLLECTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
EMBED_CHUNK = 512


def _unsafe(name: str) -> bool:
    if "\x00" in name or name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
        return True
    return ".." in PurePosixPath(name.replace("\\", "/")).parts


def safe_extract(zip_path: Path, dest: Path, settings: Settings) -> tuple[list[tuple[Path, str]], list[str]]:
    """Extract PDFs only. Returns ([(path, display_name)], warnings). Unsafe archives are rejected whole."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as e:
        raise KBError("INVALID_ARCHIVE", f"Not a readable zip file: {e}", 400)
    with zf:
        infos = zf.infolist()
        for info in infos:
            is_link = stat.S_ISLNK(info.external_attr >> 16)
            if _unsafe(info.filename) or is_link or info.flag_bits & 0x1:
                raise KBError("INVALID_ARCHIVE", "Archive contains an unsafe, linked or encrypted member.", 400,
                              details={"member": info.filename[:200]})
        if sum(i.file_size for i in infos) > settings.max_archive_bytes:
            raise KBError("ARCHIVE_TOO_LARGE", "Archive exceeds the uncompressed size limit.", 413,
                          details={"limit_bytes": settings.max_archive_bytes})
        warnings, pdfs = [], []
        for info in infos:
            name = info.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if info.is_dir() or not parts:
                continue
            if parts[0] == "__MACOSX" or parts[-1].startswith("."):
                continue
            if not name.lower().endswith(".pdf"):
                warnings.append(f"skipped non-PDF file: {name}")
                continue
            pdfs.append((info, name))
        if not pdfs:
            raise KBError("NO_DOCUMENTS", "The archive contains no PDF files.", 400)
        basenames = [PurePosixPath(n).name for _, n in pdfs]
        out = []
        dest.mkdir(parents=True, exist_ok=True)
        for i, (info, name) in enumerate(sorted(pdfs, key=lambda x: x[1])):
            base = PurePosixPath(name).name
            display = base if basenames.count(base) == 1 else name
            target = dest / f"{i:05d}.pdf"
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            out.append((target, display))
        return out, warnings


def _workers(settings: Settings) -> int:
    return settings.parse_workers or min(6, max(1, (os.cpu_count() or 2) // 2))


def _parse_all(files: list[tuple[Path, str]], settings: Settings, use_ocr: bool) -> list[ParsedDoc]:
    infos = [(path, display, *read_pdf_info(path)) for path, display in files]
    jobs = [(i, start, min(start + settings.page_job_size - 1, count))
            for i, (_, _, _, count, _, _) in enumerate(infos) for start in range(1, count + 1, settings.page_job_size)]
    workers = _workers(settings)
    if workers <= 1 or len(jobs) <= 1:
        results = [parse_pages(infos[i][0], s, e, settings, use_ocr) for i, s, e in jobs]
    else:
        # ponytail: each worker's onnxruntime may use all cores during OCR; fine for <200 OCR pages, cap workers if CPU-bound
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(parse_pages, infos[i][0], s, e, settings, use_ocr) for i, s, e in jobs]
            results = [f.result() for f in futures]
    docs = [ParsedDoc(doc_id, display, count, [], outline, meta) for _, display, doc_id, count, outline, meta in infos]
    for (i, _, _), (pages, unavailable) in zip(jobs, results):
        docs[i].pages.extend(pages)
        docs[i].ocr_unavailable_pages += unavailable
    for d in docs:
        d.pages.sort(key=lambda p: p.page_no)
    return docs


def _embed(embedder: Embedder, texts: list[str]) -> np.ndarray:
    parts = [embedder.embed(texts[i:i + EMBED_CHUNK]) for i in range(0, len(texts), EMBED_CHUNK)]
    return np.vstack(parts) if parts else np.zeros((0, 1), dtype=np.float32)


def index_collection(zip_path: Path, collection_name: str, *, settings: Settings, llm: LLM, embedder: Embedder,
                     use_ocr: bool = True, registry: Registry | None = None) -> dict:
    if not COLLECTION_RE.match(collection_name or ""):
        raise KBError("INVALID_COLLECTION_NAME", "collection_name must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", 422,
                      details={"collection_name": (collection_name or "")[:100]})
    registry = registry or Registry(settings)
    llm = llm.scoped()
    t0 = time.perf_counter()

    def stage(name: str, **counts) -> None:
        log.info("[%s] %s %s (%.1fs)", collection_name, name, counts, time.perf_counter() - t0)

    with registry.indexing_lock(collection_name):
        gen_id, staging = registry.new_staging(collection_name)
        try:
            files, warnings = safe_extract(Path(zip_path), staging / "src", settings)
            stage("extracted", pdfs=len(files))

            docs, seen = [], {}
            for d in _parse_all(files, settings, use_ocr):
                if d.doc_id in seen:
                    warnings.append(f"{d.file_name}: duplicate of {seen[d.doc_id]}")
                    continue
                seen[d.doc_id] = d.file_name
                docs.append(d)
            stage("parsed", documents=len(docs), pages=sum(d.page_count for d in docs))

            segmented = []
            for d in docs:
                elements, sections = segment_document(d)
                mark_boilerplate(elements, d.page_count, settings)
                segmented.append((elements, sections))
            stage("segmented", elements=sum(len(e) for e, _ in segmented))

            cards = parallel_map(lambda d: build_doc_card(llm, d, settings), docs, settings.llm_concurrency)
            cards = assign_sibling_groups(cards)
            stage("doc_cards")

            page_cards = parallel_map(lambda i: build_page_cards(llm, docs[i], cards[i], segmented[i][1], settings),
                                      list(range(len(docs))), max(1, settings.llm_concurrency // 2))
            for pcs in page_cards:
                if isinstance(pcs, Exception):  # build_page_cards never raises; keep the guard explicit
                    raise pcs
            cards = [augment_topics(c, pcs) for c, pcs in zip(cards, page_cards)]
            stage("page_cards", llm_calls=llm.usage.calls)

            page_keys, page_texts = [], []
            for c, pcs in zip(cards, page_cards):
                for pc in pcs:
                    if pc.summary != BLANK_PAGE_SUMMARY:
                        page_keys.append((c.doc_id, pc.page_no))
                        page_texts.append(page_embedding_text(c, pc, settings.embed_max_chars))
            page_vecs = _embed(embedder, page_texts)
            el_keys, el_vecs = [], None
            if settings.embed_elements:
                el_texts = []
                for c, (elements, _) in zip(cards, segmented):
                    for e in elements:
                        if "boilerplate" not in e.flags:
                            el_keys.append(e.element_id)
                            el_texts.append(element_embedding_text(c, e, settings.embed_max_chars))
                el_vecs = _embed(embedder, el_texts)
            stage("embedded", pages=len(page_keys), elements=len(el_keys))

            store = Store.create(staging)
            try:
                for d, c, pcs, (elements, _) in zip(docs, cards, page_cards, segmented):
                    store.add_document(c, d.pages, pcs, elements)
                if page_keys:
                    store.set_vectors("page", page_keys, page_vecs)
                if el_keys:
                    store.set_vectors("element", el_keys, el_vecs)
            finally:
                store.close()

            summary = {
                "status": "ready", "collection_name": collection_name, "generation_id": gen_id,
                "documents": len(docs), "pages": sum(d.page_count for d in docs),
                "elements": sum(len(e) for e, _ in segmented),
                "ocr_pages": sum(p.is_ocr for d in docs for p in d.pages),
                "ocr_unavailable_pages": sum(d.ocr_unavailable_pages for d in docs),
                "warnings": warnings, "llm_usage": asdict(llm.usage),
                "ingestion_seconds": round(time.perf_counter() - t0, 2),
            }
            (staging / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            shutil.rmtree(staging / "src", ignore_errors=True)
            registry.promote(collection_name, gen_id, staging)
            stage("promoted", generation_id=gen_id)
            return summary
        except BaseException:
            registry.discard(staging)
            raise
