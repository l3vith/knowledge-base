"""POST /query only. Person 1's app mounts this router; no competing /index."""
from dataclasses import dataclass
import re
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from kb.query.errors import QueryError
from kb.query.pipeline import answer_query

router=APIRouter()
COLLECTION_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class QueryIn(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    collection_name: str=Field(min_length=1,max_length=64)
    query: str=Field(min_length=1,max_length=32000)


@dataclass
class BoundServices:
    store: object
    generation_id: str
    settings: object
    llm: object
    embedder: object=None
    reranker: object=None
    sink: object=None
    close_store: bool=False


def legacy_bind(collection_name):
    """Lazy compatibility seam for the original M0/M3; no import at module load."""
    try:
        from kb.config import get_settings
        from kb.registry import Registry
        from kb.store import Store
        from kb.embed import get_embedder, get_reranker
    except ImportError as exc:
        raise QueryError("COLLECTION_NOT_READY","Person 1 storage/foundation must be integrated or app.state.query_services configured",503) from exc
    settings=get_settings()
    generation,directory=Registry(settings).active_dir(collection_name)
    from kb.llm import get_llm
    from kb.query.settings import SharedQuerySettings
    # Shared client: KB_BUDGET_USD cap + spend ledger, disk response cache and KB_LLM_MODE=dryrun apply to queries too.
    llm=get_llm(settings)
    store=Store.open(directory)
    try:
        return BoundServices(store,generation,SharedQuerySettings(settings),llm,get_embedder(settings),get_reranker(settings),close_store=True)
    except BaseException:
        store.close()
        raise


def bind_services(request,collection_name):
    binder=getattr(request.app.state,"query_services",None)
    return binder(collection_name) if callable(binder) else legacy_bind(collection_name)


@router.post("/query")
async def query_route(body: QueryIn,request: Request):
    import uuid
    request_id="req_"+uuid.uuid4().hex
    if not COLLECTION_RE.fullmatch(body.collection_name) or not body.query.strip():
        error=QueryError("INVALID_REQUEST","Invalid collection name or empty query",422)
        return JSONResponse(status_code=422,content=error.to_body(request_id))
    def run():
        services=bind_services(request,body.collection_name)
        try:
            return answer_query(body.collection_name,body.query,store=services.store,generation_id=services.generation_id,
                        settings=services.settings,llm=services.llm,embedder=services.embedder,reranker=services.reranker,
                        sink=services.sink,request_id=request_id)
        finally:
            if services.close_store:
                services.store.close()
    try:
        return await run_in_threadpool(run)
    except QueryError as exc:
        return JSONResponse(status_code=exc.http_status,content=exc.to_body(request_id))
    except Exception as exc:
        # Accept Person 1 typed errors structurally without importing its module.
        if hasattr(exc,"http_status") and callable(getattr(exc,"to_body",None)):
            return JSONResponse(status_code=exc.http_status,content=exc.to_body(request_id))
        from kb.llm import LLMError
        if isinstance(exc,LLMError):  # provider down, retries exhausted or spend cap reached
            error=QueryError("PROVIDER_UNAVAILABLE",f"Model unavailable: {exc}",503,True)
            return JSONResponse(status_code=503,content=error.to_body(request_id))
        error=QueryError("QUERY_FAILED","Query failed; inspect private request artifacts",500)
        return JSONResponse(status_code=500,content=error.to_body(request_id))
