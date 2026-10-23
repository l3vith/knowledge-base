import hashlib
import json
from pathlib import Path
import pytest
from evaluation.runner import flatten_gold_chunks,select_rows,capture
from evaluation.splits import make_split
from evaluation.alignment import align_reference,containment
from evaluation.official import load_notebook_namespace,EXPECTED_EVALUATOR_SHA256


def test_flatten_gold_preserves_all_content():
    row={"benchmark_chunks_w_metadata":{"x.pdf":[{"content":"first"}],"y.pdf":[{"content":"second"}]}}
    assert flatten_gold_chunks(row)==["first","second"]


def test_family_split_is_deterministic_and_never_splits_family():
    rows=[{"id":str(i)} for i in range(10)]
    families={str(i):"family"+str(i//2) for i in range(10)}
    a=make_split(rows,families);b=make_split(rows,families)
    assert a==b and set(a["dev"]).isdisjoint(a["holdout"])
    assert set(a["dev"])|set(a["holdout"])==set(families)
    for family in set(families.values()):
        members={i for i,f in families.items() if f==family}
        assert members<=set(a["dev"]) or members<=set(a["holdout"])


def test_unreviewed_incomplete_families_fail():
    with pytest.raises(ValueError): make_split([{"id":"one"},{"id":"two"}],{"one":"x"})


def test_alias_requires_identity_evidence():
    with pytest.raises(ValueError):
        align_reference("proposal.pdf","shared text",[],{"proposal.pdf":{"source_name":"different.pdf","status":"overlap_only"}})
    result=align_reference("proposal.pdf","shared text",[{"document":"different.pdf","chunk_id":"e","page":1,"content":"shared text"}])
    assert result["status"]=="absent_by_filename" and result["unique_missing_facts"] is None


def test_overlap_diagnostic_is_not_hard_negative():
    result=align_reference("a.pdf","some relevant capital",[{"document":"a.pdf","chunk_id":"e","page":1,"content":"unrelated prose"}])
    assert result["status"]=="unresolved"
    assert containment("relevant capital","some relevant capital here")==1


def test_supplied_official_notebook_untouched_if_available():
    path=Path(__file__).resolve().parents[3]/"Train/Evaluation/Evaluation.ipynb"
    if not path.exists(): pytest.skip("official dataset is external to source repository")
    before=path.read_bytes()
    ns=load_notebook_namespace(path)
    assert ns["_executed_cells"]==[1,5,7,9]
    assert "sample_dataset" not in ns
    assert before==path.read_bytes()
    assert hashlib.sha256(before).hexdigest()==EXPECTED_EVALUATOR_SHA256


def test_capture_preserves_writer_context_and_resume_generation(tmp_path):
    rows=[{"id":"s1","question":"capital","benchmark_answer":"reference","benchmark_chunks_w_metadata":{"source.pdf":[{"content":"reference source"}]}}]
    calls=[]
    def execute(collection,query):
        calls.append(query)
        return {"generation_id":"g1","config_sha256":"config1","answer":"supported answer","chunks":[{"content":"cited"},{"content":"writer context"}],"trace":[],"status":"partial"}
    path=tmp_path/"run.jsonl"
    manifest=capture(rows,api="local:",collection="test",out=path,source_hash="sourcehash",query_fn=execute)
    capture(rows,api="local:",collection="test",out=path,source_hash="sourcehash",query_fn=execute)
    result=json.loads(path.read_text(encoding="utf-8"))
    assert len(calls)==1 and result["retrieved_chunks"]==["cited","writer context"]
    assert manifest["generation_id"]=="g1" and manifest["system_config_sha256"]=="config1"
    with pytest.raises(ValueError,match="resume manifest"):
        capture(rows,api="local:",collection="different",out=path,source_hash="sourcehash",query_fn=execute)


def test_capture_keeps_failed_query_row_instead_of_skipping(tmp_path):
    rows=[{"id":"s1","question":"capital","benchmark_answer":"reference","benchmark_chunks_w_metadata":{}}]
    def fail(c,q): raise RuntimeError("offline")
    path=tmp_path/"failed.jsonl"
    capture(rows,api="local:",collection="test",out=path,source_hash="sourcehash",query_fn=fail)
    row=json.loads(path.read_text(encoding="utf-8"))
    assert row["id"]=="s1" and row["error"] and row["retrieved_chunks"]==[]


def test_official_judge_adapter_uses_configured_shared_transport(monkeypatch):
    from evaluation.official import OfficialJudgeTransport
    seen=[]
    class Client:
        def __init__(self,settings):
            seen.append(settings)
        def complete_json(self,system,user,**kwargs):
            seen.append((system,user,kwargs))
            return {'ok':True}
    monkeypatch.setattr('kb.llm.OpenCodeLLM',Client)
    client=OfficialJudgeTransport('fake','qwen3.8-flash','https://opencode.ai/inference/openai/v1/chat/completions')
    assert client.call_structured('system','source',max_tokens=512)=={'ok':True}
    assert seen[0].llm_model=='qwen3.8-flash' and seen[0].llm_max_retries==1
    assert seen[1][2]=={'name':'official_judge','max_tokens':512}


def test_deepseek_judge_is_cheap_cached_and_never_retries_an_empty_reply(tmp_path,monkeypatch):
    import requests
    from evaluation.official import OfficialJudgeTransport
    monkeypatch.setenv("KB_SPEND_LEDGER",str(tmp_path/"spend.jsonl"))
    monkeypatch.setenv("KB_BUDGET_USD","1")
    sent=[]
    class Reply:
        def __init__(self,content): self.content=content
        def raise_for_status(self): pass
        def json(self): return {"usage":{"prompt_tokens":10,"completion_tokens":20},
                                "choices":[{"message":{"content":self.content},"finish_reason":"stop" if self.content else "length"}]}
    replies=iter([Reply('{"points":["a"]}'),Reply(None)])
    monkeypatch.setattr(requests,"post",lambda url,headers,json,timeout:(sent.append(json),next(replies))[1])
    judge=OfficialJudgeTransport("test-key","deepseek-v4.1-flash","http://judge.test")
    judge.cache=tmp_path/"judge_cache"
    assert judge.call_structured("s","u")=={"points":["a"]} and sent[0]["reasoning_effort"]=="low"
    assert judge.call_structured("s","u")=={"points":["a"]} and len(sent)==1  # cached: no second paid call
    replies2=iter([Reply(None),Reply('{"points":[]}'),Reply(None),Reply(None)])
    monkeypatch.setattr(requests,"post",lambda url,headers,json,timeout:(sent.append(json),next(replies2))[1])
    assert judge.call_structured("s","other")=={"points":[]}  # token-exhausted: one retry with a larger limit
    assert [p["max_tokens"] for p in sent[1:]]==[10000,32000] and judge.over_notebook_limit==1
    with pytest.raises(RuntimeError,match="no content"):
        judge.call_structured("s","third")
    assert len(sent)==5  # never more than that one larger retry
