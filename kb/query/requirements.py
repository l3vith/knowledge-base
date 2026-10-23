"""Literal requested-topic checklist, never generated facts or rewritten source text."""
import re


# Only terms actually present in the original user query can create a checklist item.
# These generic axes span scientific, operational and policy questions; no corpus IDs/gold.
_AXES = (
    r"accuracy|precision|recall|error rates?",
    r"speed|latency|throughput|runtime|run time",
    r"(?:build|building|construction|training|operating|operational) costs?|costs?",
    r"limitations?|caveats?|assumptions?",
    r"controls?|safeguards?|requirements?",
    r"conceptual soundness",
    r"(?:ongoing )?monitoring",
    r"outcomes analysis|validation",
    r"outside (?:its|the) original purpose|out[- ]of[- ](?:purpose|domain)",
)


def requested_topics(query, intent):
    if intent == 'factoid':
        return []
    matches=[]
    for pattern in _AXES:
        match=re.search(r'\b(?:'+pattern+r')\b',query,re.I)
        if match:
            matches.append((match.start(),match.end(),match.group()))
    return [{'id':f'R{i+1}','text':text,'query_start':start,'query_end':end}
            for i,(start,end,text) in enumerate(sorted(matches))]


def audit_topic_coverage(requirements, rows, accepted_claims):
    """Fail closed on missing/duplicate checks or references to rejected claims."""
    accepted={c.claim_id for c in accepted_claims}
    by_id={};duplicates=set()
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict) or not isinstance(row.get('requirement_id'),str):continue
        key=row['requirement_id']
        if key in by_id:duplicates.add(key)
        by_id[key]=row
    result=[]
    for requirement in requirements:
        row=by_id.get(requirement['id'],{})
        ids=row.get('claim_ids',[])
        valid=isinstance(ids,list) and bool(ids) and all(isinstance(c,str) and c in accepted for c in ids)
        supported=(requirement['id'] not in duplicates and row.get('status')=='supported' and valid)
        result.append({**requirement,'status':'supported' if supported else 'unresolved',
                       'claim_ids':list(dict.fromkeys(ids)) if valid else []})
    return result
