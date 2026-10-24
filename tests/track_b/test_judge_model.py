import pytest
from evaluation.official import load_notebook_namespace,OfficialJudgeTransport
from kb.model_api import REQUIRED_MODEL


def test_judge_override_does_not_change_answer_model(monkeypatch):
    from pathlib import Path
    path=Path(__file__).resolve().parents[3]/'Train/Evaluation/Evaluation.ipynb'
    if not path.exists():pytest.skip('external organizer notebook unavailable')
    monkeypatch.setenv('OPENCODE_JUDGE_MODEL','glm-5.3-flash')
    monkeypatch.setenv('OPENCODE_MODEL','qwen3.8-flash')
    ns=load_notebook_namespace(path)
    assert ns['OPENCODE_MODEL']=='glm-5.3-flash' and REQUIRED_MODEL=='qwen3.8-flash'


def test_glm_judge_uses_flash_prices_low_effort_and_no_escalation(monkeypatch,tmp_path):
    from kb.config import get_settings
    from kb.llm import spent_usd
    settings=get_settings(data_dir=tmp_path/'data',budget_usd=1)
    monkeypatch.setattr('kb.config.get_settings',lambda:settings)
    monkeypatch.setenv('JUDGE_REASONING_EFFORT','low')
    monkeypatch.delenv('JUDGE_PRICE_INPUT_PER_M',raising=False)
    monkeypatch.delenv('JUDGE_PRICE_OUTPUT_PER_M',raising=False)
    seen=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'finish_reason':'length','message':{'content':None}}],
            'usage':{'prompt_tokens':100,'completion_tokens':1000}}
    def post(*args,**kw):seen.append(kw['json']);return Response()
    monkeypatch.setattr('requests.post',post)
    client=OfficialJudgeTransport('fake','glm-5.3-flash','https://example.invalid')
    assert client.prices==(.15,.5) and client.client is None
    with pytest.raises(RuntimeError,match='no content'):
        client.call_structured('system','source',max_tokens=4000,max_retries=3)
    assert len(seen)==1 and seen[0]['reasoning_effort']=='low' and seen[0]['model']=='glm-5.3-flash'
    assert client.over_notebook_limit==0 and spent_usd(settings)>0
