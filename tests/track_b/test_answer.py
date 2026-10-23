import pytest
from kb.query.answer import generate_answer,verify_answer,render_verified,number_evidence,verify_calculation
from kb.query.types import QueryPlan,Aspect,Evidence
from .helpers import MemoryStore,FakeLLM,settings


def fixture():
    store=MemoryStore({"a":["Capital was 12 million USD in FY2025."]})
    numbered=number_evidence([Evidence(store.elements[0],["a1"])])
    plan=QueryPlan("analytical",[Aspect("a1","capital",["capital"])],["a"])
    return store,numbered,plan


def test_unknown_evidence_rejects_whole_claim(tmp_path):
    store,numbered,plan=fixture()
    llm=FakeLLM(lambda n,p:{"claims":[{"text":"Unsupported assertion","evidence_ids":["E99"],"aspect_ids":["a1"],"quotes":[]}]})
    draft=generate_answer(llm,"capital",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    assert not draft.claims and draft.limitations


def test_semantic_review_removes_unsupported_whole_claim(tmp_path):
    store,numbered,plan=fixture()
    def respond(n,p):
        if n=="answer_verify": return {"verdicts":[{"claim_id":"c1","verdict":"unsupported"}]}
        return FakeLLM.default(n,p)
    llm=FakeLLM(respond)
    draft=generate_answer(llm,"capital",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    checked,report=verify_answer(llm,draft,numbered,settings(tmp_path))
    answer,_=render_verified(checked,numbered,{"a":store.doc("a")})
    assert report["rejected"]==1 and "12 million" not in answer


def test_citations_come_from_actual_source(tmp_path):
    store,numbered,plan=fixture();llm=FakeLLM()
    draft=generate_answer(llm,"capital",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    checked,_=verify_answer(llm,draft,numbered,settings(tmp_path))
    answer,_=render_verified(checked,numbered,{"a":store.doc("a")})
    assert "[a.pdf p1]" in answer and "[E1]" not in answer


def test_duplicate_verdicts_are_not_accepted(tmp_path):
    store,numbered,plan=fixture()
    llm=FakeLLM(lambda n,p:{"verdicts":[{"claim_id":"c1","verdict":"supported"}]*2} if n=="answer_verify" else FakeLLM.default(n,p))
    draft=generate_answer(llm,"capital",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    checked,_=verify_answer(llm,draft,numbered,settings(tmp_path))
    assert not checked.claims


@pytest.mark.parametrize("operation,unit,result,expected",[("add","USD",24,True),("add","EUR",24,False),("divide","ratio",1,True),("divide","USD",1,False),("multiply","USD",144,False)])
def test_calculation_requires_supported_operands_and_units(operation,unit,result,expected):
    store,numbered,_=fixture()
    operand={"value":12,"unit":"USD","evidence_id":"E1","quote":store.elements[0].text}
    calc={"operation":operation,"operands":[operand,operand],"result":result,"unit":unit}
    assert verify_calculation(calc,numbered) is expected


def test_calculation_rejects_invented_operand():
    store,numbered,_=fixture()
    operand={"value":999,"unit":"USD","evidence_id":"E1","quote":store.elements[0].text}
    assert not verify_calculation({"operation":"add","operands":[operand,operand],"result":1998,"unit":"USD"},numbered)


def test_malformed_claim_identifier_is_rejected(tmp_path):
    store,numbered,plan=fixture()
    llm=FakeLLM(lambda n,p:{"claims":[{"text":"bad","evidence_ids":[[]],"aspect_ids":None,"quotes":None}],"limitations":None})
    draft=generate_answer(llm,"capital",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    assert not draft.claims and draft.limitations


def test_extractive_selections_copy_exact_source_and_require_obligation(tmp_path):
    store,numbered,plan=fixture()
    def respond(name,payload):
        if name=='answer':
            assert 'source_spans' in payload['evidence'][0] and 'content' not in payload['evidence'][0]
            return {'status':'answered','selections':[{'obligation_id':'a1','evidence_id':'E1','span_ids':['S1'],
                                                     'text':'Invented capital of 99 million.'}]}
        return FakeLLM.default(name,payload)
    draft=generate_answer(FakeLLM(respond),'capital',plan,numbered,{},settings(tmp_path))
    assert draft.claims[0].text==store.elements[0].text
    assert draft.claims[0].quotes==[{'evidence_id':'E1','quote':store.elements[0].text}]
    assert draft.claims[0].aspect_ids==['a1']


@pytest.mark.parametrize('row',[
    {'obligation_id':'','evidence_id':'E1','span_ids':['S1']},
    {'obligation_id':'unknown','evidence_id':'E1','span_ids':['S1']},
    {'obligation_id':'a1','evidence_id':'E1','span_ids':['S999']},
    {'obligation_id':['a1'],'evidence_id':'E1','span_ids':['S1']},
])
def test_extractive_invalid_selection_cannot_become_claim(tmp_path,row):
    store,numbered,plan=fixture()
    draft=generate_answer(FakeLLM(lambda n,p:{'selections':[row]}),'capital',plan,numbered,{},settings(tmp_path))
    assert not draft.claims and draft.limitations
    answer,_=render_verified(draft,numbered,{'a':store.doc('a')})
    assert 'no answer claims passed source validation' in answer
    assert 'No supporting information was found' not in answer


def test_legacy_adapter_cannot_paraphrase_a_source(tmp_path):
    store,numbered,plan=fixture()
    row={'text':'The bank had a capital base of 12 million USD.','evidence_ids':['E1'],'aspect_ids':['a1'],
         'quotes':[{'evidence_id':'E1','quote':store.elements[0].text}]}
    draft=generate_answer(FakeLLM(lambda n,p:{'claims':[row]}),'capital',plan,numbered,{},settings(tmp_path))
    assert not draft.claims


def test_display_number_cleanup_preserves_raw_support(tmp_path):
    from kb.query.types import Evidence
    store=MemoryStore({'a':['The simulation used 12 _,_ 000 trials in the tests.']})
    numbered=number_evidence([Evidence(store.elements[0],['a1'])])
    plan=QueryPlan('factoid',[Aspect('a1','trials',['trials'])],['a'])
    draft=generate_answer(FakeLLM(),'trials',plan,numbered,{},settings(tmp_path))
    assert draft.claims[0].text=='The simulation used 12,000 trials in the tests.'
    assert draft.claims[0].quotes[0]['quote']==store.elements[0].text


def test_nonconsecutive_span_selection_is_rejected(tmp_path):
    store=MemoryStore({'a':['Capital increased. The result excludes losses. Reporting changed.']})
    numbered=number_evidence([Evidence(store.elements[0],['a1'])])
    plan=QueryPlan('analytical',[Aspect('a1','capital',['capital'])],['a'])
    row={'obligation_id':'a1','evidence_id':'E1','span_ids':['S1','S3']}
    draft=generate_answer(FakeLLM(lambda n,p:{'selections':[row]}),'capital',plan,numbered,{},settings(tmp_path))
    assert not draft.claims
