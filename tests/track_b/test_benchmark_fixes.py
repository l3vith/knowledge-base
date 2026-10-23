"""Regression coverage for measured latency, schema and numerical failures."""
import json
import numpy as np
import pytest
from kb.query.answer import select_portfolio
from kb.query.errors import QueryError
from kb.query.pipeline import answer_query
from kb.query.screen import verify_elements
from kb.query.types import Aspect, QueryPlan, Candidate, Evidence
from kb.query.utils import fragment, support_spans, narrow_factoid
from kb.store import _Vectors
from .helpers import MemoryStore, FakeLLM, FakeReranker, settings


def plan(intent="analytical"):
    return QueryPlan(intent,[Aspect("a1","How many trials?",["trials"])],["d"])


def test_spans_reconstruct_math_and_nested_offsets():
    store=MemoryStore({"d":[('Equation "x\\y".\n'+'π trials. ')*200]})
    el=store.elements[0]
    spans=support_spans(el.text)
    assert ''.join(spans.values())==el.text
    outer=fragment(el,20,300)
    inner=fragment(outer,10,80)
    assert inner.parent_element_id==el.element_id
    assert (inner.char_start,inner.char_end)==(30,100)
    assert inner.text==el.text[30:100]


def test_compact_batches_do_not_echo_text_and_reject_unknown_span(tmp_path):
    store=MemoryStore({"d":['\n\n'.join(f'Trial count {i}.' for i in range(35))]})
    candidates=[Candidate(e,["a1"],["fts"]) for e in store.elements]
    def respond(name,p):
        assert all("text" not in e for e in p["elements"])
        assert len(p["elements"])<=8
        return {"keep":[{"id":"E1","aspects":["a1"],"support_span_ids":["S999"]}]}
    llm=FakeLLM(respond)
    evidence,report=verify_elements(llm,store,plan(),"trials",candidates,settings(tmp_path))
    assert not evidence and report['invalid_quotes']==5
    assert len(llm.calls)==5


def test_schema_failure_splits_once_then_stops(tmp_path):
    store=MemoryStore({"d":['\n\n'.join(f'Trials {i}' for i in range(32))]})
    calls=[]
    def fail(name,p):
        calls.append(len(p['elements']))
        raise QueryError('MODEL_SCHEMA','truncated',503)
    with pytest.raises(QueryError,match='absence cannot be inferred'):
        verify_elements(FakeLLM(fail),store,plan(),'trials',
                        [Candidate(e,['a1'],['fts']) for e in store.elements],settings(tmp_path))
    assert sorted(calls[:4])==[8,8,8,8] and calls[4:]==[4]  # one parallel round, one split retry, then no new calls


def test_recovery_retains_successful_evidence(tmp_path):
    store=MemoryStore({'d':['\n\n'.join(f'Trials {i}' for i in range(8))]})
    calls=[]
    def respond(name,p):
        calls.append(len(p['elements']))
        if len(calls)==1:
            raise QueryError('MODEL_SCHEMA','truncated',503)
        return FakeLLM.default(name,p)
    evidence,report=verify_elements(FakeLLM(respond),store,plan(),'trials',
                        [Candidate(e,['a1'],['fts']) for e in store.elements],settings(tmp_path))
    assert len(evidence)==8 and calls==[8,4,4]
    assert report['split_retries']==1


def test_factoid_uses_reserve_and_leaves_unread_work_visible(tmp_path):
    store=MemoryStore({'d':['\n\n'.join(f'Trials {i}' for i in range(24))]})
    calls=[]
    def respond(name,p):
        calls.append(p)
        return {'keep':[]} if len(calls)==1 else FakeLLM.default(name,p)
    evidence,report=verify_elements(FakeLLM(respond),store,plan('factoid'),'How many trials?',
                        [Candidate(e,['a1'],['fts']) for e in store.elements],settings(tmp_path))
    assert len(calls)==2 and len(evidence)==8
    assert report['bounded_candidates_not_verified']==8


def test_factual_fast_path_skips_survey_keeps_ten_stages(tmp_path):
    def respond(name,p):
        if name=='plan':
            return {'intent':'factoid','aspects':[{'text':'How many trials?','keywords':['trials']}],'documents':[]}
        return FakeLLM.default(name,p)
    llm=FakeLLM(respond)
    result=answer_query('c','How many trials?',store=MemoryStore({'d':['The study used 72 trials.']}),
                       generation_id='g',settings=settings(tmp_path),llm=llm,reranker=FakeReranker())
    assert len(result['trace'])==10
    assert result['trace'][3]['output']['skipped']
    assert 'survey' not in [n for n,_ in llm.calls]
    assert result['chunks'][0]['content']=='The study used 72 trials.'
    p=plan('factoid')
    for query in ['Compare trials','List all trials','Explain trials across periods']:
        assert not narrow_factoid(p,query)
    p.limitations=['Period unresolved']
    assert not narrow_factoid(p,'How many trials?')


def test_duplicate_scalar_support_keeps_conflicts_units_dependencies(tmp_path):
    store=MemoryStore({'d':['Used 72 trials.\n\nWe performed the experiment using 72 trials.\n\nOther experiment used 81 trials.\n\nDuration 72 hours.']})
    values=['72 trials','72 trials','81 trials','72 hours']
    ev=[Evidence(e,['a1'],quotes=[e.text],fact_value=v) for e,v in zip(store.elements,values)]
    selected,report=select_portfolio(ev,plan('factoid'),settings(tmp_path))
    assert report['redundant_removed']==1 and report['omitted']==0
    assert {e.fact_value for e in selected}=={'72 trials','81 trials','72 hours'}
    assert store.elements[0] in [e.element for e in selected]
    ev[1].dependencies=['table_header']
    assert len(select_portfolio(ev,plan('factoid'),settings(tmp_path))[0])==4
    assert len(select_portfolio(ev,plan(),settings(tmp_path))[0])==4


def test_dense_scoped_search_finite_under_strict_fp():
    rng=np.random.default_rng(33)
    vectors=rng.normal(size=(24,384)).astype(np.float32)
    vectors/=np.linalg.norm(vectors,axis=1,keepdims=True)
    q=vectors[[3,8]]
    keys=[('d' if i<12 else 'other',i) for i in range(24)]
    index=_Vectors(vectors,keys,lambda k:k[0])
    with np.errstate(all='raise'):
        found=index.search(q,['d'],12)
    reference=[(keys[i],max(sum(float(a)*float(b) for a,b in zip(vectors[i],query)) for query in q)) for i in range(12)]
    reference.sort(key=lambda row:-row[1])
    assert [k for k,_ in found]==[k for k,_ in reference]
    assert np.allclose([v for _,v in found],[v for _,v in reference],atol=1e-12)
    with pytest.raises(ValueError,match='finite'):
        index.search(np.full((1,384),np.nan),['d'],1)
    with pytest.raises(ValueError,match='dimensions'):
        index.search(np.ones((1,3)),['d'],1)


def test_repeated_nested_fragments_keep_distinct_source_offsets():
    el=MemoryStore({'d':['same block '*100]}).elements[0]
    a=fragment(fragment(el,0,100),0,20)
    b=fragment(fragment(el,110,210),0,20)
    assert a.text==b.text
    assert a.element_id!=b.element_id
    assert (a.char_start,b.char_start)==(0,110)


def test_local_page_navigation_uses_no_survey_call(tmp_path):
    llm=FakeLLM()
    result=answer_query('c','Explain trial counts and reported results',
                       store=MemoryStore({'d':['Trials 72 and reported results improved.']}),
                       generation_id='g',settings=settings(tmp_path),llm=llm,reranker=FakeReranker())
    assert 'survey' not in [n for n,_ in llm.calls]
    assert result['trace'][3]['output']['selection_mode']=='local'
    assert result['trace'][3]['output']['navigation_only']
    assert result['chunks'][0]['content']=='Trials 72 and reported results improved.'
    assert len(result['trace'])==10
