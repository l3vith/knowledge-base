"""POST /index: upload a zip, build and promote a new generation of the collection (blocking).

Ingestion modules (parser, OCR, layout) are imported lazily inside the handler so a query-only process
(e.g. a 512 MB free-tier host) never loads them.
"""
import logging
import os
import tempfile

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from kb.config import get_settings
from kb.errors import KBError
from kb.llm import get_llm

log = logging.getLogger("kb.routes.index")
router = APIRouter()


def get_embedder(settings):
    from kb.embed import get_embedder as _get
    return _get(settings)


def _index(*args, **kwargs):
    from kb.ingest.pipeline import index_collection
    return index_collection(*args, **kwargs)


@router.post("/index")
async def index_endpoint(file: UploadFile = File(...), collection_name: str = Form(...)):
    settings = get_settings()
    fd, tmp = tempfile.mkstemp(suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(1 << 20):
                out.write(chunk)
        try:
            return await run_in_threadpool(_index, tmp, collection_name, settings=settings,
                                           llm=get_llm(settings), embedder=get_embedder(settings))
        except KBError:
            raise
        except Exception as e:
            log.exception("indexing failed")
            raise KBError("INDEXING_FAILED", f"Indexing failed: {type(e).__name__}", 500, retryable=True)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
