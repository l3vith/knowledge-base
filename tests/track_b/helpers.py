from dataclasses import dataclass, field, replace
import hashlib
import json
import re
import numpy as np
from kb.query.settings import QuerySettings
from kb.query.utils import get,terms


@dataclass
class Card:
    doc_id: str
    file_name: str
    title: str=""
    issuer: str="Example Bank"
    entities: list=field(default_factory=list)
    period_year: int | None=2025
    period_label: str="FY2025"
    doc_type: str="annual_report"
    jurisdiction: str=""
    topics: list=field(default_factory=list)
    summary: str=""
    page_count: int=1
    identifiers: list=field(default_factory=list)
    sibling_group: str | None=None
    scope: str="standalone"
    metadata_provenance: dict=field(default_factory=lambda:{"period_year":"source","identifiers":"source"})


@dataclass
class Element:
    element_id: str
    doc_id: str
    page_no: int
    idx: int
    kind: str
    section: str
    text: str
    flags: list=field(default_factory=list)


@dataclass
class PageCard:
    doc_id: str
    page_no: int
    section: str
    summary: str
    topics: list=field(default_factory=list)
    entities: list=field(default_factory=list)
    figures: list=field(default_factory=list)


class MemoryStore:
    def __init__(self,docs,cards=None):
        self._cards=cards or [Card(d,d+".pdf",title=d,page_count=len(pages)) for d,pages in docs.items()]
        self.pages={(d,i+1):text for d,pages in docs.items() for i,text in enumerate(pages)}
        self.elements=[Element(f"{d}:p{i+1}:e{j}",d,i+1,j,"text","Notes",part)
                       for d,pages in docs.items() for i,text in enumerate(pages) for j,part in enumerate(text.split("\n\n")) if part.strip()]
        self._lookup={e.element_id:e for e in self.elements}

    def docs(self): return self._cards
    def doc(self,doc_id): return next(c for c in self._cards if c.doc_id==doc_id)
    def nonblank_pages(self,doc_id): return sorted(p for (d,p),text in self.pages.items() if d==doc_id and text.strip())
    def page_cards(self,doc_id,page_nos=None):
        return [PageCard(d,p,"Notes",text[:200]) for (d,p),text in self.pages.items() if d==doc_id and (page_nos is None or p in page_nos)]
    def elements_for_pages(self,doc_id,page_nos,include_boilerplate=False):
        return [e for e in self.elements if e.doc_id==doc_id and e.page_no in page_nos and (include_boilerplate or "boilerplate" not in e.flags)]
    def elements_by_ids(self,ids): return [self._lookup[i] for i in ids if i in self._lookup]
    def search_pages(self,words,doc_ids,limit):
        q=set(terms(" ".join(words)))
        result=[(d,p,len(q&set(terms(text)))) for (d,p),text in self.pages.items() if doc_ids is None or d in doc_ids]
        return sorted([x for x in result if x[2]],key=lambda x:(-x[2],x[0],x[1]))[:limit]
    def search_elements(self,words,doc_ids,limit):
        q=set(terms(" ".join(words)))
        result=[(e.element_id,len(q&set(terms(e.text)))) for e in self.elements if doc_ids is None or e.doc_id in doc_ids]
        return sorted([x for x in result if x[1]],key=lambda x:(-x[1],x[0]))[:limit]
    def dense_pages(self,vecs,doc_ids,limit): return []
    def dense_elements(self,vecs,doc_ids,limit): return []


class FakeLLM:
    def __init__(self,responder=None,calls=None):
        self.responder=responder or self.default
        self.calls=calls if calls is not None else []
        self.last_usage=None
    def scoped(self): return FakeLLM(self.responder,self.calls)
    def complete_json(self,system,user,*,name,max_tokens,model=None):
        payload=json.loads(user);self.calls.append((name,payload))
        result=self.responder(name,payload)
        self.last_usage={"input_tokens":100,"output_tokens":20,"cost_usd":None}
        return result
    @staticmethod
    def default(name,p):
        if name=="plan":
            return {"intent":"analytical","aspects":[{"text":p["query"],"keywords":terms(p["query"])}],"documents":[]}
        if name=="survey":
            return {"pages":[{"page_no":c["page_no"],"aspects":["a1"],"strength":"high"} for c in p["cards"]]}
        if name=="verify":
            return {"keep":[{"id":e["id"],"aspects":["a1"],"support_span_ids":list(e["source_spans"]),"note":"source support"} for e in p["elements"]]}
        if name=="answer_select":  # ranks in the order given; code keeps each topic's quota
            return {"groups":[{"topic":g["topic"],"ranked":[f["id"] for f in g["facts"]]} for g in p["groups"]]}
        if name=="answer" and "max_statements" in p:  # cited-synthesis writer
            return {"status":"answered","sections":[{"heading":"Findings","statements":[{"kind":"finding",
                    "text":" ".join(e["source_spans"].values()),"obligation_ids":e["obligation_ids"][:1],
                    "cites":[{"evidence_id":e["id"],"span_ids":list(e["source_spans"])}]} for e in p["evidence"]]}]}
        if name=="answer":
            return {"status":"answered","selections":[{"obligation_id":e["obligation_ids"][0],
                    "evidence_id":e["id"],"span_ids":list(e["source_spans"])} for e in p["evidence"]]}
        if name=="answer_verify":
            return {"verdicts":[{"claim_id":c["claim_id"],"verdict":"supported"} for c in p["claims"]]}
        raise AssertionError(name)


class FakeReranker:
    max_pair_tokens=24
    def __init__(self): self.seen=[]
    def token_count(self,q,t): return len(re.findall(r"\S+",q))+len(re.findall(r"\S+",t))+3
    def score(self,q,texts):
        self.seen.extend((q,t) for t in texts)
        assert all(self.token_count(q,t)<=self.max_pair_tokens for t in texts)
        return [len(set(terms(q))&set(terms(t))) for t in texts]


def settings(tmp_path,**kwargs):
    return replace(QuerySettings(artifact_dir=tmp_path/"runs",strict_observability=False),**kwargs)
