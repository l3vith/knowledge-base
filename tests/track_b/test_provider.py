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


def test_raw_failure_diagnostics_and_reservation_release(tmp_path,monkeypatch):
    body={"usage":{"prompt_tokens":31,"completion_tokens":23},
          "choices":[{"finish_reason":"length","message":{"content":None}}]}
    monkeypatch.setattr("kb.query.provider.httpx.Client",lambda **kwargs:Client(body))
    runtime=QueryRuntime(settings(tmp_path),OpenCodeJSONClient(model="test-model",key="test-key"),LocalSink())
    with pytest.raises(QueryError):
        runtime.call("verify","system",{},500)
    raw=json.loads((runtime.path/'call_1_raw_response.json').read_text(encoding='utf-8'))
    assert raw=={'content':None,'finish_reason':'length','output_limit':500}
    assert runtime.reserved_output==23
    assert runtime.usage()['output_tokens']==23


def test_shared_query_client_preserves_cache_spend_and_one_attempt(tmp_path,monkeypatch):
    from kb.config import get_settings
    from kb.llm import OpenCodeLLM, spent_usd
    from kb.query.provider import SharedQueryClient
    calls=[]
    class SharedResponse:
        status_code=200
        def raise_for_status(self): pass
        def json(self):
            return {'usage':{'prompt_tokens':31,'completion_tokens':23},
                    'choices':[{'finish_reason':'length','message':{'content':None}}]}
    def post(*args,**kwargs):
        calls.append(kwargs)
        return SharedResponse()
    monkeypatch.setattr('kb.llm.requests.post',post)
    shared=get_settings(data_dir=tmp_path/'data',llm_cache=False,llm_max_retries=3,
                        opencode_api_key='fake',price_input_per_m=0.3,price_output_per_m=1.2)
    client=SharedQueryClient(OpenCodeLLM(shared)).scoped()
    runtime=QueryRuntime(settings(tmp_path),client,LocalSink())
    with pytest.raises(QueryError,match='invalid or truncated'):
        runtime.call('verify','system',{},500)
    assert len(calls)==1
    assert calls[0]['json']['reasoning_effort']=='low'
    assert runtime.usage()['input_tokens']==31
    assert spent_usd(shared)>0
    assert runtime.events[0]['response_artifact']=='call_1_raw_response'


def test_shared_dryrun_understands_compact_spans(tmp_path):
    from kb.config import get_settings
    from kb.llm import get_llm
    from kb.query.provider import SharedQueryClient
    client=SharedQueryClient(get_llm(get_settings(data_dir=tmp_path,llm_mode='dryrun'))).scoped()
    out=client.complete_json('system',json.dumps({'query':'capital ratio','aspects':'a1: capital ratio',
        'elements':[{'id':'E1','source_spans':{'S1':'The capital ratio is 15 percent.'}}]}),name='verify',max_tokens=500)
    assert out['keep'][0]['support_span_ids']==['S1']
