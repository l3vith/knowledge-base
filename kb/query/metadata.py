"""Bounded, source-derived navigation hints. Never establish factual support or absence."""
import math
import re
from kb.ingest.navigation import words, _REFERENCE, locator_key
from .utils import get
from .settings import value


def navigation_hints(store,plan,query,doc,pool,ranked,settings):
    method=getattr(store,'navigation',None)
    nav=(method(doc) if callable(method) else get(store.doc(doc),'navigation',{})) if value(settings,'metadata_navigation_enabled') else {}
    report={'available':bool(nav),'version':nav.get('version'),'matches':[],
            'covered_aspects':[],'page_scores':{},'preferred_pages':[],'direct_pages':[],'focused':False}
    if not nav:return report
    allowed=set(pool);priority={p:i for i,p in enumerate(ranked)}
    entries=list(nav.get('sections',[]))+[e for e in nav.get('printed_references',[]) if e.get('kind')=='index']
    for no,features in nav.get('pages',{}).items():
        for caption in features.get('captions',[]):
            entries.append({'title':caption['title'],'start_page':int(no),'end_page':int(no),
                            'origin':'source_caption','confidence':.95})
    selected=[];scores={};covered=set();direct=[]
    context_words=words(get(store.doc(doc),'title',''))
    for aspect in plan.aspects:
        qwords=words(query) & words(aspect.text+' '+' '.join(aspect.keywords))
        scored=[]
        for entry in entries:
            if entry.get('origin') not in ('pdf_outline','source_heading','printed_heading_match',
                    'printed_label_or_offset_verified','source_caption') or entry.get('confidence',0)<.85:
                continue
            tw=words(entry.get('title',''));overlap=tw&qwords
            if not overlap:continue
            score=len(overlap)/math.sqrt(max(1,len(tw)))
            if len(overlap)/max(1,len(tw))<.4:continue
            start=entry.get('start_page',0);end=entry.get('end_page',start)
            if type(start) is not int or type(end) is not int or start<1 or end<start:continue
            scored.append((score,entry))
        scored.sort(key=lambda row:(-row[0],row[1]['end_page']-row[1]['start_page']))
        for score,entry in scored[:value(settings,'metadata_ranges_per_aspect')]:
            candidates=[p for p in allowed if entry['start_page']<=p<=entry['end_page']]
            if not candidates:continue
            specific=bool((words(entry.get('title','')) & qwords) - context_words - words(aspect.entity or ''))
            candidates.sort(key=lambda p:(priority.get(p,10**9),p))
            pages=list(dict.fromkeys(candidates[:value(settings,'metadata_pages_per_range')]+[entry['start_page']]))
            pages=[p for p in pages if p in allowed]
            report['matches'].append({**entry,'aspect_ids':[aspect.aspect_id],'score':round(score,4),'selected_pages':pages if specific else [],'specific':specific})
            if not specific:continue
            covered.add(aspect.aspect_id)
            for page in pages:
                selected.append(page);scores[str(page)]=max(scores.get(str(page),0),min(2.,score))
    # Explicit table/figure/section/page requests bypass fuzzy title matching, not scope guards.
    for match in _REFERENCE.finditer(query):
        for page in nav.get('locators',{}).get(locator_key(match.group(1),match.group(2)),[]):
            if page in allowed:selected.append(page);direct.append(page);scores[str(page)]=2.
    for match in re.finditer(r'\b(?:page|p\.)\s*(\d+|[ivxlcdm]+)\b',query,re.I):
        label=match.group(1).casefold();pages=nav.get('label_map',{}).get(label,[])
        if not pages and label.isdigit():pages=[int(label)]
        for page in pages:
            if page in allowed:selected.append(page);direct.append(page);scores[str(page)]=2.
    # A directly requested locator is a strong point hint, but does not prove every aspect covered.
    # Explicit units, periods, table headers and structural types are modest boosts only.
    query_words=words(query);query_years=set(re.findall(r'\b(?:19|20)\d{2}\b',query))
    for page in allowed:
        features=nav.get('pages',{}).get(str(page),{})
        header_words=words(' '.join(features.get('table_headers',[])))
        feature_score=min(.6,.15*len(query_words & header_words))
        feature_score+=min(.3,.1*len(query_words & words(' '.join(features.get('units',[])))))
        if query_years & set(features.get('years',[])):feature_score+=.15
        if re.search(r'\btable\b',query,re.I) and features.get('table_count'):feature_score+=.3
        if features.get('navigation_page') and not re.search(r'\b(contents|index|page)\b',query,re.I):feature_score-=1.
        if feature_score:scores[str(page)]=max(-1.,min(2.,scores.get(str(page),0)+feature_score))
    # Broad analytical requests must retain independent full-source searches.
    narrow_request=(plan.intent=='factoid' or (len(plan.aspects)==1 and len(words(query))<=6
                    and not re.search(r'\b(compare|versus|explain|analy[sz]e|evidence|limitations|controls)\b',query,re.I)))
    report['focus_policy']='specific_request_only' if narrow_request else 'broad_query_boost_only'
    report.update(covered_aspects=sorted(covered),preferred_pages=list(dict.fromkeys(selected)),page_scores=scores,
                  direct_pages=list(dict.fromkeys(direct)),focused=narrow_request and bool(covered) and len(covered)==len(plan.aspects) and plan.intent!='exhaustive',
                  unresolved_reference_count=nav.get('stats',{}).get('unresolved_printed_references',0))
    return report


def element_metadata_score(element,navigation):
    route=(navigation or {}).get(get(element,'doc_id'),{}).get('navigation',{})
    return float(route.get('page_scores',{}).get(str(get(element,'page_no')),0))
