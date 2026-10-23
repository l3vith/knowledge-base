import pytest
from kb.query.answer import generate_answer,verify_answer,render_verified,number_evidence,verify_calculation
from kb.query.types import QueryPlan,Aspect,Evidence
from .helpers import MemoryStore,FakeLLM,settings as _settings


def settings(tmp_path,**kw):
    # These tests cover the extractive writer; synthesis tests pass analytical_writer_mode="synthesis".
    return _settings(tmp_path,**{"analytical_writer_mode":"extractive",**kw})


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


def test_factoid_answer_keeps_only_the_clause_with_the_verified_value(tmp_path):
    text=("The implementation of the pricing routine used is based on the one mentioned in [2], available\non github "
          "and implemented in C++. <sup>5</sup> It is a Monte Carlo based pricing routine; 60 _,_ 000 paths were\n"
          "used to generate the prices in our tests. Once prices are obtained, these are turned into implied\nvolatilities.")
    store=MemoryStore({"a":[text]})
    numbered=number_evidence([Evidence(store.elements[0],["a1"],fact_value="60 _,_ 000 paths")])
    plan=QueryPlan("factoid",[Aspect("a1","paths",["paths"])],["a"])
    llm=FakeLLM(lambda n,p:{"status":"answered","selections":[{"obligation_id":"a1","evidence_id":"E1","span_ids":["S1","S2"]}]})
    draft=generate_answer(llm,"How many Monte Carlo paths were used?",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    # The clause naming the query's subject (Monte Carlo routine) stays; the earlier sentence does not.
    assert [c.text for c in draft.claims]==["It is a Monte Carlo based pricing routine; 60,000 paths were\nused to generate the prices in our tests."]
    assert draft.claims[0].quotes[0]["quote"] in text
    draft=generate_answer(llm,"How many paths were used?",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    assert [c.text for c in draft.claims]==["60,000 paths were\nused to generate the prices in our tests."]



def test_long_selection_keeps_the_four_most_numeric_sentences(tmp_path):
    text="Intro one. Background two. Errors fall within 0.05% and 0.35%. Max error 5%. Build took 5 minutes. Outlook ends."
    store=MemoryStore({"a":[text]})
    numbered=number_evidence([Evidence(store.elements[0],["a1"])])
    plan=QueryPlan("analytical",[Aspect("a1","errors",["error"])],["a"])
    llm=FakeLLM(lambda n,p:{"status":"answered","selections":[{"obligation_id":"a1","evidence_id":"E1","span_ids":["S1","S2","S3","S4","S5","S6"]}]})
    draft=generate_answer(llm,"explain the errors",plan,numbered,{"a":store.doc("a")},settings(tmp_path))
    assert draft.claims[0].text=="Background two. Errors fall within 0.05% and 0.35%. Max error 5%. Build took 5 minutes."


def synth(tmp_path,statements,text="Capital was 12 million USD in FY2025. Buffers rose to 3 percent."):
    store=MemoryStore({"a":[text]})
    numbered=number_evidence([Evidence(store.elements[0],["a1"])])
    plan=QueryPlan("analytical",[Aspect("a1","capital",["capital"])],["a"])
    llm=FakeLLM(lambda n,p:{"status":"answered","sections":[{"heading":"Capital","statements":statements}]} if n=="answer"
                else FakeLLM.default(n,p))
    s=settings(tmp_path,analytical_writer_mode="synthesis")
    draft=generate_answer(llm,"assess capital",plan,numbered,{"a":store.doc("a")},s)
    checked,report=verify_answer(llm,draft,numbered,s)
    return draft,checked,report,render_verified(checked,numbered,{"a":store.doc("a")})[0]


def test_synthesis_statement_gets_exact_source_quotes_and_a_cited_bullet(tmp_path):
    draft,checked,_,answer=synth(tmp_path,[{"kind":"finding","text":"Capital was USD 12 million in FY2025.",
                                             "obligation_ids":["a1"],"cites":[{"evidence_id":"E1","span_ids":["S1"]}]}])
    assert draft.claims[0].quotes==[{"evidence_id":"E1","quote":"Capital was 12 million USD in FY2025. "}]
    assert answer=="## Capital\n- Capital was USD 12 million in FY2025. [a.pdf p1]"


def test_synthesis_rejects_uncited_or_invented_citations_but_keeps_gaps(tmp_path):
    draft,checked,report,answer=synth(tmp_path,[
        {"kind":"finding","text":"Invented fact.","cites":[]},
        {"kind":"finding","text":"Bad span.","cites":[{"evidence_id":"E1","span_ids":["S9"]}]},
        {"kind":"inference","text":"Unknown source.","cites":[{"evidence_id":"E7","span_ids":["S1"]}]},
        {"kind":"gap","text":"The excerpts do not show the 2024 figure.","obligation_ids":["a1"]}])
    assert [c.kind for c in checked.claims]==["gap"] and report["gaps"]==1
    assert answer=="## Capital\n- The excerpts do not show the 2024 figure."


def test_synthesis_claims_the_checker_rejects_are_removed(tmp_path):
    store_text="Capital was 12 million USD in FY2025."
    store=MemoryStore({"a":[store_text]})
    numbered=number_evidence([Evidence(store.elements[0],["a1"])])
    plan=QueryPlan("analytical",[Aspect("a1","capital",["capital"])],["a"])
    def respond(n,p):
        if n=="answer":
            return {"status":"answered","sections":[{"heading":"Capital","statements":[
                {"kind":"finding","text":"Capital was USD 12 million.","cites":[{"evidence_id":"E1","span_ids":["S1"]}]},
                {"kind":"inference","text":"Capital will double next year.","cites":[{"evidence_id":"E1","span_ids":["S1"]}]}]}]}
        assert all("kind" in c for c in p["claims"])
        return {"verdicts":[{"claim_id":"c1","verdict":"supported"},{"claim_id":"c2","verdict":"unsupported"}]}
    s=settings(tmp_path,analytical_writer_mode="synthesis")
    draft=generate_answer(FakeLLM(respond),"assess capital",plan,numbered,{"a":store.doc("a")},s)
    checked,report=verify_answer(FakeLLM(respond),draft,numbered,s)
    assert [c.text for c in checked.claims]==["Capital was USD 12 million."] and report["rejected"]==1


def test_narrow_factoid_stays_extractive_under_synthesis(tmp_path):
    store=MemoryStore({"a":["Coverage was 178.4% in 2025."]})
    numbered=number_evidence([Evidence(store.elements[0],["a1"],fact_value="178.4%")])
    plan=QueryPlan("factoid",[Aspect("a1","coverage",["coverage"])],["a"])
    llm=FakeLLM(lambda n,p:(_ for _ in ()).throw(AssertionError("synthesis used")) if "max_statements" in p else
                {"status":"answered","selections":[{"obligation_id":"a1","evidence_id":"E1","span_ids":["S1"]}]})
    draft=generate_answer(llm,"What was the coverage ratio?",plan,numbered,{"a":store.doc("a")},settings(tmp_path,analytical_writer_mode="synthesis"))
    assert draft.claims[0].text=="Coverage was 178.4% in 2025."


def test_synthesis_writes_each_obligation_group_in_parallel_with_its_own_evidence(tmp_path):
    store=MemoryStore({"a":["Capital was 12 million USD.","Liquidity was 140 percent."]})
    numbered=number_evidence([Evidence(store.elements[0],["a1"]),Evidence(store.elements[1],["a2"])])
    plan=QueryPlan("analytical",[Aspect("a1","capital",["capital"]),Aspect("a2","liquidity",["liquidity"])],["a"])
    seen=[]
    def respond(n,p):
        if n!="answer": return FakeLLM.default(n,p)
        seen.append(([e["id"] for e in p["evidence"]],p["short_answer"],p["role"]))
        e=p["evidence"][0]
        st={"kind":"finding","text":"Same sentence.","cites":[{"evidence_id":e["id"],"span_ids":["S1"]}]}
        return {"status":"answered","sections":[{"heading":p["obligations"][0]["text"],"statements":[
            {**st,"text":e["source_spans"]["S1"]},st]}]}
    draft=generate_answer(FakeLLM(respond),"assess capital and liquidity",plan,numbered,{"a":store.doc("a")},settings(tmp_path,analytical_writer_mode="synthesis"))
    assert sorted(seen)==[(["E1"],True,"findings"),(["E1","E2"],False,"appraisal"),(["E2"],False,"findings")]
    assert [c.text for c in draft.claims].count("Same sentence.")==1 and len(draft.claims)==3
