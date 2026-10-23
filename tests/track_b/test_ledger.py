from dataclasses import replace
import pytest
from kb.query.ledger import parse_records, select_records, cell_key, generate_ledger_answer, numeric_tokens
from kb.query.answer import generate_answer, verify_answer
from kb.query.types import Aspect, QueryPlan, Evidence
from .helpers import MemoryStore, FakeLLM, settings


def fixture():
    store=MemoryStore({'a':['Direct method required 200 calls.','TT method required 900 calls.','TT method is reusable offline.']})
    ev={f'E{i+1}':Evidence(el,['a1']) for i,el in enumerate(store.elements)}
    plan=QueryPlan('analytical',[Aspect('a1','construction cost',['cost'])],['a'])
    def row(i,eid,method,values,**kwargs):
        return dict(id=i,obligation_ids=['a1'],requirement_ids=[],role='FINDING',experiment=None,
                    method=method,metric='construction_effort',mode='REPORTED',values=values,
                    anchors=[{'evidence_id':eid,'span_ids':['S1']}],links=[],**kwargs)
    rows=[row('L1','E1','Direct method',['200 calls']),row('L2','E2','TT method',['900 calls'])]
    return ev,plan,rows


def test_observed_cells_preserve_both_methods_without_cartesian_invention():
    ev,plan,rows=fixture();records,audit=parse_records({'records':rows},ev,plan,[])
    selected,report=select_records(records,10000)
    assert report['observed_cells']==report['selected_cells']==2
    assert {r.record_id for r in selected}=={'L1','L2'}


def test_fabricated_quantity_cannot_enter_ledger():
    ev,plan,rows=fixture();rows[0]['values']=['300 calls']
    records,audit=parse_records({'records':rows},ev,plan,[])
    assert [r.record_id for r in records]==['L2']
    assert audit['rejections'][0]['reason']=='non_exact_value'


def test_unanchored_experiment_becomes_unknown_and_cannot_join_methods():
    ev,plan,rows=fixture();rows[0]['experiment']='Imagined experiment';rows[0]['links']=['L2']
    records,audit=parse_records({'records':rows},ev,plan,[])
    assert records[0].experiment is None and not records[0].links
    assert len(audit['warnings'])==2


def test_background_is_quarantined_before_writer():
    ev,plan,rows=fixture();rows[0]['role']='BACKGROUND'
    records,audit=parse_records({'records':rows},ev,plan,[])
    assert len(records)==1 and audit['rejections'][0]['reason']=='quarantined_background'


def test_duplicate_record_ids_fail_closed():
    ev,plan,rows=fixture();rows[1]['id']='L1'
    records,audit=parse_records({'records':rows},ev,plan,[])
    assert not records


def test_different_experiments_or_methods_do_not_automatically_share_baselines():
    ev,plan,rows=fixture();rows[0]['links']=['L2']
    records,audit=parse_records({'records':rows},ev,plan,[])
    assert not records[0].links
    assert cell_key(records[0])!=cell_key(records[1])


def test_qualification_dependency_counts_toward_real_budget():
    ev,plan,rows=fixture();records,_=parse_records({'records':rows},ev,plan,[])
    first=replace(records[0],experiment='same',method='same',links=['L2'])
    second=replace(records[1],experiment='same',method='same',role='QUALIFICATION')
    cap=len(first.quotes[0]['quote'])
    selected,report=select_records([first,second],cap)
    assert 'L1' not in {r.record_id for r in selected}
    assert report['quote_chars']<=cap


def test_ledger_writer_gets_records_not_unfiltered_paragraphs_and_repairs_omissions(tmp_path):
    ev,plan,rows=fixture()
    def respond(n,p):
        if n=='ledger_extract':return {'records':rows}
        if n=='answer':
            assert 'records' in p and 'sources' not in p and 'evidence' not in p
            return {'status':'answered','selections':[{'text':'Direct method required 200 calls.','record_ids':['L1']}]}
        return FakeLLM.default(n,p)
    cfg=settings(tmp_path,analytical_writer_mode='ledger');llm=FakeLLM(respond)
    draft=generate_answer(llm,'construction cost',plan,ev,{},cfg)
    assert {rid for c in draft.claims for rid in c.record_ids}=={'L1','L2'}
    assert all(q['quote'] in ev[q['evidence_id']].element.text for c in draft.claims for q in c.quotes)
    assert [n for n,p in llm.calls]==['ledger_extract','answer']


def test_new_numeric_assertion_rejected_and_source_fallback_used(tmp_path):
    ev,plan,rows=fixture()
    def respond(n,p):
        if n=='ledger_extract':return {'records':rows[:1]}
        return {'selections':[{'text':'Direct method required 999 calls.','record_ids':['L1']}]}
    draft=generate_answer(FakeLLM(respond),'cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert '999' not in draft.claims[0].text and '200' in draft.claims[0].text
    assert draft.status=='partial'


def test_semantic_rejection_removes_record_from_coverage(tmp_path):
    ev,plan,rows=fixture()
    def respond(n,p):
        if n=='ledger_extract':return {'records':rows[:1]}
        if n=='answer':return {'selections':[{'text':'Direct method required 200 calls.','record_ids':['L1']}]}
        if n=='answer_verify':return {'verdicts':[{'claim_id':'c1','verdict':'unsupported'}]}
    cfg=settings(tmp_path,analytical_writer_mode='ledger');llm=FakeLLM(respond)
    draft=generate_answer(llm,'cost',plan,ev,{},cfg)
    checked,report=verify_answer(llm,draft,ev,cfg,query='cost')
    assert not checked.claims and report['ledger']['selected_cell_coverage']==0
    assert checked.status=='partial'


def test_factual_path_never_extracts_ledger(tmp_path):
    ev,plan,rows=fixture();plan.intent='factoid';llm=FakeLLM()
    generate_answer(llm,'calls',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert 'ledger_extract' not in [n for n,p in llm.calls]


def test_numeric_guard_normalizes_markup_without_changing_values():
    assert numeric_tokens('0 _._ 05% and 12 _,_ 000 calls')=={'0.05','12000'}


def test_unknown_scope_cannot_be_synthesized_into_one_cross_experiment_range(tmp_path):
    ev,plan,rows=fixture()
    def respond(n,p):
        if n=='ledger_extract':return {'records':rows}
        return {'selections':[{'text':'The methods used 200 to 900 calls.','record_ids':['L1','L2']}]}
    draft=generate_answer(FakeLLM(respond),'cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert len(draft.claims)==2
    assert all(len(c.record_ids)==1 for c in draft.claims)
    assert all('200 to 900' not in c.text for c in draft.claims)


def test_modality_aliases_preserve_unknown_mode_and_exact_quotes():
    ev,plan,rows=fixture();rows[0]['role']='CONTROL';rows[0]['mode']='RECOMMENDED'
    records,audit=parse_records({'records':rows[:1]},ev,plan,[])
    assert records[0].role=='QUALIFICATION' and records[0].mode=='UNSPECIFIED'
    assert records[0].quotes[0]['quote']==ev['E1'].element.text


def test_synthesis_cannot_turn_a_reported_result_into_a_mandatory_control(tmp_path):
    ev,plan,rows=fixture()
    def respond(n,p):
        if n=='ledger_extract':return {'records':rows[:1]}
        return {'selections':[{'text':'Production systems must use 200 calls.','record_ids':['L1']}]}
    draft=generate_answer(FakeLLM(respond),'cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert all('must' not in c.text for c in draft.claims)


def test_projected_result_must_keep_its_modality(tmp_path):
    ev,plan,rows=fixture();rows[0]['mode']='PROJECTED'
    def respond(n,p):
        if n=='ledger_extract':return {'records':rows[:1]}
        return {'selections':[{'text':'Direct method required 200 calls.','record_ids':['L1']}]}
    draft=generate_answer(FakeLLM(respond),'cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert draft.limitations and draft.claims[0].quotes


def test_query_runtime_reserves_ledger_plus_writer_and_final_check(tmp_path):
    from kb.query.runtime import QueryRuntime
    from kb.query.errors import BudgetExceeded
    from kb.query.observability import LocalSink
    runtime=QueryRuntime(settings(tmp_path,max_llm_calls=4),FakeLLM(),LocalSink())
    runtime.pending_ledger=True;runtime.calls=1
    with pytest.raises(BudgetExceeded):runtime._reserve('verify','system',{},100)
    runtime._reserve('ledger_extract','system',{},100)
    runtime._reserve('answer','system',{},100)
    runtime._reserve('answer_verify','system',{},100)
    assert runtime.calls==4
