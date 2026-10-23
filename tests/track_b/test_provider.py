import json
import pytest
from kb.query.provider import OpenCodeJSONClient
from kb.query.runtime import QueryRuntime
from kb.query.observability import LocalSink
from kb.query.errors import QueryError
from .helpers import settings


class Response:
    def __init__(self,body): self.body=body
    def raise_for_status(self): return None
    def json(self): return self.body


class Client:
    def __init__(self,body): self.body=body
    def __enter__(self): return self
    def __exit__(self,*args): return None
    def post(self,*args,**kwargs): return Response(self.body)


def test_failed_json_still_accounts_billed_usage(tmp_path,monkeypatch):
    body={"usage":{"prompt_tokens":123,"completion_tokens":17},"choices":[{"message":{"content":"prefix {\"x\":1} suffix"}}]}
    monkeypatch.setattr("kb.query.provider.httpx.Client",lambda **kwargs:Client(body))
    runtime=QueryRuntime(settings(tmp_path),OpenCodeJSONClient(model="test-model",key="test-key"),LocalSink())
    with pytest.raises(QueryError,match="invalid JSON"):
        runtime.call("plan","system",{},100)
    assert runtime.usage()["input_tokens"]==123
    assert runtime.usage()["output_tokens"]==17
    assert runtime.usage()["cost_usd"] is None
    assert runtime.events[0]["status"]=="failed"


def test_missing_model_key_is_explicit(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY",raising=False)
    with pytest.raises(QueryError,match="Configure"):
        OpenCodeJSONClient(model="test-model")
