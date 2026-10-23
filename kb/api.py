"""FastAPI app. Routes live in kb/routes/index.py (Track A) and kb/routes/query.py (Track B)."""
import importlib
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kb.errors import KBError

log = logging.getLogger("kb.api")
app = FastAPI(title="Smart Knowledge Base", docs_url=None, redoc_url=None, openapi_url=None)


def new_request_id() -> str:
    return "req_" + uuid.uuid4().hex[:12]


@app.exception_handler(KBError)
async def _kb_error(request: Request, exc: KBError):
    return JSONResponse(status_code=exc.http_status, content=exc.to_body(new_request_id()))


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    err = KBError("INVALID_REQUEST", "Request fields are missing or malformed.", 422,
                  details={"errors": [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]})
    return JSONResponse(status_code=422, content=err.to_body(new_request_id()))


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception):
    log.exception("unhandled error")
    err = KBError("INTERNAL_ERROR", "Internal error.", 500, retryable=True)
    return JSONResponse(status_code=500, content=err.to_body(new_request_id()))


for _module in ("kb.routes.index", "kb.routes.query"):
    app.include_router(importlib.import_module(_module).router)
