from dataclasses import replace
import json
import pytest
from kb.query.pipeline import answer_query,STEP_NAMES
from kb.query.runtime import QueryRuntime
from kb.query.errors import QueryError,BudgetExceeded
from kb.query.observability import LocalSink
from .helpers import MemoryStore,FakeLLM,settings,Card


def run(tmp_path,store=None,llm=None,**kw):
    return answer_query("demo","capital ratio",store=store or MemoryStore({"a":["Capital ratio was 14 percent."]}),
                        generation_id="g1",settings=settings(tmp_path,**kw),llm=llm or FakeLLM(),sink=LocalSink())


def test_ten_stage_trace_and_source_fidelity(tmp_path):
    store=MemoryStore({"a":["Capital ratio was 14 percent."]})
    result=run(tmp_path,store)
    assert [t["step_name"] for t in result["trace"]]==STEP_NAMES
    assert all(set(t)=={"step_name","description","input","output"} for t in result["trace"])
    assert result["chunks"][0]["content"]==store.elements[0].text
    assert result["status"]=="answered"
    assert result["usage"]["cost_usd"] is None
    assert result["usage"]["input_tokens"]==500
    assert (tmp_path/"runs"/result["request_id"]/"writer_context.json").exists()


def test_no_candidates_no_model_answer_and_all_trace_steps(tmp_path):
    llm=FakeLLM()
    result=answer_query("demo","xyz absent",store=MemoryStore({}),generation_id="g1",settings=settings(tmp_path),llm=llm,sink=LocalSink())
    assert result["status"]=="no_answer" and not result["chunks"]
    assert len(result["trace"])==10
    assert "answer" not in [name for name,p in llm.calls]


def test_provider_failure_is_not_a_no_answer(tmp_path):
    def respond(n,p):
        if n=="verify": raise RuntimeError("provider offline")
        return FakeLLM.default(n,p)
    with pytest.raises(QueryError,match="verification failed"):
        run(tmp_path,llm=FakeLLM(respond))
    failures=list((tmp_path/"runs").glob("*/failure.json"))
    assert len(failures)==1


def test_writer_visible_unused_context_is_returned(tmp_path):
    store=MemoryStore({"a":["Capital ratio was 14 percent.\n\nCapital buffer was 3 percent."]})
    def respond(n,p):
        result=FakeLLM.default(n,p)
        if n=="answer": result["claims"]=result["claims"][:1]
        return result
    result=run(tmp_path,store,FakeLLM(respond))
    assert len(result["chunks"])==2
    assert any(c["evidence_role"]=="writer_context" for c in result["chunks"])


def test_missing_period_returns_explicit_limitations(tmp_path):
    cards=[Card("old","old.pdf",period_year=2024)]
    result=answer_query("demo","Example Bank 2025 capital",store=MemoryStore({"old":["Capital 12 in FY2024."]},cards),generation_id="g1",settings=settings(tmp_path),llm=FakeLLM(),sink=LocalSink())
    assert result["coverage"]["limitations"]
    assert not result["chunks"]


def test_strict_observability_cannot_use_noop_sink(tmp_path):
    with pytest.raises(QueryError,match="Langfuse"):
        run(tmp_path,strict_observability=True)


def test_deadline_checked_before_model_call(tmp_path):
    runtime=QueryRuntime(settings(tmp_path),FakeLLM(),LocalSink());runtime.deadline=0
    with pytest.raises(BudgetExceeded): runtime.call("plan","system",{},100)
    assert runtime.calls==0


def test_budget_does_not_silently_become_corpus_absence(tmp_path):
    with pytest.raises(BudgetExceeded): run(tmp_path,max_llm_calls=1)


def test_same_source_in_two_collections_keeps_generation(tmp_path):
    store=MemoryStore({"a":["Capital ratio was 14 percent."]})
    a=answer_query("one","capital",store=store,generation_id="generation_one",settings=settings(tmp_path),llm=FakeLLM(),sink=LocalSink())
    b=answer_query("two","capital",store=store,generation_id="generation_two",settings=settings(tmp_path),llm=FakeLLM(),sink=LocalSink())
    assert a["generation_id"]=="generation_one" and b["generation_id"]=="generation_two"
    assert a["request_id"]!=b["request_id"]
