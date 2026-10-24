from dataclasses import replace
from kb.query.worksheet import compile_tasks, bind_results
from kb.query.types import Aspect, QueryPlan, Evidence, Candidate, AnswerDraft, Claim
from kb.query.answer import generate_answer, verify_answer, source_spans
from kb.query.screen import verify_elements
from kb.query.pipeline import answer_query
from kb.query.candidates import source_acronyms
from .helpers import MemoryStore, FakeLLM, settings


def task_plan(query, operation='assess'):
    aspects=[Aspect('a1',query,[query])]
    tasks=compile_tasks(query,aspects,[{'operation':operation,'description':query,'query_anchor':query,
                                     'obligation_ids':['a1'],'source_roles':[query]}])
    return QueryPlan('analytical',aspects,['d'],tasks=tasks)


def test_task_compiler_rejects_nonquery_anchor_and_unknown_obligation():
    q='Assess the data split'
    tasks=compile_tasks(q,[Aspect('a1',q,[])],[{'query_anchor':'external control checklist','operation':'assess',
                 'obligation_ids':['invented'],'source_roles':['external data']}])
    assert len(tasks)==1 and tasks[0]['query_anchor']==q and tasks[0]['obligation_ids']==['a1']


def test_advisory_inventory_allows_qualitative_finding_and_no_mandatory_restoration(tmp_path):
    store=MemoryStore({'d':['Zero changes fall in the otherwise branch.','Training took 12 seconds.']})
    ev={f'E{i+1}':Evidence(e,['a1']) for i,e in enumerate(store.elements)}
    plan=task_plan('Assess target definition')
    def respond(n,p):
        if n=='answer':
            assert len(p['evidence'])==2 and p['role']=='task_worksheet'
            return {'sections':[{'heading':'Target','statements':[{'kind':'finding','text':store.elements[0].text,
                'obligation_ids':['a1'],'cites':[{'evidence_id':'E1','span_ids':['S1']}]}]}],
                'task_results':[{'task_id':'T1','status':'supported','inputs':[{'evidence_id':'E1','span_id':'S1'}]}]}
        return {'verdicts':[{'claim_id':c['claim_id'],'verdict':'supported'} for c in p['claims']],
                'coverage':[{'requirement_id':'T1','status':'supported','claim_ids':['c1']}]}
    draft=generate_answer(FakeLLM(respond),plan.aspects[0].text,plan,ev,{},settings(tmp_path,analytical_writer_mode='synthesis'))
    assert [c.text for c in draft.claims]==[store.elements[0].text]
    checked,_=verify_answer(FakeLLM(respond),draft,ev,settings(tmp_path),query=plan.aspects[0].text)
    assert len(checked.claims)==1 and checked.worksheet[0]['completion']=='supported'


def test_unsupported_claim_outside_inventory_is_not_resurrected_after_check(tmp_path):
    store=MemoryStore({'d':['The study uses one exchange.']});ev={'E1':Evidence(store.elements[0],['a1'])}
    plan=task_plan('Assess generalisation')
    def respond(n,p):
        if n=='answer':return {'sections':[{'heading':'Scope','statements':[{'kind':'finding','text':'It works on all exchanges.',
            'obligation_ids':['a1'],'cites':[{'evidence_id':'E1','span_ids':['S1']}]}]}]}
        return {'verdicts':[{'claim_id':'c1','verdict':'unsupported'}]}
    draft=generate_answer(FakeLLM(respond),'Assess generalisation',plan,ev,{},settings(tmp_path,analytical_writer_mode='synthesis'))
    checked,_=verify_answer(FakeLLM(respond),draft,ev,settings(tmp_path))
    assert not checked.claims


def test_explanation_does_not_stop_recovery_but_direct_numeric_answer_does(tmp_path):
    store=MemoryStore({'d':['\n\n'.join(['Impact depends on circumstances.']*8+['The total is 42 percent.']*32)]})
    plan=QueryPlan('factoid',[Aspect('a1','What percentage?',[])],['d'])
    calls=[]
    def respond(n,p):
        calls.append(p)
        e=p['elements'][0]
        return {'keep':[{'id':e['id'],'aspects':['a1'],'support_span_ids':['S1'],
                        'relevance':'explanation' if len(calls)==1 else 'direct',
                        'fact_value':None if len(calls)==1 else '42 percent'}]}
    evidence,report=verify_elements(FakeLLM(respond),store,plan,'What percentage?',
                         [Candidate(e,['a1'],[]) for e in store.elements],settings(tmp_path))
    assert len(calls)==2 and len(evidence)==2
    assert report['elements_seen']==16 and report['remaining_candidates']==24
    assert report['direct_answer_found'] and report['recovery_batches']==0


def test_zero_hit_recovery_is_bounded_and_keeps_only_verified_explanation(tmp_path):
    text='\n\n'.join(['No answer here.']*16+['Impact cannot be forecast.']+['Other material.']*30)
    store=MemoryStore({'d':[text]});plan=QueryPlan('factoid',[Aspect('a1','What percentage?',[])],['d'])
    calls=[]
    def respond(n,p):
        calls.append(p)
        return {'keep':[{'id':e['id'],'aspects':['a1'],'support_span_ids':['S1'],'relevance':'counterevidence'}
                        for e in p['elements'] if 'cannot' in e['source_spans']['S1']]}
    ev,report=verify_elements(FakeLLM(respond),store,plan,'What percentage?',
                   [Candidate(e,['a1'],[]) for e in store.elements],settings(tmp_path))
    assert len(calls)==4 and report['recovery_batches']==2 and len(ev)==1
    assert report['elements_seen']==32 and report['remaining_candidates']==15
    assert ev[0].relevance=='counterevidence' and not ev[0].fact_value


def test_factual_explanation_uses_checked_analyst_writer_instead_of_numeric_clipping(tmp_path):
    store=MemoryStore({'d':['The impact varies and cannot be forecast.']})
    plan=task_plan('What percentage?',operation='lookup');plan.intent='factoid'
    ev={'E1':Evidence(store.elements[0],['a1'],relevance='explanation')}
    draft=generate_answer(FakeLLM(),'What percentage?',plan,ev,{},settings(tmp_path,analytical_writer_mode='synthesis'))
    assert draft.worksheet and draft.claims[0].text==store.elements[0].text


def test_comparison_scope_must_be_known_and_compatible():
    store=MemoryStore({'d':['Acme revenue 2024 USD standalone: 10.','Acme revenue 2025 USD standalone: 10.']})
    ev={'E1':Evidence(store.elements[0],['a1']),'E2':Evidence(store.elements[1],['a1'])}
    tasks=task_plan('Check consistency across sections','compare').tasks
    inputs=[{'evidence_id':eid,'span_id':'S1','scope':{'entity':'Acme','metric':'revenue','period':year,'unit':'USD','basis':'standalone'}}
            for eid,year in [('E1','2024'),('E2','2025')]]
    row={'task_id':'T1','status':'contradicted','inputs':inputs}
    bound=bind_results(tasks,[row],ev,source_spans(ev))[0]
    assert bound['status']=='incomparable' and bound['scope_status']=='incomparable'
    inputs[1]['scope']['period']='2024'  # this invented scope string is absent from its source
    bound=bind_results(tasks,[row],ev,source_spans(ev))[0]
    assert bound['status']=='unresolved' and 'period' in bound['missing_inputs']
    store.elements[1].text='Acme revenue 2024 USD standalone: 11.'
    bound=bind_results(tasks,[row],ev,source_spans(ev))[0]
    assert bound['scope_status']=='comparable' and bound['status']=='contradicted'
    assert bound['inputs'][0]['char_start']==0 and bound['inputs'][0]['quote']==store.elements[0].text


def test_faithful_assurance_does_not_complete_a_reconciliation(tmp_path):
    store=MemoryStore({'d':['The auditor issued an assurance.']});ev={'E1':Evidence(store.elements[0],['a1'])}
    tasks=task_plan('Reconcile the statements','reconcile').tasks
    worksheet=bind_results(tasks,[],ev,source_spans(ev))
    draft=AnswerDraft([Claim('c1',store.elements[0].text,['E1'],['a1'])],'answered',
                      requested_topics=[{'id':'T1','text':'Reconcile the statements'}],worksheet=worksheet)
    def respond(n,p):
        assert p['task_worksheet']
        return {'verdicts':[{'claim_id':'c1','verdict':'supported'}],
                'coverage':[{'requirement_id':'T1','status':'partial','claim_ids':['c1']}]}
    checked,_=verify_answer(FakeLLM(respond),draft,ev,settings(tmp_path))
    assert checked.claims and checked.worksheet[0]['completion']=='unresolved' and checked.status=='partial'


def test_source_acronym_alternatives_are_sourced_and_bounded():
    store=MemoryStore({'d':['The expected credit loss (ECL) method differs from estimated credit loss (ECL).']})
    hints=source_acronyms('Explain expected credit loss',store.elements)
    assert 'ECL' in hints and len(hints)<=12
    assert not source_acronyms('What is the weather?',store.elements)


def test_unresolved_scope_blocks_calculation_before_semantic_checker(tmp_path):
    store=MemoryStore({'d':['Revenue was 10 USD in 2024.','Revenue was 20 USD in 2025.']})
    ev={f'E{i+1}':Evidence(e,['a1']) for i,e in enumerate(store.elements)}
    calc={'operation':'subtract','operands':[{'evidence_id':'E2','quote':store.elements[1].text,'value':'20','unit':'USD'},
          {'evidence_id':'E1','quote':store.elements[0].text,'value':'10','unit':'USD'}],'result':'10','unit':'USD'}
    claim=Claim('c1','Calculated: 20 - 10 = 10 USD',['E1','E2'],['a1'],calculation=calc,requirement_ids=['T1'])
    worksheet=bind_results(task_plan('Check consistency across sections','compare').tasks,[],ev,source_spans(ev))
    checked,report=verify_answer(FakeLLM(lambda n,p: (_ for _ in ()).throw(AssertionError('must fail before call'))),
        AnswerDraft([claim],'answered',worksheet=worksheet),ev,settings(tmp_path))
    assert not checked.claims and report['rejected']==1


def test_one_source_core_repair_is_rechecked_and_never_loops(tmp_path):
    store=MemoryStore({'d':['Testing used one exchange.']});ev={'E1':Evidence(store.elements[0],['a1'])}
    task=task_plan('Assess testing scope').tasks
    worksheet=bind_results(task,[{'task_id':'T1','status':'supported','inputs':[{'evidence_id':'E1','span_id':'S1'}]}],ev,source_spans(ev))
    claim=Claim('c1','The experiment proves universal accuracy.',['E1'],['a1'],
                [{'evidence_id':'E1','quote':store.elements[0].text}],requirement_ids=['T1'])
    calls=[]
    def respond(n,p):
        calls.append(p)
        if len(calls)==1:return {'verdicts':[{'claim_id':'c1','verdict':'unsupported','relevance':'direct',
                                              'reason_code':'unsupported_phrase','repair_quote_indexes':[0]}]}
        assert p['source_core_repair'] and p['claims'][0]['text']==store.elements[0].text
        return {'verdicts':[{'claim_id':'c2','verdict':'supported','relevance':'direct'}]}
    checked,report=verify_answer(FakeLLM(respond),AnswerDraft([claim],'answered',worksheet=worksheet),ev,settings(tmp_path))
    assert len(calls)==2 and [c.text for c in checked.claims]==[store.elements[0].text]
    assert report['source_core_repair']=={'attempted':1,'accepted':1,'calls':1}


def test_source_core_repair_budget_denial_preserves_original_valid_claims(tmp_path):
    from kb.query.errors import BudgetExceeded
    store=MemoryStore({'d':['Testing used one exchange.']});ev={'E1':Evidence(store.elements[0],['a1'])}
    worksheet=bind_results(task_plan('Assess testing scope').tasks,[],ev,source_spans(ev))
    claim=Claim('c1','An unsupported embellishment.',['E1'],['a1'],[{'evidence_id':'E1','quote':store.elements[0].text}])
    calls=[]
    def respond(n,p):
        calls.append(p)
        if len(calls)>1:raise BudgetExceeded('spend cap')
        return {'verdicts':[{'claim_id':'c1','verdict':'unsupported','relevance':'direct',
                            'reason_code':'unsupported_phrase','repair_quote_indexes':[0]}]}
    checked,report=verify_answer(FakeLLM(respond),AnswerDraft([claim],'answered',worksheet=worksheet),ev,settings(tmp_path))
    assert len(calls)==2 and not checked.claims and report['source_core_repair']['failed']
