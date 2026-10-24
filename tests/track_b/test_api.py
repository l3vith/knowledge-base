from fastapi.testclient import TestClient
from kb.query.demo_app import create_query_app
from kb.routes.query import BoundServices
from kb.query.observability import LocalSink
from kb.query.errors import QueryError
from .helpers import MemoryStore,FakeLLM,settings


def client(tmp_path):
    def binder(name):
        if name!="demo": raise QueryError("COLLECTION_NOT_FOUND","Missing",404)
        return BoundServices(MemoryStore({"a":["Capital ratio is 14 percent."]}),"g1",settings(tmp_path),FakeLLM(),sink=LocalSink())
    return TestClient(create_query_app(binder))


def test_query_http_and_no_extra_routes(tmp_path):
    c=client(tmp_path)
    response=c.post("/query",json={"collection_name":"demo","query":"capital ratio"})
    body=response.json()
    assert response.status_code==200 and set(body)=={"answer","chunks","trace"}
    assert len(body["trace"])==10
    assert all(set(step)=={"step_name","description","input","output"} for step in body["trace"])
    assert all(set(chunk)=={"content","metadata"} and
               set(chunk["metadata"])=={"file_name","page_numbers"} for chunk in body["chunks"])
    assert c.get("/docs").status_code==c.get("/openapi.json").status_code==c.get("/health").status_code==404


def test_missing_and_invalid_inputs(tmp_path):
    c=client(tmp_path)
    missing=c.post("/query",json={"collection_name":"missing","query":"capital"})
    assert missing.status_code==404 and missing.json()=={"detail":"unknown collection"}
    for body in [{"collection_name":"../bad","query":"capital"},{"collection_name":"demo","query":"  "},
                 {"collection_name":"demo","query":True}]:
        assert c.post("/query",json=body).status_code==422
    assert c.post("/query",json={"collection_name":"demo","query":"capital","ignored":"field"}).status_code==200


def test_contract_response_returns_only_cited_source_evidence():
    from kb.routes.query import _contract_response
    body=_contract_response({"answer":"Grounded answer", "chunks":[
        {"content":"Cited passage", "document":"folder/report.pdf", "page":3,"cited_by_claim_ids":["c1"]},
        {"content":"Uncited passage", "document":"report.pdf", "page":4,"cited_by_claim_ids":[]},
    ],"trace":[{"step_name":"rerank","description":"Ranked candidates","input":3,"output":1,"private":"drop"}]})
    assert body=={"answer":"Grounded answer","chunks":[{"content":"Cited passage","metadata":{"file_name":"report.pdf","page_numbers":[3]}}],
                 "trace":[{"step_name":"rerank","description":"Ranked candidates","input":3,"output":1}]}


def test_unintegrated_harness_is_explicit_not_fake_index():
    app=create_query_app()
    with TestClient(app) as c:
        assert c.post("/index").status_code==404
        assert c.get("/health").status_code==404
        assert c.post("/query",json={}).status_code==422
