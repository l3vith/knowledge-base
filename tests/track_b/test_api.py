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
    assert response.status_code==200 and len(response.json()["trace"])==10
    assert c.get("/docs").status_code==c.get("/openapi.json").status_code==c.get("/health").status_code==404


def test_missing_and_invalid_inputs(tmp_path):
    c=client(tmp_path)
    assert c.post("/query",json={"collection_name":"missing","query":"capital"}).status_code==404
    for body in [{"collection_name":"../bad","query":"capital"},{"collection_name":"demo","query":"  "},
                 {"collection_name":"demo","query":True},{"collection_name":"demo","query":"x","extra":1}]:
        assert c.post("/query",json=body).status_code==422


def test_unintegrated_harness_is_explicit_not_fake_index():
    app=create_query_app()
    with TestClient(app) as c:
        assert c.post("/index").status_code==404
        assert c.get("/health").status_code==404
        assert c.post("/query",json={}).status_code==422
