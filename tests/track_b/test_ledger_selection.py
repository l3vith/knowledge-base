from dataclasses import replace
from kb.query.anchors import SourceCatalog
from kb.query.ledger import parse_id_records, select_records
from kb.query.types import Aspect, QueryPlan, Evidence
from .helpers import MemoryStore

PAGES=['Build took 5 minutes in Matlab. A second build took 8 minutes for the larger model.',
       'The surrogate cannot extrapolate outside its domain.',
       'Errors were 0.1% on average. Calibration took 0.7 seconds.']


def setup(pages=PAGES):
    store=MemoryStore({'d':pages});ev={f'E{i+1}':Evidence(e,['a1','a2','a3']) for i,e in enumerate(store.elements)}
    plan=QueryPlan('analytical',[Aspect('a1','cost',[]),Aspect('a2','limitations',[]),Aspect('a3','accuracy',[])],['d'])
    return ev,plan,SourceCatalog(ev)


def rows(catalog):
    s=lambda e,i:catalog.by_evidence[e][i]
    return [{'anchor_ids':[s('E1',0)],'obligation_ids':['a1']},{'anchor_ids':[s('E1',1)],'obligation_ids':['a1']},
            {'anchor_ids':[s('E2',0)],'obligation_ids':['a2'],'role':'QUALIFICATION'},
            {'anchor_ids':[s('E3',0)],'obligation_ids':['a3']},{'anchor_ids':[s('E3',1)],'obligation_ids':['a3']}]


def texts(selected):
    return sorted(r.render_text for r in selected)


def test_selection_ignores_record_ids_and_input_order():
    ev,plan,catalog=setup();records,_=parse_id_records(rows(catalog),ev,plan,[],catalog)
    budget=len(' '.join(r.render_text for r in records))-40  # one record must go
    a,_=select_records(records,budget)
    renamed=[replace(r,record_id='Z'+str(i)) for i,r in enumerate(reversed(records))]
    b,_=select_records(renamed,budget)
    assert texts(a)==texts(b)


def test_limitation_survives_before_a_second_build_example():
    ev,plan,catalog=setup();records,_=parse_id_records(rows(catalog),ev,plan,[],catalog)
    budget=sum(len(r.render_text) for r in records)-len(records[1].render_text)
    selected,report=select_records(records,budget)
    kept=' '.join(texts(selected))
    assert 'cannot extrapolate' in kept and 'Errors were 0.1%' in kept and not report['uncovered_topics']


def test_projection_keeps_its_assumption_and_a_leaning_sentence_keeps_its_subject():
    ev,plan,catalog=setup(['We assume a C++ implementation. That would give a 40,000 times speed-up.',
                           'The routine is Monte Carlo based. It used 60,000 paths.'])
    s=lambda e,i:catalog.by_evidence[e][i]
    records,_=parse_id_records([{'anchor_ids':[s('E1',1)],'obligation_ids':['a1'],'mode':'PROJECTED'},
                                {'anchor_ids':[s('E2',1)],'obligation_ids':['a3']}],ev,plan,[],catalog)
    assert records[0].render_text.startswith('We assume a C++ implementation.')
    assert records[1].render_text.startswith('The routine is Monte Carlo based.')


def test_compact_bundle_drops_unselected_numeric_setup():
    ev,plan,catalog=setup(['The grid had 117,649 points and 12 ranks. The build used 10,000 calls.'])
    ids=catalog.by_evidence['E1'];value=[v for v in catalog.value_ids['E1'] if catalog.anchors[v].text.startswith('10')]
    records,_=parse_id_records([{'anchor_ids':list(ids),'obligation_ids':['a1'],'value_ids':value}],ev,plan,[],catalog)
    assert records[0].render_text=='The build used 10,000 calls.'


def test_abstract_repeat_merges_into_detailed_result_but_other_scope_does_not():
    ev,plan,catalog=setup(['Errors were 0.1% on average.','Errors were 0.1% on average across 1,000 surfaces.'])
    ev['E1'].element=replace(ev['E1'].element,section='Abstract');catalog=SourceCatalog(ev)
    s=lambda e:catalog.by_evidence[e][0]
    same,report=parse_id_records([{'anchor_ids':[s('E1')],'obligation_ids':['a3']},{'anchor_ids':[s('E1')],'obligation_ids':['a1']}],ev,plan,[],catalog)
    assert len(same)==1 and same[0].obligation_ids==['a3','a1']  # one finding verified for two question parts
    ev2,plan2,cat2=setup(['Errors were 0.1% on average.','Errors were 0.1% on average.'])
    ev2['E1'].element=replace(ev2['E1'].element,section='Abstract');cat2=SourceCatalog(ev2)
    merged,report=parse_id_records([{'anchor_ids':[cat2.by_evidence[e][0]],'obligation_ids':['a3']} for e in ('E1','E2')],ev2,plan2,[],cat2)
    assert len(merged)==1 and report['deduplicated']==1 and merged[0].position[1]==2  # the non-abstract statement
    projected,_=parse_id_records([{'anchor_ids':[cat2.by_evidence['E1'][0]],'obligation_ids':['a3']},
                                  {'anchor_ids':[cat2.by_evidence['E2'][0]],'obligation_ids':['a3'],'mode':'PROJECTED'}],ev2,plan2,[],cat2)
    assert len(projected)==2  # different epistemic mode never merges
