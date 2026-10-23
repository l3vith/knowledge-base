"""M7: relevance ordering only; logits never auto-verify factual support."""
from dataclasses import replace
import math
from .settings import value, budget
from .utils import get, estimate_tokens


def _counter(reranker):
    fn=getattr(reranker,"token_count",None)
    if callable(fn):
        return lambda q,t: fn(q,t)
    # FastEmbed wrappers nest the ONNX backend. Inspect only this known, bounded chain.
    backend=reranker
    for depth in range(4):
        tokenizer=getattr(backend,"tokenizer",None)
        if tokenizer is not None:
            limit=(getattr(tokenizer,"truncation",None) or {}).get("max_length",512)
            # The scoring tokenizer may truncate/pad. Clone before counting so hidden tails count.
            if hasattr(tokenizer,"to_str"):
                from tokenizers import Tokenizer
                tokenizer=Tokenizer.from_str(tokenizer.to_str())
                tokenizer.no_truncation();tokenizer.no_padding()
            counter=lambda q,t: len(tokenizer.encode(q,t).ids)
            counter.model_limit=limit
            return counter
        backend=getattr(backend,"model",None)
        if backend is None:
            break
    return None


def _windows(query,text,count,max_tokens):
    start=0
    while start<len(text):
        end=min(len(text),start+max_tokens*4)
        while end>start and count(query,text[start:end])>max_tokens:
            end-=max(1,(end-start)//8)
        if end==start:
            return
        yield text[start:end]
        if end==len(text):
            return
        start=max(start+1,end-min(80,(end-start)//5))


def element_triage(candidates,plan,reranker,settings):
    candidates=[replace(c) for c in candidates]
    report={"scored":0,"pairs":0,"auto_kept":0,"auto_dropped":0,"dropped_budget":0,"scores":[],"limitations":[]}
    counter=_counter(reranker) if reranker is not None else None
    if reranker is not None and counter is None:
        report["limitations"].append("Reranker skipped: actual pair tokenizer unavailable; no character truncation substituted")
    if counter:
        max_pairs=value(settings,"max_ce_pairs")
        pair_limit=min(getattr(reranker,"max_pair_tokens",512),getattr(counter,"model_limit",512))
        queues=[]
        by_aspect={a.aspect_id:a for a in plan.aspects}
        for candidate in candidates:
            q=" ".join(by_aspect[a].text for a in candidate.aspect_ids if a in by_aspect) or " ".join(a.text for a in plan.aspects)
            queues.append((candidate,q,iter(_windows(q,get(candidate.element,"text"),counter,pair_limit))))
        # Round-robin windows prevents a huge first table consuming every pair.
        active=list(queues);pairs=[]
        while active and report["pairs"]<max_pairs:
            remaining=[]
            for candidate,q,windows in active:
                if report["pairs"]>=max_pairs:
                    break
                text=next(windows,None)
                if text is None:
                    continue
                pairs.append((candidate,q,text))
                report["pairs"]+=1
                remaining.append((candidate,q,windows))
            active=remaining
        grouped={}
        for candidate,q,text in pairs:
            grouped.setdefault(q,[]).append((candidate,text))
        for q,group in grouped.items():
            for offset in range(0,len(group),64):
                batch=group[offset:offset+64]
                scores=reranker.score(q,[text for candidate,text in batch])
                if len(scores)!=len(batch) or any(not math.isfinite(float(s)) for s in scores):
                    raise ValueError("invalid reranker scores")
                for (candidate,text),score in zip(batch,scores):
                    candidate.ce_score=max(candidate.ce_score if candidate.ce_score is not None else -math.inf,float(score))
        report["scored"]=sum(c.ce_score is not None for c in candidates)
        report["scores"]=[[get(c.element,"element_id"),c.ce_score] for c in candidates if c.ce_score is not None]
        if active:
            report["limitations"].append("Reranker pair budget reached; some source windows unscored")
    # Fair candidates by obligation, score is a tie-break inside each queue.
    report["metadata_boosted"]=sum(c.metadata_score>0 for c in candidates)
    ordered=sorted(candidates,key=lambda c:(c.ce_score is None,-((c.ce_score or 0)+min(2.,c.metadata_score)),get(c.element,"doc_id"),get(c.element,"page_no"),get(c.element,"idx",0)))
    queues=[[c for c in ordered if a.aspect_id in c.aspect_ids] for a in plan.aspects]
    selected=[];seen=set();used=0;cap=budget(settings,plan.intent,"verify_chars")
    # Keep original candidates intact; screen.py creates visible bounded fragments.
    for i in range(max([len(q) for q in queues] or [0])):
        for queue in queues:
            if i>=len(queue):
                continue
            c=queue[i];key=get(c.element,"element_id")
            if key in seen:
                continue
            cost=min(len(get(c.element,"text").encode()),value(settings,"verify_chars_per_call"))
            if used+cost>cap:
                continue
            seen.add(key);selected.append(c);used+=cost
    report["dropped_budget"]=len(candidates)-len(selected)
    report["middle"]=len(selected)
    return [],selected,report
