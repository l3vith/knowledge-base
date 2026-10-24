"""Regression cases for failures found after the teammate synthesis merge."""
from dataclasses import replace
from kb.query.facts import states, inventory, trim_secondary, is_fact
from kb.query.answer import (source_spans, generate_answer, verify_answer, _restore_facts,
                             _synthesis_calculation, _calculation_text, _repeats)
from kb.query.types import Evidence, Claim, AnswerDraft, QueryPlan, Aspect
from evaluation.audit import judge_consistency
from .helpers import MemoryStore, FakeLLM, settings


def test_qualitative_fact_cannot_be_covered_by_any_sentence_with_no_numbers():
    fact={'text':'The correlation parameter controls the skewness of spot returns.'}
    assert not states('The model supports accurate pricing.',fact)
    assert states('Correlation controls the skewness of spot returns.',fact)
    assert not states('Correlation does not control skewness of spot returns.',fact)
    assert not states('Correlation controls skewness in the projected experiment.',fact)


def test_small_and_short_mechanistic_results_are_not_lost():
    assert is_fact('ρ controls skewness.')
    assert is_fact('The maximum rank of the fitted tensor was 12.')
    assert is_fact('The largest tested dimension was 13.')
    assert is_fact('This paper reports that positive correlation increases call prices.')


def test_equal_values_in_different_experiments_and_documents_stay_distinct():
    store=MemoryStore({'a':['Direct calibration took 2 seconds.','TT calibration took 2 seconds.'],
                       'b':['Direct calibration took 2 seconds.']})
    ev={f'E{i}':Evidence(e,['a1']) for i,e in enumerate(store.elements)}
    facts=inventory(ev,source_spans(ev),[])
    kept,_=trim_secondary(facts)
    assert len(kept)==3
    assert len({tuple(f['scope']) for f in kept})==3


def test_sampling_and_train_test_details_are_retained_when_validation_is_asked():
    facts=[{'id':'F1','text':'From 1,000 points, 800 were used for training and 200 for testing.','doc_id':'a'},
           {'id':'F2','text':'The 1,000 combinations were obtained by randomly sampling the parameter domain.','doc_id':'a'}]
    assert not trim_secondary(facts)[0]
    assert len(trim_secondary(facts,'Assess validation and production controls')[0])==2


def test_statement_deduplication_needs_same_cited_span_and_mode():
    text='The calibration is 40,000 times faster than the pricing function.'
    seen=[(text,frozenset({'a'}),(('E1','S1'),))]
    assert _repeats(text,seen,frozenset({'a'}),(('E1','S1'),))
    assert not _repeats(text,seen,frozenset({'a'}),(('E2','S1'),))
    assert not _repeats('The calibration is expected to be 40,000 times faster than the pricing function.',seen,frozenset({'a'}),(('E1','S1'),))


def test_code_owns_calculation_result_text_and_rounding():
    spans={'E1':{'S1':'The build used 10,000 calls.','S2':'The grid had 117,649 points.'}}
    raw={'operation':'percentage','operands':[{'evidence_id':'E1','span_id':'S1','value':'10000','unit':'calls'},
        {'evidence_id':'E1','span_id':'S2','value':'117649','unit':'points'}],'result':'99.9','unit':'%','decimals':1}
    calc=_synthesis_calculation(raw,spans)
    assert calc['result']=='8.5' and '8.5 %' in _calculation_text(calc) and '99.9' not in _calculation_text(calc)
    assert _synthesis_calculation({**raw,'decimals':-1},spans) is None
    assert _synthesis_calculation({**raw,'decimals':True},spans) is None


def test_gap_is_checked_against_all_inspected_evidence_and_rejected_when_contradicted(tmp_path):
    store=MemoryStore({'a':['Market data validation was performed on 100 surfaces.']})
    ev={'E1':Evidence(store.elements[0],['a1'])}
    draft=AnswerDraft([Claim('c1','Not shown in the inspected evidence: market data validation.',[],['a1'],kind='gap')],'partial')
    def respond(n,p):
        assert n=='answer_verify' and 'Market data validation' in p['evidence'][0]['content']
        return {'verdicts':[{'claim_id':'c1','verdict':'unsupported'}]}
    checked,report=verify_answer(FakeLLM(respond),draft,ev,settings(tmp_path),query='Assess validation')
    assert not checked.claims and report['rejected']==1 and report['gaps']==0


def test_restoring_facts_after_filtered_claims_never_reuses_existing_ids():
    store=MemoryStore({'a':['Calibration took 2 seconds.']});ev={'E1':Evidence(store.elements[0],['a1'])}
    claims=[Claim('c2','Existing claim.',[],[])]
    missing=[{'id':'F1','evidence_id':'E1','span_id':'S1','topic':'a1'}]
    _restore_facts(missing,ev,source_spans(ev),claims,[])
    assert [c.claim_id for c in claims]==['c2','c3']


def test_background_fact_rejected_by_checker_is_not_resurrected(tmp_path):
    store=MemoryStore({'a':['The unrelated calibration took 2 seconds.']});ev={'E1':Evidence(store.elements[0],['a1'])}
    fact={'id':'F1','evidence_id':'E1','span_id':'S1','topic':'a1'}
    claim=Claim('c1',store.elements[0].text,['E1'],['a1'],[{'evidence_id':'E1','quote':store.elements[0].text}],fact_ids=['F1'])
    draft=AnswerDraft([claim],'partial',facts=[fact])
    checked,_=verify_answer(FakeLLM(lambda n,p:{'verdicts':[{'claim_id':'c1','verdict':'supported','relevance':'background'}]}),
                            draft,ev,settings(tmp_path))
    assert not checked.claims


def test_split_citation_points_and_messages_truncation_are_visible():
    metrics={'answer_detail':{'benchmark_points':{'bp1':'The source is a.pdf.','bp2':'The location is page 15.'},
        'agent_points':{'ap1':'A result.'},'matched_ids':[],'missing_ids':['bp1','bp2'],'extra_ids':[]}}
    audit=judge_consistency(metrics,'A result. [a.pdf p15]',[{'request_sha256':'r','finish_reason':'max_tokens'}])
    assert len([f for f in audit['flags'] if f['kind']=='citation_present_but_judge_marks_missing'])==2
    assert any(f['kind']=='judge_response_truncated_at_notebook_limit' for f in audit['flags'])
