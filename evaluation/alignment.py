"""Offline diagnostics only. No guessed source aliases and no hard-negative labels."""
import re


def normalize(text):
    return " ".join(re.findall(r"\w+",text.casefold()))


def containment(passage,source,n=5):
    a=normalize(passage);b=normalize(source)
    if not a or not b:
        return 0.0
    if len(a)<n:
        return float(a in b)
    grams={a[i:i+n] for i in range(len(a)-n+1)}
    return sum(g in b for g in grams)/len(grams)


def align_reference(reference_name,passage,elements,verified_aliases=None,threshold=0.8):
    aliases=verified_aliases or {}
    alias=aliases.get(reference_name)
    if alias and (alias.get("status")!="identity_verified" or not alias.get("identity_evidence")):
        raise ValueError("aliases require reviewed identity evidence")
    source_name=alias["source_name"] if alias else reference_name
    possible=[e for e in elements if e["document"]==source_name]
    if not possible:
        return {"status":"absent_by_filename","reference":reference_name,"matches":[],"unique_missing_facts":None}
    matches=[{"chunk_id":e["chunk_id"],"page":e["page"],"containment":containment(passage,e["content"])} for e in possible]
    matches=[m for m in matches if m["containment"]>=threshold]
    return {"status":"candidate_span_match" if matches else "unresolved","reference":reference_name,"matches":matches,
            "warning":"Overlap is not factual equivalence or a hard relevance label"}
