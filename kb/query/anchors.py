"""Immutable source-offset anchors. Models select IDs; code owns every source string."""
from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType
from .utils import get, answer_spans, display_source

# Match raw numeric punctuation, including PDF-to-Markdown italic punctuation.
_DIGITS=r'\d+(?:(?:\s*_,_\s*|,\s*)\d{3})*'
_NUMBER=re.compile(r'(?<![\w])(?:[<>≤≥]\s*)?[+−-]?'+_DIGITS+r'(?:(?:\s*_\._\s*|\s*\.\s*)\d+)?(?:\s*(?:%|(?:micro|milli|nano)?seconds?|minutes?|hours?|days?|weeks?|months?|years?|calls?|paths?|points?|KB|MB|GB|USD|EUR|GBP|INR|million|billion|bps))?')


@dataclass(frozen=True)
class SourceAnchor:
    anchor_id: str
    parent_element_id: str
    doc_id: str
    page_no: int
    char_start: int
    char_end: int
    text: str
    kind: str
    owner_span_id: str | None = None


def _identity(element):
    return get(element,'parent_element_id') or get(element,'element_id')


def _anchor(element,start,end,kind,owner=None):
    text=get(element,'text');base=get(element,'char_start',0)
    raw='\x00'.join(map(str,(get(element,'doc_id'),_identity(element),base+start,base+end,kind,text[start:end])))
    prefix='V' if kind=='value' else 'A'
    return SourceAnchor(prefix+hashlib.sha256(raw.encode()).hexdigest()[:24],_identity(element),
        get(element,'doc_id'),get(element,'page_no'),base+start,base+end,text[start:end],kind,owner)


class SourceCatalog:
    def __init__(self,numbered):
        anchors={};by_evidence={};value_ids={};owners={};headers={}
        for eid,ev in numbered.items():
            element=get(ev,'element',ev);text=get(element,'text','');sentences=[];values=[];cursor=0
            pieces=list(answer_spans(text,get(element,'kind','text')).values())
            if get(element,'kind')=='table' and '|' in text:
                pieces=[line for line in text.splitlines(keepends=True) if line.strip() and not re.fullmatch(r'[|:\-\s]+',line)]
            for source in pieces:
                start=text.find(source,cursor)
                if start<0:raise ValueError('Source sentence has no exact offset')
                end=start+len(source);cursor=end
                kind=('table_header' if not sentences else 'table_row') if get(element,'kind')=='table' else 'sentence'
                anchor=_anchor(element,start,end,kind)
                anchors[anchor.anchor_id]=anchor;sentences.append(anchor.anchor_id);owners[anchor.anchor_id]=eid
                if kind=='table_header':headers[eid]=anchor.anchor_id
                for match in _NUMBER.finditer(source):
                    # Citation/footnote numbers are not standalone value candidates.
                    at=match.start()
                    if (at and source[at-1]=='[') or '<sup>' in source[max(0,at-6):at]:continue
                    val=_anchor(element,start+match.start(),start+match.end(),'value',anchor.anchor_id)
                    anchors[val.anchor_id]=val;values.append(val.anchor_id);owners[val.anchor_id]=eid
            # Legacy verified quotations may end inside a sentence; preserve their own exact range.
            for quote in get(ev,'quotes',[]) or []:
                if not isinstance(quote,str) or not quote or quote not in text:continue
                if any(anchors[a].text==quote for a in sentences):continue
                start=text.index(quote);anchor=_anchor(element,start,start+len(quote),'support')
                anchors[anchor.anchor_id]=anchor;sentences.append(anchor.anchor_id);owners[anchor.anchor_id]=eid
            by_evidence[eid]=tuple(sentences);value_ids[eid]=tuple(values)
        self.anchors=MappingProxyType(anchors);self.by_evidence=MappingProxyType(by_evidence)
        self.value_ids=MappingProxyType(value_ids);self.owners=MappingProxyType(owners);self.headers=MappingProxyType(headers)

    def aliases(self):
        counts={'A':0,'V':0};forward={};reverse={}
        for sid,anchor in self.anchors.items():
            prefix='V' if anchor.kind=='value' else 'A';counts[prefix]+=1
            alias=prefix+str(counts[prefix]);forward[alias]=sid;reverse[sid]=alias
        return forward,reverse

    def spans(self,eid):
        return {a:self.anchors[a].text for a in self.by_evidence[eid]}

    def values(self,eid):
        return [{'id':a,'text':self.anchors[a].text,'span_id':self.anchors[a].owner_span_id}
                for a in self.value_ids[eid]]

    def anchored_values(self,anchor_ids):
        ranges=[self.anchors[a] for a in anchor_ids if a in self.anchors]
        return list(dict.fromkeys(a.anchor_id for a in self.anchors.values() if a.kind=='value' and any(
            a.doc_id==r.doc_id and a.parent_element_id==r.parent_element_id and
            r.char_start<=a.char_start<a.char_end<=r.char_end for r in ranges)))

    def source_quotes(self,anchor_ids):
        return [{'evidence_id':self.owners[a],'quote':self.anchors[a].text} for a in anchor_ids]

    def scope(self,anchor_id,doc_id):
        # A selected source sentence is an explicit anchor, not a canonicalized/generated label.
        anchor=self.anchors.get(anchor_id) if isinstance(anchor_id,str) else None
        return anchor_id if anchor and anchor.kind!='value' and anchor.doc_id==doc_id else None


def source_format_key(text):
    """Compatibility-only punctuation equivalence, never semantic/fuzzy value matching."""
    text=display_source(text)
    text=re.sub(r'(?<=\d)\s*([.,])\s*(?=\d)',r'\1',text)
    return text
