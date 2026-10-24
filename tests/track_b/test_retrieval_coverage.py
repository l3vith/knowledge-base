from kb.query.candidates import candidate_pages, element_retrieval
from kb.query.screen import local_survey_pages
from kb.query.triage import element_triage
from kb.query.types import Aspect, Candidate, QueryPlan
from kb.store import fts_query
from .helpers import MemoryStore, settings

PAGES=[f"Speed result {i}: calibration took {i} seconds." for i in range(1,24)]+["In conclusion, the surrogate cannot extrapolate."]


def plan():
    return QueryPlan("analytical",[Aspect("a1","calibration speed",["speed","calibration"])],["a"])


def test_retrieval_limits_are_four_times_the_previous_baseline():
    from kb.config import DEFAULT_BUDGETS
    from kb.config import get_settings
    from kb.query.settings import QuerySettings
    s=QuerySettings()
    assert s.survey_cards_total==4*400
    assert s.verify_pages==4*200
    assert s.lexical_net_pages_per_aspect==4*5
    assert s.element_hits_per_aspect==4*40
    assert s.escape_pages==4*20
    assert s.max_ce_pairs==4*400
    assert s.verify_chars_total==4*192000
    assert s.verify_output_tokens==4*48000
    assert s.task_recovery_batches==4*1
    assert DEFAULT_BUDGETS['analytical']['verify_chars']==4*120000
    assert get_settings().budget_usd==1.50


def test_decisive_limitation_on_the_last_page_reaches_verification(tmp_path):
    store=MemoryStore({"a":PAGES});s=settings(tmp_path)
    pool,lexical,report=candidate_pages(store,plan(),"calibration speed and limitations",None,s)
    picks,_=local_survey_pages(plan(),pool,lexical,report,s)
    assert {p.page_no for p in picks}==set(range(1,25))  # short document: every page eligible
    candidates,_=element_retrieval(store,plan(),"calibration speed and limitations",[],[],None,s)
    last=[c for c in candidates if c.element.page_no==24]
    assert last and "structure" in last[0].sources  # found by the conclusion search even with no page survey
    _,middle,_=element_triage(candidates,plan(),None,settings(tmp_path,verify_chars_total=200))
    assert middle[0].element.page_no==24  # verified first, before the budget runs out


def test_each_task_role_gets_a_candidate_before_repeated_aspect_hits(tmp_path):
    tasks=[{'id':f'T{i}','operation':'inspect','obligation_ids':['a1'],'source_roles':[f'role {i}']}
           for i in range(1,4)]
    p=QueryPlan('analytical',[Aspect('a1','all requested topics',['topics'])],['a'],tasks=tasks)
    store=MemoryStore({'a':[f'candidate {i}' for i in range(1,4)]})
    candidates=[Candidate(e,['a1'],[f'task_role:T{i}'],ce_score=1-i/10)
                 for i,e in enumerate(store.elements,1)]
    _,middle,report=element_triage(candidates,p,None,settings(tmp_path))
    assert [c.sources[0] for c in middle[:3]]==['task_role:T1','task_role:T2','task_role:T3']
    assert report['task_queue_counts']=={'T1':1,'T2':1,'T3':1}


def test_explicit_numerical_example_retrieves_matching_next_page_context(tmp_path):
    store=MemoryStore({'a':[
        'The amounts used in this example are for illustrative purposes and do not represent community bank allowance percentages.',
        'The institution allowance increased from 100 to 125 in the example.',
        'A separate topic discusses unrelated loan classifications.'
    ]})
    p=QueryPlan('factoid',[Aspect('a1','community bank allowance percentage',['community','bank','allowance','percentage'])],['a'])
    s=settings(tmp_path,element_hits_per_aspect=1)
    candidates,_=element_retrieval(store,p,'community bank allowance percentage',[],[],None,s)
    continuation=[c for c in candidates if c.element.page_no==2]
    assert continuation and 'source_continuation' in continuation[0].sources
    assert not any(c.element.page_no==3 for c in candidates)


def test_letter_digit_terms_also_match_their_split_markdown_form():
    assert fts_query(["i7","speed"])=='"i7" OR "speed" OR "i 7"'
