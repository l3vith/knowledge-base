from dataclasses import replace
from kb.query.plan import plan_query,guard_routing,query_hints
from kb.query.types import QueryPlan,Aspect
from .helpers import Card,MemoryStore,FakeLLM,settings


def test_preserves_explicit_comparison_scopes(tmp_path):
    cards=[Card("a24","a24.pdf",issuer="Acme Holdings",period_year=2024),Card("a25","a25.pdf",issuer="Acme Holdings",period_year=2025),
           Card("b25","b25.pdf",issuer="Beta Group",period_year=2025)]
    store=MemoryStore({c.doc_id:["capital ratio"] for c in cards},cards)
    query="Compare Acme Holdings 2024 and 2025 with Beta Group 2025 capital ratio"
    cfg=settings(tmp_path,router_max_docs=1)
    plan=plan_query(FakeLLM(),query,cards,cfg)
    guarded,report=guard_routing(plan,query,cards,store,cfg)
    assert set(guarded.doc_ids)=={"a24","a25","b25"}
    assert len(plan.aspects)>=4


def test_confirmed_wrong_period_cannot_reenter_route(tmp_path):
    cards=[Card("old","old.pdf",period_year=2024),Card("new","new.pdf",period_year=2025)]
    store=MemoryStore({c.doc_id:["Example Bank capital ratio"] for c in cards},cards)
    plan=QueryPlan("analytical",[Aspect("a1","capital ratio",["capital"])],["old","new"])
    guarded,report=guard_routing(plan,"Example Bank 2025 capital ratio",cards,store,settings(tmp_path))
    assert guarded.doc_ids==["new"]
    assert report["excluded"][0]["doc_id"]=="old"


def test_legacy_uncertain_metadata_is_soft(tmp_path):
    card=Card("old","old.pdf",period_year=2024,metadata_provenance={})
    store=MemoryStore({"old":["capital ratio"]},[card])
    plan=QueryPlan("analytical",[Aspect("a1","capital",["capital"])],["old"])
    guarded,_=guard_routing(plan,"Example Bank 2025 capital",[card],store,settings(tmp_path))
    assert guarded.doc_ids==["old"]
    assert guarded.limitations


def test_model_no_answer_does_not_stop_search(tmp_path):
    card=Card("d","d.pdf")
    store=MemoryStore({"d":["capital ratio 14 percent"]},[card])
    llm=FakeLLM(lambda n,p:{"answerable":False,"aspects":[],"documents":[]})
    plan=plan_query(llm,"capital ratio",[card],settings(tmp_path))
    guarded,report=guard_routing(plan,"capital ratio",[card],store,settings(tmp_path))
    assert guarded.answerable and guarded.doc_ids==["d"] and report["fallback"]


def test_planner_failure_falls_back_and_preserves_negation(tmp_path):
    def fail(n,p): raise RuntimeError("offline")
    plan=plan_query(FakeLLM(fail),"Which loans are not eligible?",[],settings(tmp_path))
    assert "not" in plan.aspects[0].keywords
    assert "planner_failed" in plan.notes


def test_obligation_overflow_is_visible(tmp_path):
    llm=FakeLLM(lambda n,p:{"aspects":[{"text":str(i)} for i in range(10)]})
    plan=plan_query(llm,"all risks",[],settings(tmp_path,max_obligations=2))
    assert len(plan.aspects)==2 and plan.limitations


def test_different_identifier_not_an_alias(tmp_path):
    cards=[Card("a","a.pdf",identifiers=["FR Doc. 2030-11111"]),Card("b","b.pdf",identifiers=["FR Doc. 2030-22222"])]
    store=MemoryStore({c.doc_id:["capital proposal"] for c in cards},cards)
    plan=QueryPlan("analytical",[Aspect("a1","proposal",["proposal"])],["a","b"])
    guarded,_=guard_routing(plan,"FR Doc. 2030-11111 capital proposal",cards,store,settings(tmp_path))
    assert guarded.doc_ids==["a"]


def test_null_or_wrong_planner_fields_have_safe_fallback(tmp_path):
    llm=FakeLLM(lambda n,p:{"intent":{},"aspects":[{"text":"capital","keywords":None}],"documents":None})
    result=plan_query(llm,"capital",[],settings(tmp_path))
    assert result.intent=="analytical" and result.aspects[0].keywords==["capital"]
