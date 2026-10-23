from dataclasses import replace
import pytest
from kb.query.answer import generate_answer, verify_answer
from kb.query.requirements import requested_topics, audit_topic_coverage
from kb.query.types import Aspect, Claim, Evidence, QueryPlan
from kb.query.utils import display_source
from evaluation.audit import judge_consistency
from .helpers import FakeLLM, MemoryStore, settings


def test_topics_are_literal_user_spans_not_planner_keywords():
    query='Compare accuracy, speed and build cost; discuss limitations.'
    rows=requested_topics(query,'analytical')
    assert {r['text'] for r in rows}=={'accuracy','speed','build cost','limitations'}
    assert all(query[r['query_start']:r['query_end']]==r['text'] for r in rows)
    assert requested_topics(query,'factoid')==[]


@pytest.mark.parametrize('rows',[
    [], [{'requirement_id':'R1','status':'supported','claim_ids':['invented']}],
    [{'requirement_id':'R1','status':'supported','claim_ids':[]}],
    [{'requirement_id':'R1','status':'supported','claim_ids':['c1']}]*2,
    [{'requirement_id':'R1','status':'partial','claim_ids':['c1']}],
])
def test_missing_duplicate_or_unaccepted_coverage_cannot_pass(rows):
    requirements=requested_topics('accuracy','analytical')
    result=audit_topic_coverage(requirements,rows,[Claim('c1','source',['E1'],['a1'])])
    assert result[0]['status']=='unresolved'


def test_supported_claim_does_not_prove_entire_query_covered(tmp_path):
    store=MemoryStore({'a':['Accuracy improved in the tests.']})
    evidence={'E1':Evidence(store.elements[0],['a1'])}
    plan=QueryPlan('analytical',[Aspect('a1','accuracy and speed',['accuracy','speed'])],['a'])
    def respond(name,payload):
        if name=='answer_verify':
            return {'verdicts':[{'claim_id':'c1','verdict':'supported'}],
                    'coverage':[{'requirement_id':'R1','status':'supported','claim_ids':['c1']},
                                {'requirement_id':'R2','status':'missing','claim_ids':[]}]}
        return FakeLLM.default(name,payload)
    llm=FakeLLM(respond)
    draft=generate_answer(llm,'accuracy and speed',plan,evidence,{},settings(tmp_path))
    checked,report=verify_answer(llm,draft,evidence,settings(tmp_path),query='accuracy and speed')
    assert len(checked.claims)==1 and checked.status=='partial'
    assert 'speed' in checked.limitations[-1]
    assert report['requested_topics'][0]['status']=='supported'
    assert [n for n,p in llm.calls]==['answer','answer_verify']


def test_background_is_removed_even_when_source_support_passes(tmp_path):
    store=MemoryStore({'a':['The algorithm was introduced decades ago.']})
    evidence={'E1':Evidence(store.elements[0],['a1'])}
    plan=QueryPlan('analytical',[Aspect('a1','performance',['performance'])],['a'])
    llm=FakeLLM(lambda n,p:{'verdicts':[{'claim_id':'c1','verdict':'supported','relevance':'background'}]}
                if n=='answer_verify' else FakeLLM.default(n,p))
    draft=generate_answer(llm,'performance',plan,evidence,{},settings(tmp_path))
    checked,report=verify_answer(llm,draft,evidence,settings(tmp_path),query='performance')
    assert not checked.claims and report['background_removed']==1


@pytest.mark.parametrize('raw,expected',[
    ('Error was 0 _._ 05%.','Error was 0.05%.'),
    ('Time was 60 _._ 5 microseconds.','Time was 60.5 microseconds.'),
    ('12 _,_ 000 and 1 _._ 25.','12,000 and 1.25.'),
    ('Version _._ unknown; x_y; 12,000; 0.05%.','Version _._ unknown; x_y; 12,000; 0.05%.'),
])
def test_numeric_display_cleanup_is_local_and_conservative(raw,expected):
    assert display_source(raw)==expected


def test_normalized_display_preserves_original_quotes(tmp_path):
    raw='Error was 0 _._ 05% in the tests.'
    store=MemoryStore({'a':[raw]});ev={'E1':Evidence(store.elements[0],['a1'])}
    plan=QueryPlan('factoid',[Aspect('a1','error',['error'])],['a'])
    draft=generate_answer(FakeLLM(),'error',plan,ev,{},settings(tmp_path))
    assert draft.claims[0].text=='Error was 0.05% in the tests.'
    assert draft.claims[0].quotes[0]['quote']==raw


def test_judge_audit_flags_contradictions_without_rewriting_scores():
    metrics={'answer_precision':0,'answer_detail':{
        'benchmark_points':{'bp1':'Accuracy improved.','bp2':'Source: a.pdf page 3.'},
        'agent_points':{'ap1':'Accuracy improved.'},'matched_ids':['bp1'],
        'missing_ids':['bp2'],'extra_ids':['ap1']}}
    result=judge_consistency(metrics,'Accuracy improved. [a.pdf p3]')
    assert {f['kind'] for f in result['flags']}=={
        'all_answer_points_extra_despite_benchmark_matches','citation_present_but_judge_marks_missing'}
    assert metrics['answer_precision']==0


def test_each_literal_topic_keeps_an_independent_source_page(tmp_path):
    from kb.query.candidates import candidate_pages
    store=MemoryStore({'a':['Accuracy improved.', 'Build cost was reduced.', 'Speed increased.']})
    plan=QueryPlan('analytical',[Aspect('a1','accuracy',['accuracy'])],['a'])
    pool,lexical,report=candidate_pages(store,plan,'accuracy, speed and build cost',None,settings(tmp_path))
    assert {1,2,3} <= lexical['a']
    assert len(report['documents']['a']['requested_topic_hits'])==3


def test_bounded_answers_keep_source_text_and_topic_diversity(tmp_path):
    from kb.query.answer import bound_analytical_claims
    claims=[Claim('c1','Accuracy error was 0.2%.',['E1'],['a1'],requirement_ids=['R1']),
            Claim('c2','Accuracy error was 0.2%.',['E2'],['a1'],requirement_ids=['R1']),
            Claim('c3','Runtime was 12 milliseconds.',['E3'],['a1'],requirement_ids=['R2'])]
    chosen,report=bound_analytical_claims(claims,settings(tmp_path,analytical_answer_chars=100,analytical_answer_claims=2))
    assert {c.claim_id for c in chosen}=={'c1','c3'}
    assert report['selected_source_chars']<=100
    assert chosen[0] is claims[0] and chosen[1] is claims[2]


def test_judge_audit_flags_nearly_all_extra_as_review_only():
    detail={'benchmark_points':{f'bp{i}':'result' for i in range(3)},
            'agent_points':{f'ap{i}':'result' for i in range(10)},
            'matched_ids':['bp0','bp1','bp2'],'extra_ids':[f'ap{i}' for i in range(9)]}
    metrics={'answer_precision':.1,'answer_detail':detail}
    audit=judge_consistency(metrics,'source answer')
    assert audit['flags'][0]['kind']=='possible_inconsistent_matching_nearly_all_answer_points_extra'
    assert metrics['answer_precision']==.1
