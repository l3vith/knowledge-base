from kb.query.answer import generate_answer, verify_calculation, number_evidence
from kb.query.types import Aspect, QueryPlan, Evidence
from .helpers import MemoryStore, FakeLLM, settings


def draft(tmp_path,statements,pages=None):
    store=MemoryStore(pages or {"a":["The build used 10 _,_ 000 calls. The grid had 117 _,_ 649 points. The surrogate cannot extrapolate."]})
    numbered=number_evidence([Evidence(e,["a1"]) for e in store.elements])
    plan=QueryPlan("analytical",[Aspect("a1","cost",["cost"])],[c.doc_id for c in store.docs()])
    llm=FakeLLM(lambda n,p:{"status":"answered","sections":[{"heading":"Findings","statements":statements}]})
    return generate_answer(llm,"what controls and what cost?",plan,numbered,{c.doc_id:c for c in store.docs()},
                           settings(tmp_path,analytical_writer_mode="synthesis"))


def test_interpretations_gaps_and_calculations_are_labelled_and_checked(tmp_path):
    cite=[{"evidence_id":"E1","span_ids":["S3"]}]
    calc={"operation":"percentage","operands":[{"evidence_id":"E1","span_id":"S1","value":"10000","unit":"calls"},
          {"evidence_id":"E1","span_id":"S2","value":"117649","unit":"points"}],"result":"8.5","unit":"%","decimals":1}
    d=draft(tmp_path,[{"kind":"inference","text":"Enforce a domain check with a fallback to the full model.","obligation_ids":["a1"],"cites":cite},
                      {"kind":"gap","text":"No out-of-domain error is quantified.","obligation_ids":["a1"],"cites":[]},
                      {"kind":"calculation","text":"The 10,000 calls are 8.5% of the 117,649-point grid.","obligation_ids":["a1"],
                       "cites":[{"evidence_id":"E1","span_ids":["S1","S2"]}],"calculation":calc}])
    texts=[c.text for c in d.claims]
    assert texts[0].startswith("Interpretation: ") and texts[1].startswith("Not shown in the inspected evidence: ")
    assert texts[2].startswith("Calculated: ")
    numbered={"E1":Evidence(MemoryStore({"a":["The build used 10 _,_ 000 calls. The grid had 117 _,_ 649 points. The surrogate cannot extrapolate."]}).elements[0],["a1"])}
    assert verify_calculation(d.claims[2].calculation,numbered)  # markdown commas and stated rounding both handled
    wrong=dict(d.claims[2].calculation,result="9.1")
    assert not verify_calculation(wrong,numbered)


def test_same_figure_from_two_documents_is_not_a_duplicate(tmp_path):
    pages={"a":["Bank A ratio was 14 percent."],"b":["Bank B ratio was 14 percent."]}
    d=draft(tmp_path,[{"kind":"finding","text":"The ratio was 14 percent.","obligation_ids":["a1"],"cites":[{"evidence_id":"E1","span_ids":["S1"]}]},
                      {"kind":"finding","text":"The ratio was 14 percent.","obligation_ids":["a1"],"cites":[{"evidence_id":"E2","span_ids":["S1"]}]},
                      {"kind":"finding","text":"The ratio was 14 percent.","obligation_ids":["a1"],"cites":[{"evidence_id":"E2","span_ids":["S1"]}]}],pages)
    assert len(d.claims)==2
