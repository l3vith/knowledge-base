"""Source-derived navigation must not become an answer or an unverified page filter."""
from dataclasses import replace
import json
import numpy as np
import pytest
import pymupdf
from kb.ingest.navigation import build_navigation
from kb.ingest.segment import segment_document
from kb.ingest.parse import parse_pdf
from kb.ingest.enrich import enrich_collection
from kb.models import ParsedDoc,PageText,DocCard,PageCard
from kb.store import Store
from kb.registry import Registry
from kb.testing import make_pdf
from kb.query.metadata import navigation_hints
from kb.query.screen import local_survey_pages
from kb.query.candidates import element_retrieval
from kb.query.types import QueryPlan,Aspect
from tests.track_b.helpers import settings as query_settings


def document(texts,outline=None,labels=None):
    return ParsedDoc('d','source.pdf',len(texts),[
        PageText(i,t,False,[],{'page_label':labels[i-1]} if labels else {}) for i,t in enumerate(texts,1)],outline or [],{})


def navigation(doc):
    elements,sections=segment_document(doc)
    return build_navigation(doc,elements,sections)


def test_outline_ranges_keep_parent_and_child_boundaries():
    doc=document(['# Overview','## Market risk','Additional detail','# Results'],
                 [(1,'Overview',1),(2,'Market risk',2),(1,'Results',4)])
    nav=navigation(doc)
    rows={e['title']:e for e in nav['sections'] if e['origin']=='pdf_outline'}
    assert rows['Overview']['end_page']==3
    assert rows['Market risk']['end_page']==3
    assert rows['Results']['end_page']==4
    assert all(e['start_page']<=e['end_page']<=4 for e in nav['sections'])


def test_printed_contents_offset_needs_multiple_heading_anchors():
    doc=document(['# Contents\nCapital requirements ........ 1\nModel validation ........ 3',
                  'Front matter','# Capital requirements\nCapital source text.',
                  'More capital text','# Model validation\nValidation source text.'])
    nav=navigation(doc)
    assert nav['printed_page_offset']==2
    assert {e['title']:e['start_page'] for e in nav['printed_references']}=={'Capital requirements':3,'Model validation':5}
    assert nav['pages']['1']['navigation_page']


def test_wrong_unvalidated_contents_page_is_not_silently_physical():
    nav=navigation(document(['# Contents\nUnknown target ........ 2','Unrelated source']))
    assert not nav['printed_references']
    assert nav['unresolved_references'][0]['printed_label']=='2'
    assert nav['printed_page_offset'] is None


def test_explicit_roman_labels_and_back_of_book_index():
    doc=document(['# Contents\nOverview ........ i','# Overview\nBackground.',
                  '# Index\nLiquidity buffers 2, 3',
                  '# Liquidity buffers\nLiquidity buffers details.','More liquidity buffers details.'],
                 labels=['cover','i','index','2','3'])
    nav=navigation(doc)
    assert next(e for e in nav['printed_references'] if e['title']=='Overview')['start_page']==2
    index=[e for e in nav['printed_references'] if e['kind']=='index']
    assert [e['start_page'] for e in index]==[4,5]


def test_tables_figures_units_periods_and_reference_locators():
    nav=navigation(document(['# 1 Risk reporting\nSee Table 2 and Figure 3.',
        '# Table 2: Capital buffer\n| Metric | FY2025 USD million |\n|---|---|\n| Buffer | 12 |',
        '# Figure 3: Liquidity trends\nThe liquidity ratio improved in 2025.']))
    assert nav['locators']['table:2']==[2]
    assert nav['locators']['figure:3']==[3]
    assert nav['pages']['2']['table_headers']
    assert '2025' in nav['pages']['3']['years']
    assert 'USD' in nav['pages']['2']['units']
    assert nav['pages']['2']['numeric_density']>0


def test_parse_captures_native_labels_links_and_source_hash(tmp_path,settings):
    path=make_pdf(tmp_path/'native.pdf',['# Intro\nText '*10,'# Risk\nRisk details '*10])
    pdf=pymupdf.open(path)
    pdf.set_page_labels([{'startpage':0,'prefix':'','style':'r','firstpagenum':1}])
    pdf[0].insert_link({'kind':pymupdf.LINK_GOTO,'from':pymupdf.Rect(10,10,90,40),'page':1})
    pdf.saveIncr();pdf.close()
    doc=parse_pdf(path,settings,use_ocr=False)
    assert doc.pages[0].metadata['page_label']=='i'
    assert doc.pages[0].metadata['internal_link_pages']==[2]
    assert doc.pages[0].metadata['width_points']>0
    assert len(doc.pdf_metadata['source_sha256'])==64


def test_metadata_focus_preserves_outside_source_reserve_and_scope(tmp_path):
    doc=document(['# Capital requirements\nCapital buffers are described here.',
                  'Additional capital buffers details.',
                  '# Other material\nCapital exception outside the section.'],
                 [(1,'Capital requirements',1),(1,'Other material',3)])
    elements,sections=segment_document(doc)
    nav=build_navigation(doc,elements,sections)
    store=Store.create(tmp_path/'store')
    card=DocCard('d','source.pdf','Source','other','',[],'',None,None,'',[],'',3,navigation=nav)
    pcs=[PageCard('d',p.page_no,sections[p.page_no],p.markdown,[],[],[]) for p in doc.pages]
    store.add_document(card,doc.pages,pcs,elements)
    plan=QueryPlan('analytical',[Aspect('a1','capital requirements',['capital'])],['d'])
    cfg=query_settings(tmp_path,metadata_fallback_pages=1,metadata_pages_per_range=1)
    hints=navigation_hints(store,plan,'capital requirements','d',[1,2,3],[1,2,3],cfg)
    assert hints['focused'] and hints['matches']
    picks,report=local_survey_pages(plan,{'d':[1,2,3]},{'d':{1,2,3}},
        {'documents':{'d':{'ranked_pages':[1,2,3],'navigation':hints}}},cfg)
    assert report['metadata_matches']>0
    selected,_=element_retrieval(store,plan,'capital requirements',picks,[],None,cfg,
                               navigation={'d':{'navigation':hints}})
    assert any(e.element.page_no==3 for e in selected)
    assert all(e.element.doc_id=='d' for e in selected)
    assert not store.search_elements_on_pages(['capital'],'d',[1],40)==[]
    assert all('p0001' in eid for eid,_ in store.search_elements_on_pages(['capital'],'d',[1],40))
    store.close()


def test_no_metadata_is_backward_compatible_and_not_focused(tmp_path):
    from tests.track_b.helpers import MemoryStore
    store=MemoryStore({'d':['Capital report']})
    plan=QueryPlan('analytical',[Aspect('a1','capital',['capital'])],['d'])
    h=navigation_hints(store,plan,'capital','d',[1],[1],query_settings(tmp_path))
    assert not h['available'] and not h['focused']


def test_metadata_upgrade_uses_new_generation_preserves_source_and_vectors(tmp_path,settings):
    registry=Registry(settings);gen,staging=registry.new_staging('metadata')
    store=Store.create(staging)
    doc=document(['# Capital requirements\nThe capital buffer is 12 percent.'])
    elements,sections=segment_document(doc)
    store.add_document(DocCard('d','source.pdf','Source','other','',[],'',None,None,'',[],'',1),
        doc.pages,[PageCard('d',1,'Capital requirements','Source',[],[],[])],elements)
    store.set_vectors('page',[('d',1)],np.array([[1.,0.]],dtype=np.float32));store.close()
    registry.promote('metadata',gen,staging)
    _,old_dir=registry.active_dir('metadata');old=Store.open(old_dir)
    original=old.elements_for_pages('d',[1])[0].text
    report=enrich_collection('metadata',settings)
    new_gen,new_dir=registry.active_dir('metadata');new=Store.open(new_dir)
    assert new_gen!=gen and report['llm_calls']==report['embedding_calls']==0
    assert new.doc('d').navigation['sections']
    assert not old.doc('d').navigation
    assert new.elements_for_pages('d',[1])[0].text==original
    assert (old_dir/'page_vecs.npy').read_bytes()==(new_dir/'page_vecs.npy').read_bytes()
    old.close();new.close()


def test_explicit_late_page_survives_global_page_cap(tmp_path):
    from tests.track_b.helpers import MemoryStore
    from kb.query.candidates import candidate_pages
    store=MemoryStore({'d':['Generic body text']*700})
    store.doc('d').navigation={'version':1,'sections':[], 'locators':{},'label_map':{},'pages':{}}
    plan=QueryPlan('analytical',[Aspect('a1','page 650',['page'])],['d'])
    pool,_,report=candidate_pages(store,plan,'page 650',None,query_settings(tmp_path,survey_cards_total=3))
    assert 650 in pool['d'] and len(pool['d'])<=3
    assert report['documents']['d']['navigation']['direct_pages']==[650]


def test_generic_document_topic_is_not_a_specific_range_filter(tmp_path):
    from tests.track_b.helpers import MemoryStore
    store=MemoryStore({'d':['# Banking models\nFirst material','More models']})
    store.doc('d').title='Banking models'
    store.doc('d').navigation={'version':1,'sections':[{'title':'Banking models','start_page':1,
        'end_page':2,'origin':'source_heading','confidence':.9}],'locators':{},'pages':{},'label_map':{}}
    plan=QueryPlan('analytical',[Aspect('a1','Banking models capital',['banking','models'],entity='Banking models')],['d'])
    h=navigation_hints(store,plan,'Banking models capital','d',[1,2],[1,2],query_settings(tmp_path))
    assert h['matches'] and not h['focused'] and not h['preferred_pages']


def test_direct_table_dependency_preserves_context_without_expanding_generic_sections(tmp_path):
    doc=document(['# Results\nSee Table 2 and Section 3.',
        '# Table 2: Capital values\n| Metric | Percent |\n|---|---|\n| Buffer | 12 |',
        '# 3 Background\nLong generic discussion.'])
    elements,sections=segment_document(doc);nav=build_navigation(doc,elements,sections)
    store=Store.create(tmp_path/'store')
    card=DocCard('d','source.pdf','Source','other','',[],'',None,None,'',[],'',3,navigation=nav)
    store.add_document(card,doc.pages,[PageCard('d',p.page_no,sections[p.page_no],p.markdown,[],[],[]) for p in doc.pages],elements)
    deps=store.dependencies(elements[0].element_id)
    assert any(e.page_no==2 and e.kind=='table' for e in deps)
    assert not any(e.page_no==3 for e in deps)
    store.close()


def test_internal_contents_links_help_validate_destinations():
    doc=document(['# Contents\nFunding risks ........ 9','Background',
                  'Funding risks are assessed by the committee.'])
    doc.pages[0].metadata={'internal_link_pages':[3]}
    nav=navigation(doc)
    assert nav['printed_references'][0]['start_page']==3
    assert nav['printed_references'][0]['printed_label']=='9'


def test_bad_metadata_never_becomes_a_focused_scope(tmp_path):
    from tests.track_b.helpers import MemoryStore
    store=MemoryStore({'d':['Capital details']})
    store.doc('d').navigation={'version':1,'sections':[{'title':'Capital requirements','start_page':1,
        'end_page':1,'origin':'unverified_guess','confidence':.2}],'pages':{},'locators':{}}
    plan=QueryPlan('analytical',[Aspect('a1','capital requirements',['capital'])],['d'])
    h=navigation_hints(store,plan,'capital requirements','d',[1],[1],query_settings(tmp_path))
    assert not h['focused'] and not h['preferred_pages']


def test_mismatched_native_bookmark_is_retained_but_not_trusted_for_focus(tmp_path):
    from tests.track_b.helpers import MemoryStore
    doc=document(['Source text about an unrelated subject.'],[(1,'Capital requirements',1)])
    nav=navigation(doc)
    assert nav['sections'][0]['confidence']<.85
    store=MemoryStore({'d':['Source text about an unrelated subject.']})
    store.doc('d').navigation=nav
    plan=QueryPlan('analytical',[Aspect('a1','capital requirements',['capital'])],['d'])
    h=navigation_hints(store,plan,'capital requirements','d',[1],[1],query_settings(tmp_path))
    assert not h['focused']


def test_metadata_can_be_disabled_for_ablation(tmp_path):
    from tests.track_b.helpers import MemoryStore
    store=MemoryStore({'d':['Capital requirements']})
    store.doc('d').navigation={'version':1,'locators':{'table:2':[1]},'pages':{}}
    plan=QueryPlan('analytical',[Aspect('a1','table 2',['table'])],['d'])
    h=navigation_hints(store,plan,'table 2','d',[1],[1],query_settings(tmp_path,metadata_navigation_enabled=False))
    assert not h['available'] and not h['direct_pages']


def test_broad_analytical_query_never_narrows_to_metadata_ranges(tmp_path):
    from tests.track_b.helpers import MemoryStore
    store=MemoryStore({'d':['# Accuracy\nAccuracy result.', '# Speed\nSpeed result.']})
    store.navigation=lambda d:{'version':1,'sections':[
        {'title':'Accuracy','start_page':1,'end_page':1,'origin':'source_heading','confidence':.9},
        {'title':'Speed','start_page':2,'end_page':2,'origin':'source_heading','confidence':.9}]}
    plan=QueryPlan('analytical',[Aspect('a1','accuracy and speed',['accuracy','speed'])],['d'])
    hints=navigation_hints(store,plan,'Compare accuracy and speed, build cost, controls and limitations before production use',
                           'd',[1,2],[1,2],query_settings(tmp_path))
    assert hints['matches'] and not hints['focused']
    assert hints['focus_policy']=='broad_query_boost_only'


def test_planner_expansion_cannot_create_specific_metadata_focus(tmp_path):
    from tests.track_b.helpers import MemoryStore
    store=MemoryStore({'d':['# Numerical instability\nGeneral theory.']})
    store.navigation=lambda d:{'version':1,'sections':[
        {'title':'Numerical instability','start_page':1,'end_page':1,'origin':'source_heading','confidence':.9}]}
    plan=QueryPlan('analytical',[Aspect('a1','production controls',['numerical instability'])],['d'])
    hints=navigation_hints(store,plan,'production controls','d',[1],[1],query_settings(tmp_path))
    assert not hints['matches'] and not hints['focused']
