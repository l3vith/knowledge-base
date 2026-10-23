"""M10: bound-generation executor; no imports from Track A storage."""
from __future__ import annotations
from time import monotonic
from .answer import ABSTAIN_TEXT, select_portfolio, number_evidence, generate_answer, verify_answer, render_verified
from .candidates import candidate_pages, escape_pages, element_retrieval
from .errors import BudgetExceeded, QueryError
from .observability import sink_from_environment
from .plan import plan_query, guard_routing, field
from .runtime import QueryRuntime
from .screen import survey_pages, verify_elements, local_survey_pages, NO_EVIDENCE_LIMIT
from .settings import value, QuerySettings
from .triage import element_triage
from .types import QueryPlan, Aspect, Evidence, AnswerDraft, SurveyPick
from .utils import get, terms, plain, id_for, narrow_factoid

BUDGET_TEXT="Not answered: the query budget ran out before any source evidence could be verified."

STEP_NAMES=["query_planning","routing_guard","candidate_pages","page_survey","element_retrieval",
            "element_triage","element_verification","answer_generation","answer_verification","citation_render"]
DESCRIPTIONS=["Compile query obligations and explicit scopes","Guard document identity and reporting period",
              "Find scoped source pages and independent lexical matches","Survey finite page cards with visible omissions",
              "Recover exact source elements and dependencies","Order bounded verification work with local relevance scores",
              "Verify source-visible evidence against obligations","Select complementary evidence and draft supported claims",
              "Check claim support and deterministic calculations","Render immutable source citations and full writer context"]


def format_chunk(card,ev,evidence_id):
    el=ev.element;content=get(el,"text")
    source=field(card,"file_name",get(el,"doc_id")+".pdf")
    return {"chunk_id":get(el,"element_id"),"evidence_id":evidence_id,"doc_id":get(el,"doc_id"),
            "document":source,"source_path":field(card,"relative_path",source),"page":get(el,"page_no"),
            "content":content,"text":content,"kind":get(el,"kind","text"),"section":get(el,"section",""),
            "parent_element_id":get(el,"parent_element_id",get(el,"element_id")),
            "char_start":get(el,"char_start",0),"char_end":get(el,"char_end",len(content)),
            "evidence_role":"writer_context","cited_by_claim_ids":[]}


def _coverage(plan,numbered,claims,limits,counts):
    rows=[]
    for aspect in plan.aspects:
        eids=[eid for eid,ev in numbered.items() if aspect.aspect_id in ev.aspect_ids]
        supported=[c.claim_id for c in claims if aspect.aspect_id in c.aspect_ids]
        rows.append({"id":aspect.aspect_id,"text":aspect.text,"entity":aspect.entity,"period":aspect.period,
                     "evidence_ids":eids,"claim_ids":supported,"status":"supported" if supported else "unresolved"})
    return {"aspects":rows,"obligations":rows,"limitations":list(dict.fromkeys(limits)),"counts":counts,
            "completeness_proven":False}


def answer_query(collection,query,*,store,generation_id,settings,llm,embedder=None,reranker=None,mode="full",sink=None,request_id=None):
    if mode not in ("full","baseline"):
        raise QueryError("INVALID_REQUEST","Unknown execution mode",422)
    if not isinstance(query,str) or not query.strip() or len(query)>value(settings,"query_max_chars"):
        raise QueryError("INVALID_REQUEST","Query is empty or too long",422)
    query=query.strip()
    sink=sink or sink_from_environment(value(settings,"strict_observability"))
    ctx=QueryRuntime(settings,llm,sink,request_id)
    # Explicit allow-list: never hash/serialize credentials in a shared Settings object.
    from dataclasses import fields
    safe_config={f.name:plain(value(settings,f.name)) for f in fields(QuerySettings)}
    safe_config["legacy_budgets"]=plain(getattr(settings,"budgets",{}))
    config_sha256=id_for(safe_config)
    ctx.save("run_manifest",{"collection":collection,"generation_id":generation_id,
                             "config_sha256":config_sha256,"query_config":safe_config,"mode":mode})
    cards={get(c,"doc_id"):c for c in store.docs()}
    page_report={};numbered={};draft=AnswerDraft([],"no_answer");limits=[];counts={};answer=ABSTAIN_TEXT
    current_stage=-1
    try:
        with sink.span("query",input={"collection":collection,"query":query},metadata={"generation_id":generation_id,"request_id":ctx.request_id,"mode":mode}) as root:
            with ctx.stage(STEP_NAMES[0],DESCRIPTIONS[0],{"query":query,"catalogue_count":len(cards)}) as out:
                current_stage=0
                if mode=="baseline":
                    plan=QueryPlan("analytical",[Aspect("a1",query,terms(query))],list(cards))
                    out.update(skipped=True,reason="baseline control",obligations=plain(plan.aspects))
                else:
                    plan=plan_query(ctx.llm,query,list(cards.values()),settings,ctx=ctx)
                    out.update(intent=plan.intent,obligations=plain(plan.aspects),notes=plan.notes,limitations=plan.limitations)
            with ctx.stage(STEP_NAMES[1],DESCRIPTIONS[1],{"planned_doc_ids":plan.doc_ids}) as out:
                current_stage=1
                if mode=="baseline":
                    guard={"excluded":[]};out.update(skipped=True,reason="baseline control")
                else:
                    plan,guard=guard_routing(plan,query,list(cards.values()),store,settings);out.update(guard)
            limits.extend(plan.limitations)
            with ctx.stage(STEP_NAMES[2],DESCRIPTIONS[2],{"doc_ids":plan.doc_ids}) as out:
                current_stage=2
                if mode=="baseline":
                    pool,lexical,escape={},{},[];out.update(skipped=True,reason="baseline control")
                else:
                    pool,lexical,page_report=candidate_pages(store,plan,query,embedder,settings)
                    blocked={x["doc_id"] for x in guard.get("excluded",[])}
                    escape=[(d,p) for d,p in escape_pages(store,plan,query,embedder,settings) if d not in blocked]
                    report=page_report
                    out.update(report,escape_pages=escape)
                    counts["candidate_pages"]=report["total"]
                    if report["omitted_cards"]:
                        limits.append(f"{report['omitted_cards']} routed page cards omitted by survey budget")
            with ctx.stage(STEP_NAMES[3],DESCRIPTIONS[3],{"pool_pages":sum(len(v) for v in pool.values())}) as out:
                current_stage=3
                if mode=="baseline":
                    picks=[];out.update(skipped=True,reason="baseline control")
                elif narrow_factoid(plan,query):
                    picks=[SurveyPick(d,p,[a.aspect_id for a in plan.aspects],"lexical")
                           for d,pages in lexical.items() for p in dict.fromkeys(page_report.get("documents",{}).get(d,{}).get("navigation",{}).get("direct_pages",[])+sorted(pages))]
                    out.update(skipped=True,reason="single-document single-obligation factual path",
                               picked_pages=len(picks),cards_surveyed=0)
                    counts["cards_surveyed"]=0
                    counts["raw_candidate_pages"]=len(picks)+len(escape)
                else:
                    if value(settings,"page_selection_mode")=="local":
                        picks,report=local_survey_pages(plan,pool,lexical,page_report,settings)
                    elif value(settings,"page_selection_mode")=="llm":
                        picks,report=survey_pages(ctx.llm,store,plan,query,pool,lexical,settings,ctx=ctx)
                    else:
                        raise QueryError("INVALID_CONFIG","KB_PAGE_SELECTION must be local or llm",500)
                    out.update(report,picked_pages=len(picks));limits.extend(report["limitations"])
                    counts["cards_surveyed"]=report["cards_surveyed"]
                    counts["raw_candidate_pages"]=len(picks)+len(escape)
                    if report["truncated"]:
                        limits.append(f"{report['truncated']} selected pages omitted by raw-read budget")
            with ctx.stage(STEP_NAMES[4],DESCRIPTIONS[4],{"picked_pages":len(picks)}) as out:
                current_stage=4
                candidates,report=element_retrieval(store,plan,query,picks,escape,embedder,settings,navigation=page_report.get("documents",{}))
                out.update(report);counts["elements_retrieved"]=len(candidates)
            with ctx.stage(STEP_NAMES[5],DESCRIPTIONS[5],{"candidates":len(candidates)}) as out:
                current_stage=5
                _,middle,report=element_triage(candidates,plan,reranker,settings)
                out.update(report);limits.extend(report["limitations"])
                if report["dropped_budget"]:
                    limits.append(f"{report['dropped_budget']} candidates omitted by verification budget")
            with ctx.stage(STEP_NAMES[6],DESCRIPTIONS[6],{"candidates":len(middle)}) as out:
                current_stage=6
                if mode=="baseline":
                    evidence=[Evidence(c.element,c.aspect_ids,"baseline relevance only","baseline",c.ce_score) for c in middle[:30]]
                    out.update(skipped=True,reason="baseline control",evidence_count=len(evidence))
                elif middle:
                    evidence,report=verify_elements(ctx.llm,store,plan,query,middle,settings,ctx=ctx)
                    out.update(report);limits.extend(report["limitations"])
                    counts["raw_fragments_verified"]=report["elements_seen"]
                    if report["omitted_fragments"]:
                        limits.append(f"{report['omitted_fragments']} source fragments not verified within budget")
                else:
                    evidence=[];out.update(skipped=True,reason="no source candidates")
            with ctx.stage(STEP_NAMES[7],DESCRIPTIONS[7],{"evidence":len(evidence)}) as out:
                current_stage=7
                # Writer and claim check each resend the portfolio; cap it to half of what the input budget has left.
                left=value(settings,"max_input_tokens")-ctx.estimated_input
                portfolio,report=select_portfolio(evidence,plan,settings,cap=max(0,left//2-8000))
                numbered=number_evidence(portfolio)
                if report["omitted"]:
                    limits.append(f"{report['omitted']} verified fragments omitted from writer context")
                plan.limitations=list(dict.fromkeys(limits))
                draft=generate_answer(ctx.llm,query,plan,numbered,cards,settings,ctx=ctx)
                out.update(report,draft_claims=len(draft.claims),writer_source_ids=[get(ev.element,"element_id") for ev in portfolio])
                ctx.save("writer_context",evidence_block_for_artifact(numbered,cards))
            with ctx.stage(STEP_NAMES[8],DESCRIPTIONS[8],{"claims":len(draft.claims)}) as out:
                current_stage=8
                draft,report=verify_answer(ctx.llm,draft,numbered,settings,ctx=ctx);out.update(report)
            with ctx.stage(STEP_NAMES[9],DESCRIPTIONS[9],{"accepted_claims":len(draft.claims)}) as out:
                current_stage=9
                answer,report=render_verified(draft,numbered,cards);out.update(report)
                chunks=[format_chunk(cards[get(ev.element,"doc_id")],ev,eid) for eid,ev in numbered.items()]
                for chunk in chunks:
                    cited=[c.claim_id for c in draft.claims if chunk["evidence_id"] in c.evidence_ids]
                    chunk["cited_by_claim_ids"]=cited
                    if cited:
                        chunk["evidence_role"]="claim_support"
            coverage=_coverage(plan,numbered,draft.claims,limits+draft.limitations,counts)
            unresolved=any(a["status"]!="supported" for a in coverage["aspects"])
            if draft.claims:
                status="partial" if coverage["limitations"] or unresolved or draft.status=="partial" else "answered"
            else:
                status="partial" if numbered else "no_answer"
                if not numbered and NO_EVIDENCE_LIMIT in limits:
                    answer=BUDGET_TEXT  # a budget stop is not corpus absence; say which it was
            # Limitations stay in `coverage` and the trace, not the answer: the judge scores every answer sentence as a claim.
            result={"request_id":ctx.request_id,"collection_name":collection,"generation_id":generation_id,
                    "config_sha256":config_sha256,
                    "status":status,"answer":answer,"chunks":chunks,"trace":ctx.trace,"coverage":coverage,
                    "usage":ctx.usage(),"metrics":{"latency_ms":round((monotonic()-ctx.started)*1000,3),"usage":ctx.usage()},
                    "latency_ms":round((monotonic()-ctx.started)*1000,3),"langfuse_trace_id":sink.trace_id,
                    "trace_id":sink.trace_id,"observability_status":sink.status,"mode":mode}
            root.update(output={"status":status,"answer":answer,"chunk_count":len(chunks),"usage":ctx.usage()})
        sink.flush()
        result["observability_status"]=sink.status
        ctx.save("response",result)
        return result
    except BaseException as exc:
        ctx.save("failure",{"error":type(exc).__name__,"trace":ctx.trace,"usage":ctx.usage()})
        try:
            sink.flush()
        except Exception:
            pass
        raise


def evidence_block_for_artifact(numbered,cards):
    return {eid:format_chunk(cards[get(ev.element,"doc_id")],ev,eid) for eid,ev in numbered.items()}
