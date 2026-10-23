"""Query-router harness for local integration, not a complete submission API."""
from fastapi import FastAPI
from kb.routes.query import router


def create_query_app(binder=None):
    app=FastAPI(title="Track B integration harness",docs_url=None,redoc_url=None,openapi_url=None)
    if binder is not None:
        app.state.query_services=binder
    app.include_router(router)
    return app


app=create_query_app()
