from kb.query.types import QueryPlan,Aspect,Candidate,SurveyPick
from kb.query.candidates import candidate_pages,element_retrieval
from kb.query.triage import element_triage
from kb.query.screen import verify_elements,survey_pages
from .helpers import MemoryStore,FakeLLM,FakeReranker,Element,settings


def plan(intent="analytical"):
    return QueryPlan(intent,[Aspect("a1","capital",["capital"])],["a","b"])


def test_page_cap_preserves_two_explicit_documents(tmp_path):
    store=MemoryStore({"a":["capital ratio"]*20,"b":["capital buffer"]*20})
    pool,net,report=candidate_pages(store,plan("exhaustive"),"capital",None,settings(tmp_path,survey_cards_total=4))
    assert len(pool["a"])==len(pool["b"])==2
    assert report["omitted_cards"]==36


def test_lexical_page_survives_summary_rejection(tmp_path):
    store=MemoryStore({"a":["capital ratio was 14 percent"]})
    p=QueryPlan("analytical",[Aspect("a1","capital",["capital"])],["a"])
    selected,report=survey_pages(FakeLLM(lambda n,p:{"pages":[]}),store,p,"capital",{"a":[1]},{"a":{1}},settings(tmp_path))
    assert selected[0].strength=="lexical"


def test_equal_text_in_distinct_documents_not_deduplicated(tmp_path):
    store=MemoryStore({"a":["capital ratio was 14 percent"],"b":["capital ratio was 14 percent"]})
    candidates,_=element_retrieval(store,plan(),"capital",[SurveyPick(d,1,["a1"],"high") for d in ["a","b"]],[],None,settings(tmp_path))
    evidence,_=verify_elements(FakeLLM(),store,plan(),"capital",candidates,settings(tmp_path))
    assert len(evidence)==2


def test_long_tail_never_marked_verified_without_visibility(tmp_path):
    text="capital row\n"*90+"TAIL UNIQUE 99\n"
    store=MemoryStore({"a":[text]})
    candidate=Candidate(store.elements[0],["a1"],["hybrid"])
    p=QueryPlan("analytical",[Aspect("a1","capital",["capital"])],["a"])
    llm=FakeLLM();evidence,report=verify_elements(llm,store,p,"capital",[candidate],settings(tmp_path,verify_chars_per_call=100,verify_chars_total=180))
    visible=[e["text"] for name,payload in llm.calls if name=="verify" for e in payload["elements"]]
    assert all(ev.element.text in visible for ev in evidence)
    assert all("TAIL UNIQUE" not in ev.element.text for ev in evidence)
    assert report["omitted_fragments"]>0


def test_invalid_support_quote_is_rejected(tmp_path):
    store=MemoryStore({"a":["capital ratio is 14 percent"]})
    llm=FakeLLM(lambda n,p:{"keep":[{"id":"E1","aspects":["a1"],"quotes":["invented 90 percent"]}]})
    evidence,report=verify_elements(llm,store,plan(),"capital",[Candidate(store.elements[0],["a1"],["hybrid"])],settings(tmp_path))
    assert not evidence and report["invalid_quotes"]==1


def test_reranker_actual_pair_limits_and_tail_windows(tmp_path):
    text="irrelevant "*80+"capital tail"
    el=Element("e","a",1,0,"text","",text)
    reranker=FakeReranker()
    kept,middle,report=element_triage([Candidate(el,["a1"],["hybrid"])],plan(),reranker,settings(tmp_path,max_ce_pairs=100))
    assert not kept and middle[0].ce_score>0
    assert any("capital tail" in t for q,t in reranker.seen)


def test_missing_tokenizer_skips_reranker_without_auto_keep(tmp_path):
    class UnsafeRanker:
        def score(self,*args): raise AssertionError("must not be called")
    el=Element("e","a",1,0,"text","","capital")
    kept,middle,report=element_triage([Candidate(el,["a1"],["hybrid"])],plan(),UnsafeRanker(),settings(tmp_path))
    assert not kept and len(middle)==1 and report["limitations"]


def test_token_counter_clones_truncating_fastembed_tokenizer():
    from types import SimpleNamespace
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from kb.query.triage import _counter
    tokenizer=Tokenizer(WordLevel({"[UNK]":0,"capital":1,"row":2},unk_token="[UNK]"))
    tokenizer.pre_tokenizer=Whitespace();tokenizer.enable_truncation(max_length=8)
    wrapper=SimpleNamespace(model=SimpleNamespace(model=SimpleNamespace(tokenizer=tokenizer)))
    count=_counter(wrapper)
    assert count("capital","row "*30)>8
    assert len(tokenizer.encode("capital","row "*30).ids)==8
    assert count.model_limit==8


import pytest
@pytest.mark.slow
def test_real_fastembed_adapter_counts_unseen_tail_and_scores_windows(tmp_path):
    from kb.config import get_settings
    from kb.embed import get_reranker
    from kb.query.triage import _counter
    ranker=get_reranker(get_settings())
    count=_counter(ranker)
    text="unrelated cafeteria sentence "*250+"minimum capital ratio is 4.5 percent"
    assert count("capital ratio",text)>512
    el=Element("long","a",1,0,"text","",text)
    _,middle,report=element_triage([Candidate(el,["a1"],["hybrid"])],plan(),ranker,settings(tmp_path,max_ce_pairs=20))
    assert report["pairs"]>=2 and report["scored"]==1 and middle[0].ce_score is not None
