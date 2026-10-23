from dataclasses import FrozenInstanceError
import pytest
from kb.query.anchors import SourceCatalog, source_format_key
from kb.query.ledger import parse_id_records, integrated_records, parse_records
from kb.query.answer import generate_answer, select_portfolio, verify_answer
from kb.query.screen import verify_elements
from kb.query.types import Aspect, QueryPlan, Evidence, Candidate
from .helpers import MemoryStore, FakeLLM, settings


def fixture(text='The method used 12 _,_ 000 calls with error 0 _._ 05%.'):
    store=MemoryStore({'d':[text]});ev={'E1':Evidence(store.elements[0],['a1'])}
    plan=QueryPlan('analytical',[Aspect('a1','accuracy and cost',['accuracy','cost'])],['d'])
    return store,ev,plan,SourceCatalog(ev)


def test_source_ids_are_immutable_and_independent_of_local_evidence_numbering():
    store,ev,plan,catalog=fixture();other=SourceCatalog({'E99':ev['E1']})
    assert catalog.by_evidence['E1']==other.by_evidence['E99']
    assert catalog.value_ids['E1']==other.value_ids['E99']
    for anchor in catalog.anchors.values():
        assert store.elements[0].text[anchor.char_start:anchor.char_end]==anchor.text
    with pytest.raises(TypeError):catalog.anchors['invented']='x'
    with pytest.raises(FrozenInstanceError):next(iter(catalog.anchors.values())).text='invented'


def test_equal_values_at_different_offsets_stay_distinct():
    store,ev,plan,catalog=fixture('A run used 5 calls. Another run used 5 calls.')
    assert len(catalog.value_ids['E1'])==2
    assert len(set(catalog.value_ids['E1']))==2


def test_no_generated_value_or_unknown_optional_label_can_replace_source():
    store,ev,plan,catalog=fixture()
    rows=[{'anchor_ids':list(catalog.by_evidence['E1']),'obligation_ids':['a1'],
           'value_ids':['V_invented'],'values':['999 calls'],'method_id':'invented method',
           'experiment_id':'invented experiment','mode':'unknown','metric':[] }]
    records,audit=parse_id_records(rows,ev,plan,[],catalog)
    assert len(records)==1 and records[0].method is None and records[0].experiment is None
    assert records[0].values==[catalog.anchors[v].text for v in records[0].value_ids]
    assert '999 calls' not in records[0].values
    assert not audit['rejections'] and audit['warnings']


def test_invented_primary_anchor_is_still_rejected():
    store,ev,plan,catalog=fixture()
    records,audit=parse_id_records([{'anchor_ids':['A_invented'],'obligation_ids':['a1']}],ev,plan,[],catalog)
    assert not records and audit['rejections'][0]['reason']=='invalid_source_anchor'


def test_cross_document_anchor_mix_is_rejected():
    store=MemoryStore({'a':['Method A used 15 calls.'],'b':['Method B used 20 calls.']})
    ev={f'E{i}':Evidence(e,['a1']) for i,e in enumerate(store.elements)};catalog=SourceCatalog(ev)
    plan=QueryPlan('analytical',[Aspect('a1','cost',['cost'])],['a','b'])
    ids=[catalog.by_evidence[eid][0] for eid in ev]
    records,audit=parse_id_records([{'anchor_ids':ids,'obligation_ids':['a1']}],ev,plan,[],catalog)
    assert not records and audit['rejections'][0]['reason']=='mixed_document_anchor'


def test_id_writer_cannot_modify_values_units_or_add_prose(tmp_path):
    store,ev,plan,catalog=fixture()
    def respond(name,p):
        assert name=='answer'  # No standalone ledger extraction call.
        record=p['records'][0]
        assert record['values'][0]['id'].startswith('V')
        return {'selections':[{'record_ids':[record['id']],'anchor_ids':list(record['anchors']),
                              'text':'The method used 999 calls.'}]}
    draft=generate_answer(FakeLLM(respond),'accuracy and cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert '12,000' in draft.claims[0].text and '0.05%' in draft.claims[0].text
    assert '999' not in draft.claims[0].text
    assert draft.claims[0].quotes[0]['quote']==store.elements[0].text


def test_value_or_qualification_omission_gets_exact_source_fallback(tmp_path):
    store,ev,plan,catalog=fixture('The reported runtime was 5 seconds. This estimate applies only inside the tested domain.')
    ids=list(catalog.by_evidence['E1'])
    ev['E1'].findings=[{'anchor_ids':[ids[0]],'qualification_ids':[ids[1]],'obligation_ids':['a1']}]
    def respond(n,p):
        r=p['records'][0]
        return {'selections':[{'record_ids':[r['id']],'anchor_ids':[ids[0]]}]}
    draft=generate_answer(FakeLLM(respond),'cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert 'only inside the tested domain' in draft.claims[0].text
    assert len(draft.claims[0].quotes)==2 and draft.status=='partial'


def test_table_values_keep_source_header_and_exact_row(tmp_path):
    from dataclasses import replace
    store,ev,plan,_=fixture('| Method | Cost (USD) |\n| --- | --- |\n| Direct | 500 |\n| TT | 20 |')
    ev['E1'].element=replace(ev['E1'].element,kind='table')
    catalog=SourceCatalog(ev);ids=list(catalog.by_evidence['E1'])
    assert catalog.anchors[ids[0]].kind=='table_header'
    ev['E1'].findings=[{'anchor_ids':[ids[1]],'obligation_ids':['a1']}]
    draft=generate_answer(FakeLLM(lambda n,p:{'selections':[]}), 'cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert 'Cost (USD)' in draft.claims[0].text and '| Direct | 500 |' in draft.claims[0].text
    assert '| TT | 20 |' not in draft.claims[0].text


def test_integrated_verification_selects_stable_anchors_in_the_existing_call(tmp_path):
    store,ev,plan,catalog=fixture()
    def respond(n,p):
        assert n=='verify' and p['finding_contract']=='source_ids_v2'
        e=p['elements'][0]
        assert all(a.startswith('A') for a in e['source_spans'])
        return {'keep':[{'id':e['id'],'aspects':['a1'],'support_span_ids':list(e['source_spans']),
                         'value_ids':['V_invalid'],'method_id':'unknown'}]}
    llm=FakeLLM(respond);cfg=settings(tmp_path,analytical_writer_mode='ledger')
    evidence,report=verify_elements(llm,store,plan,'cost',[Candidate(store.elements[0],['a1'],['fts'])],cfg)
    assert len(evidence)==1 and evidence[0].findings
    numbered={'E99':evidence[0]}
    records,audit=integrated_records(numbered,plan,[])
    assert len(records)==1 and '12 _,_ 000 calls' in records[0].values
    assert not audit['rejections']
    assert [n for n,p in llm.calls]==['verify']


def test_qualification_evidence_is_bundled_under_the_same_budget(tmp_path):
    store=MemoryStore({'d':['Cost was 12 calls.\n\nOnly inside the tested domain.']})
    assert len(store.elements)==2
    parent=Evidence(store.elements[0],['a1'],dependencies=[store.elements[1].element_id])
    child=Evidence(store.elements[1],['a1'],relevance='qualification')
    plan=QueryPlan('analytical',[Aspect('a1','cost',['cost'])],['d'])
    cfg=settings(tmp_path,analytical_writer_mode='ledger')
    selected,report=select_portfolio([parent,child],plan,cfg,cap=300)
    assert parent not in selected
    selected,report=select_portfolio([parent,child],plan,cfg,cap=1000)
    assert parent in selected and child in selected
    assert report['input_budget_units']<=1000


@pytest.mark.parametrize('changed,source',[
    ('0 . 05%','0 _._ 05%'),('40 , 000 times','40 _,_ 000 times'),
    ('7 . 2 hours','7 _._ 2 hours'),('0 . 6 seconds','0 _._ 6 seconds')])
def test_legacy_format_adapter_is_punctuation_only(changed,source):
    assert source_format_key(changed)==source_format_key(source)
    assert source_format_key(changed)!=source_format_key(('9' if source[0]!='9' else '8')+source[1:])


def test_qualification_in_other_element_is_retained_with_its_parent(tmp_path):
    store=MemoryStore({'d':['Runtime was 5 seconds.\n\nOnly inside the tested domain.']})
    plan=QueryPlan('analytical',[Aspect('a1','runtime',['runtime'])],['d'])
    def respond(n,p):
        parent,child=p['elements']
        return {'keep':[{'id':parent['id'],'aspects':['a1'],
            'support_span_ids':list(parent['source_spans']),
            'qualification_ids':list(child['source_spans'])}]}
    cfg=settings(tmp_path,analytical_writer_mode='ledger')
    evidence,report=verify_elements(FakeLLM(respond),store,plan,'runtime',
        [Candidate(e,['a1'],['fts']) for e in store.elements],cfg)
    assert len(evidence)==2
    parent=next(e for e in evidence if e.dependencies)
    assert parent.dependencies==[store.elements[1].element_id]
    numbered={f'E{i}':e for i,e in enumerate(evidence)}
    draft=generate_answer(FakeLLM(lambda n,p:{'selections':[]}), 'runtime',plan,numbered,{},cfg)
    assert any('Only inside the tested domain.' in c.text and '5 seconds' in c.text for c in draft.claims)


def test_integrated_full_query_keeps_ten_stages_without_extra_extraction_call(tmp_path):
    from kb.query.pipeline import answer_query,STEP_NAMES
    from kb.query.observability import LocalSink
    store=MemoryStore({'d':['Accuracy error was 0 _._ 05%.\n\nBuild cost was 200 calls.']})
    def respond(n,p):
        if n=='answer' and 'records' in p:
            return {'selections':[{'record_ids':[r['id']],'anchor_ids':list(r['anchors'])} for r in p['records']]}
        return FakeLLM.default(n,p)
    llm=FakeLLM(respond)
    response=answer_query('demo','accuracy and build cost',store=store,generation_id='g',
        settings=settings(tmp_path,analytical_writer_mode='ledger'),llm=llm,sink=LocalSink())
    assert [t['step_name'] for t in response['trace']]==STEP_NAMES
    assert [n for n,p in llm.calls]==['plan','verify','answer','answer_verify']
    assert '0.05%' in response['answer'] and '200 calls' in response['answer']
    assert all(q['content'] in [e.text for e in store.elements] for q in response['chunks'])


def test_unknown_qualification_does_not_delete_finding_or_claim_completeness(tmp_path):
    store,ev,plan,catalog=fixture('The reported runtime was 5 seconds.')
    ev['E1'].findings=[{'anchor_ids':list(catalog.by_evidence['E1']),
                      'obligation_ids':['a1'],'qualification_ids':['A_missing']}]
    draft=generate_answer(FakeLLM(lambda n,p:{'selections':[]}), 'cost',plan,ev,{},settings(tmp_path,analytical_writer_mode='ledger'))
    assert draft.claims and '5 seconds' in draft.claims[0].text
    assert draft.status=='partial' and any('qualification' in l for l in draft.limitations)
