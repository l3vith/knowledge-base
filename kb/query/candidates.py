"""M7: scoped candidates with independent lexical evidence and fair slot quotas."""
from collections import defaultdict
from .settings import value, budget
from .types import Candidate
from .utils import get, terms, rrf
from .metadata import navigation_hints, element_metadata_score
from .requirements import requested_topics

ENDMATTER=("conclusion","conclusions","limitation","limitations","discussion","future","caveats")


def _query_vectors(embedder,texts):
    import numpy as np
    query_embed=getattr(getattr(embedder,"model",None),"query_embed",None)
    if callable(query_embed):
        vectors=np.asarray(list(query_embed(texts)),dtype=np.float32)
        if vectors.ndim!=2 or len(vectors)!=len(texts):
            raise ValueError("invalid query embedding matrix")
        norms=np.linalg.norm(vectors,axis=1,keepdims=True)
        if np.any(norms==0) or not np.all(np.isfinite(vectors)):
            raise ValueError("invalid query embedding matrix")
        return vectors/norms
    return embedder.embed(texts)


def _dense(store, embedder, texts, docs, limit, kind,cache=None):
    if embedder is None or not docs:
        return []
    method=getattr(store,"dense_"+kind,None)
    if method is None:
        return []
    key=tuple(texts)
    if cache is not None:
        if key not in cache:
            cache[key]=_query_vectors(embedder,texts)
        vectors=cache[key]
    else:
        vectors=_query_vectors(embedder,texts)
    return method(vectors,docs,limit)


def candidate_pages(store, plan, query, embedder, settings):
    pools={}; lexical={}; report={"documents":{},"omitted_cards":0};dense_cache={}
    cap=budget(settings,plan.intent,"survey_cards_total")
    slot_lists=[]
    for doc in plan.doc_ids:
        all_pages=store.nonblank_pages(doc)
        net=set()
        for aspect in plan.aspects:
            hits=store.search_pages(aspect.keywords+terms(aspect.text),[doc],value(settings,"lexical_net_pages_per_aspect"))
            net.update(p for d,p,s in hits if d==doc)
            slot_lists.append([(d,p) for d,p,s in hits if d==doc])
        topic_hits={}
        # Literal user-requested axes get independent source matches so one combined
        # obligation's popular terms cannot crowd out cost, timing or qualifications.
        for topic in requested_topics(query,plan.intent):
            hits=store.search_pages(terms(topic['text']),[doc],2)
            pages=[p for d,p,s in hits if d==doc]
            net.update(pages);topic_hits[topic['id']]=pages
            slot_lists.append([(doc,p) for p in pages])
        lexical[doc]=net
        source=store.search_pages(terms(query),[doc],cap)
        dense=_dense(store,embedder,[query]+[a.text for a in plan.aspects],[doc],cap,"pages",dense_cache)
        ranked=rrf([(d,p) for d,p,s in source],[(d,p) for d,p,s in dense])
        # Keep relevance order under the shared survey cap; validated navigation is a bounded hint.
        nonblank=set(all_pages)
        ordered=list(dict.fromkeys([p for d,p in ranked if p in nonblank]+all_pages))
        initial_nav=navigation_hints(store,plan,query,doc,all_pages,ordered,settings)
        metadata_pages=initial_nav['preferred_pages'] if initial_nav['focused'] else initial_nav['direct_pages']
        if metadata_pages:slot_lists.append([(doc,p) for p in metadata_pages])
        selected=list(dict.fromkeys(metadata_pages+sorted(net)+ordered))[:cap]

        pools[doc]=selected
        report["documents"][doc]={"available":len(all_pages),"mode":"all" if len(selected)==len(all_pages) else "bounded", "ranked_pages":selected,"requested_topic_hits":topic_hits}
    # Global fair cap: lexical obligation hits first, then round-robin across documents.
    selected=[]; seen=set()
    for rank in range(max([len(x) for x in slot_lists] or [0])):
        for hits in slot_lists:
            if rank<len(hits) and hits[rank] not in seen and len(selected)<cap:
                selected.append(hits[rank]); seen.add(hits[rank])
    for index in range(max([len(x) for x in pools.values()] or [0])):
        for doc,pages in pools.items():
            key=(doc,pages[index]) if index<len(pages) else None
            if key and key not in seen and len(selected)<cap:
                selected.append(key);seen.add(key)
    result={doc:[p for d,p in selected if d==doc] for doc in pools}
    for doc,pages in result.items():
        report["documents"][doc]["selected"]=len(pages)
        report["documents"][doc]["ranked_pages"]=[p for p in report["documents"][doc]["ranked_pages"] if p in set(pages)]
        nav=navigation_hints(store,plan,query,doc,pages,report["documents"][doc]["ranked_pages"],settings)
        report["documents"][doc]["navigation"]=nav
        report["documents"][doc]["ranked_pages"]=rrf(nav['preferred_pages'] if nav['focused'] else nav['direct_pages'],report["documents"][doc]["ranked_pages"])
        report["omitted_cards"]+=report["documents"][doc]["available"]-len(pages)
        lexical[doc]&=set(pages)
    report["total"]=len(selected)
    return result,lexical,report


def escape_pages(store,plan,query,embedder,settings):
    others=[get(c,"doc_id") for c in store.docs() if get(c,"doc_id") not in plan.doc_ids]
    if not others:
        return []
    cap=value(settings,"escape_pages")
    hits=store.search_pages(terms(query),others,cap)
    # Escape does not bypass confirmed scope checks; pipeline rechecks against guard exclusions.
    return [(d,p) for d,p,s in hits if d in others][:cap]


def element_retrieval(store,plan,query,picks,escape,embedder,settings,*,navigation=None):
    merged={}
    def add(element,aspects,source):
        key=get(element,"element_id")
        if not key or not get(element,"text","").strip():
            return
        if key not in merged:
            merged[key]=Candidate(element,[],[],metadata_score=element_metadata_score(element,navigation))
        candidate=merged[key]
        candidate.aspect_ids=list(dict.fromkeys(candidate.aspect_ids+aspects))
        candidate.sources=list(dict.fromkeys(candidate.sources+[source]))
    for pick in picks:
        # Source recovery includes flagged repeated headers; a flag is not semantic deletion.
        for el in store.elements_for_pages(pick.doc_id,[pick.page_no],include_boilerplate=True):
            add(el,pick.aspect_ids,"survey_"+pick.strength)
    for aspect in plan.aspects:
        if not plan.doc_ids:
            continue
        sparse=[]
        scoped=getattr(store,"search_elements_on_pages",None)
        focused=any((navigation or {}).get(d,{}).get("navigation",{}).get("focused") for d in plan.doc_ids)
        if not focused:
            sparse=store.search_elements(aspect.keywords+terms(aspect.text),plan.doc_ids,value(settings,"element_hits_per_aspect"))
        for doc in plan.doc_ids if focused else []:
            route=(navigation or {}).get(doc,{}).get("navigation",{})
            search_terms=aspect.keywords+terms(aspect.text)
            if route.get("focused") and callable(scoped):
                pages=[p.page_no for p in picks if p.doc_id==doc]
                local=scoped(search_terms,doc,pages,value(settings,"element_hits_per_aspect"))
                # Independent source matches outside metadata ranges remain eligible.
                outside=store.search_elements(search_terms,[doc],value(settings,"element_hits_per_aspect"))
                inside_ids={eid for eid,score in local}
                reserve=[(eid,score) for eid,score in outside if eid not in inside_ids][:value(settings,"metadata_element_fallback_hits")]
                sparse.extend(reserve+local[:max(0,value(settings,"element_hits_per_aspect")-len(reserve))])
            else:
                sparse.extend(store.search_elements(search_terms,[doc],value(settings,"element_hits_per_aspect")))
        dense=_dense(store,embedder,[aspect.text],plan.doc_ids,value(settings,"element_hits_per_aspect"),"elements") if value(settings,"embed_elements",False) else []
        ids=rrf([e for e,s in sparse],[e for e,s in dense])[:value(settings,"element_hits_per_aspect")]
        for el in store.elements_by_ids(ids):
            if get(el,"doc_id") in plan.doc_ids:
                add(el,[aspect.aspect_id],"hybrid")
    if plan.intent!="factoid" and plan.doc_ids:
        # Conclusions and limitations often sit at a document's end and rank low for any one aspect; search them
        # explicitly (element FTS indexes the section title) so page rank alone cannot drop them.
        for eid,score in store.search_elements(list(ENDMATTER),plan.doc_ids,value(settings,"endmatter_hits")):
            for el in store.elements_by_ids([eid]):
                if get(el,"doc_id") in plan.doc_ids:
                    add(el,[a.aspect_id for a in plan.aspects],"structure")
    for doc,page in escape:
        for el in store.elements_for_pages(doc,[page],include_boilerplate=True):
            add(el,[a.aspect_id for a in plan.aspects],"escape")
    # Optional source-declared dependency seam; legacy stores may not implement it.
    dependencies=getattr(store,"dependencies",None)
    if callable(dependencies) and value(settings,"metadata_navigation_enabled"):
        dependency_count=0
        for candidate in list(merged.values()):
            if dependency_count>=value(settings,"metadata_dependency_elements"):break
            for el in dependencies(get(candidate.element,"element_id")):
                if get(el,"element_id") in merged:continue
                add(el,candidate.aspect_ids,"source_dependency");dependency_count+=1
                if dependency_count>=value(settings,"metadata_dependency_elements"):break
    priority={"survey_high":0,"hybrid":1,"structure":1,"survey_lexical":2,"survey_medium":3,"source_dependency":3,"escape":4}
    result=sorted(merged.values(),key=lambda c:(min(priority.get(s,5) for s in c.sources),get(c.element,"doc_id"),get(c.element,"page_no"),get(c.element,"idx",0)))
    return result,{"total":len(result),"by_source":{s:sum(s in c.sources for c in result) for s in priority}}
