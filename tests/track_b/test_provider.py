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
    runtime=QueryRuntime(settings(tmp_path),OpenCodeJSONClient(model="qwen3.8-flash",key="test-key"),LocalSink())
    with pytest.raises(QueryError,match="invalid JSON"):
        runtime.call("plan","system",{},100)
    # Exactly one bounded repair attempt is made and both paid responses are accounted.
    assert runtime.usage()["input_tokens"]==246
    assert runtime.usage()["output_tokens"]==34
    assert runtime.usage()["cost_usd"] is None
    assert runtime.events[0]["status"]=="failed"


def test_invalid_json_gets_one_syntax_repair_and_keeps_usage(tmp_path,monkeypatch):
    calls=[]
    bodies=iter([
        {"usage":{"prompt_tokens":20,"completion_tokens":9},"choices":[{"finish_reason":"stop","message":{"content":"{bad json"}}]},
        {"usage":{"prompt_tokens":30,"completion_tokens":11},"choices":[{"finish_reason":"stop","message":{"content":"{\"keep\":[]}"}}]},
    ])
    class CaptureClient(Client):
        def post(self,url,**kwargs):
            calls.append(kwargs["json"])
            return Response(next(bodies))
    monkeypatch.setattr("kb.query.provider.httpx.Client",lambda **kwargs:CaptureClient(None))
    runtime=QueryRuntime(settings(tmp_path),OpenCodeJSONClient(model="qwen3.8-flash",key="test-key"),LocalSink())
    assert runtime.call("verify","system",{},100)=={"keep":[]}
    assert len(calls)==2 and "{bad json" in calls[1]["messages"][0]["content"]
    assert runtime.usage()["input_tokens"]==50 and runtime.usage()["output_tokens"]==20


def test_missing_model_key_is_explicit(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY",raising=False)
    with pytest.raises(QueryError,match="Configure"):
        OpenCodeJSONClient(model="test-model")


def test_raw_failure_diagnostics_and_reservation_release(tmp_path,monkeypatch):
    body={"usage":{"prompt_tokens":31,"completion_tokens":23},
          "choices":[{"finish_reason":"length","message":{"content":None}}]}
    monkeypatch.setattr("kb.query.provider.httpx.Client",lambda **kwargs:Client(body))
    runtime=QueryRuntime(settings(tmp_path),OpenCodeJSONClient(model="qwen3.8-flash",key="test-key"),LocalSink())
    with pytest.raises(QueryError):
        runtime.call("verify","system",{},500)
    raw=json.loads((runtime.path/'call_1_raw_response.json').read_text(encoding='utf-8'))
    assert raw=={'content':None,'finish_reason':'length','output_limit':500}
    assert runtime.reserved_verify==23 and runtime.reserved_output==0
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
                        llm_model="qwen3.8-flash",opencode_api_key='fake',price_input_per_m=0.15,price_output_per_m=0.47)
    client=SharedQueryClient(OpenCodeLLM(shared)).scoped()
    runtime=QueryRuntime(settings(tmp_path),client,LocalSink())
    with pytest.raises(QueryError,match='invalid or truncated'):
        runtime.call('verify','system',{},500)
    assert len(calls)==1
    assert calls[0]['json']['thinking']=={'type':'disabled'} and calls[0]['json']['model']=='qwen3.8-flash'
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


def test_qwen_uses_messages_without_reasoning_and_accounts_usage(tmp_path,monkeypatch):
    calls=[]
    body={'content':[{'type':'text','text':'{"keep":[]}'}],'stop_reason':'end_turn',
          'usage':{'input_tokens':30,'output_tokens':7,'cache_read_input_tokens':10}}
    class CaptureClient(Client):
        def post(self,url,**kwargs):
            calls.append((url,kwargs))
            return Response(self.body)
    monkeypatch.setattr('kb.query.provider.httpx.Client',lambda **kwargs:CaptureClient(body))
    llm=OpenCodeJSONClient(model='qwen3.8-flash',key='test',base_url='https://opencode.ai/inference/openai/v1/chat/completions')
    runtime=QueryRuntime(settings(tmp_path),llm,LocalSink())
    assert runtime.call('verify','Select exact spans',{},512)=={'keep':[]}
    url,kw=calls[0]
    assert url=='https://opencode.ai/inference/anthropic/v1/messages'
    assert kw['json']['thinking']=={'type':'disabled'}
    assert kw['json']['max_tokens']==512
    assert 'reasoning_effort' not in kw['json'] and 'response_format' not in kw['json']
    assert kw['headers']['anthropic-version']=='2023-06-01'
    assert runtime.usage()['input_tokens']==40 and runtime.usage()['output_tokens']==7


def test_shared_qwen_wire_format_and_zero_cost_cache(tmp_path,monkeypatch):
    from kb.config import get_settings
    from kb.llm import OpenCodeLLM
    seen=[]
    class Resp:
        status_code=200
        def raise_for_status(self): pass
        def json(self):
            return {'content':[{'type':'text','text':'{"ok":true}'}],'stop_reason':'end_turn',
                    'usage':{'input_tokens':12,'output_tokens':5}}
    def post(url,**kwargs):
        seen.append((url,kwargs))
        return Resp()
    monkeypatch.setattr('kb.llm.requests.post',post)
    s=get_settings(data_dir=tmp_path,llm_model='qwen3.8-flash',price_input_per_m=.15,price_output_per_m=.47)
    first=OpenCodeLLM(s)
    assert first.complete_json('system','user',name='verify',max_tokens=512)=={'ok':True}
    assert first.last_usage['cost_usd']==pytest.approx((12*.15+5*.47)/1e6)
    second=OpenCodeLLM(s)
    assert second.complete_json('system','user',name='verify',max_tokens=512)=={'ok':True}
    assert second.last_usage['cost_usd']==0 and len(seen)==1
    assert seen[0][1]['json']['thinking']=={'type':'disabled'}


def test_answer_stage_has_its_own_pool(tmp_path):
    # Early stages using their whole output pool cannot starve the writers or claim checks, and the answer pool
    # still has a hard bound.
    from .helpers import FakeLLM
    from kb.query.errors import BudgetExceeded
    runtime=QueryRuntime(settings(tmp_path,max_output_tokens=24000,answer_pool_output_tokens=10000),FakeLLM(lambda n,p:{'ok':1}),LocalSink())
    runtime.reserved_output=24000
    runtime.call('answer','system',{},4000)
    runtime.call('answer_verify','system',{'claims':[]},2000)
    runtime.reserved_final=8001
    with pytest.raises(BudgetExceeded,match='Answer output'):
        runtime.call('answer','system',{},2000)
    assert runtime.calls==2


def test_reasoning_floor_included_in_all_future_reserves(tmp_path):
    from .helpers import FakeLLM
    from kb.query.errors import BudgetExceeded
    llm=FakeLLM()
    runtime=QueryRuntime(settings(tmp_path,max_output_tokens=24000),llm,LocalSink())
    runtime.llm.model='deepseek-v4.1-flash'
    runtime.reserved_output=20000  # 512 becomes the 4,096 reasoning floor: 24,096 > 24,000
    with pytest.raises(BudgetExceeded,match='Output reservation'):
        runtime.call('survey','system',{},512)
    assert runtime.calls==0


def test_verification_has_its_own_output_pool(tmp_path):
    # A concurrent verify round must not be cut by the answer's reserve: 20 batches of 2,000 fit the verify pool.
    from .helpers import FakeLLM
    runtime=QueryRuntime(settings(tmp_path,max_llm_calls=40),FakeLLM(lambda n,p:{"keep":[]}),LocalSink())
    out=runtime.call_many('verify','system',[{"i":i} for i in range(20)],2000)
    assert not any(isinstance(r,Exception) for r in out) and runtime.reserved_output==0
