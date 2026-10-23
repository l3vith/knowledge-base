"""Zero-call diagnostics alongside, never replacing, unchanged official scores."""
import json
from pathlib import Path
import re

CHECKLISTS=Path(__file__).with_name('checklists.json')


def judge_consistency(metrics, answer, judge_calls=()):
    detail=metrics.get('answer_detail',{})
    bp=detail.get('benchmark_points',{});ap=detail.get('agent_points',{})
    matched_list=detail.get('matched_ids',[]);missing_list=detail.get('missing_ids',[]);extra_list=detail.get('extra_ids',[])
    matched=set(matched_list);missing=set(missing_list);extras=set(extra_list);flags=[]
    if matched & missing:
        flags.append({'kind':'contradictory_benchmark_labels','ids':sorted(matched & missing)})
    if ap and set(ap)<=extras and matched:
        flags.append({'kind':'all_answer_points_extra_despite_benchmark_matches',
                      'matched_benchmark_count':len(matched),'extra_answer_count':len(extras)})
    elif ap and len(extras & set(ap))/len(ap)>=.9 and len(matched)>=3:
        flags.append({'kind':'possible_inconsistent_matching_nearly_all_answer_points_extra',
                      'matched_benchmark_count':len(matched),'extra_answer_count':len(extras)})
    unknown=sorted((matched|missing)-set(bp))+sorted(extras-set(ap))
    if unknown:
        flags.append({'kind':'unknown_point_ids','ids':unknown})
    duplicates=sorted({i for ids in (matched_list,missing_list,extra_list) for i in ids if ids.count(i)>1})
    if duplicates:
        flags.append({'kind':'duplicate_point_ids','ids':duplicates})
    unlabelled=sorted(set(bp)-matched-missing)
    if unlabelled:
        flags.append({'kind':'benchmark_points_neither_matched_nor_missing','ids':unlabelled})
    if re.search(r'\[[^\]]*\.pdf p\d+',answer) and ap and not any(re.search(r'\.pdf|\bpage\b|\bp\d+\b',p,re.I) for p in ap.values()):
        flags.append({'kind':'citations_in_answer_dropped_by_decomposition'})
    for key in missing:
        point=bp.get(key,'')
        pages=re.findall(r'\bpage\s+(\d+)\b',point,re.I)
        names=re.findall(r'[\w.-]+\.pdf',point,re.I)
        for page in pages:
            for name in names:
                if re.search(re.escape(name)+r'\s+p'+page+r'\b',answer,re.I):
                    flags.append({'kind':'citation_present_but_judge_marks_missing','benchmark_id':key})
    truncated=[c['request_sha256'] for c in judge_calls if c.get('finish_reason')=='length' or c.get('escalated')]
    if truncated:
        flags.append({'kind':'judge_response_truncated_at_notebook_limit','requests':truncated})
    return {'official_scores_unchanged':True,'flags':flags,
            'interpretation':'Flags require review; they do not compute corrected scores or prove semantic equivalence.'}


def checklist(question_id, answer, path=CHECKLISTS):
    """Development-only factual checklist: which hand-listed benchmark facts the answer states (regex, no model)."""
    items=json.loads(Path(path).read_text(encoding='utf-8')).get(question_id)
    if not items:
        return None
    hit=[name for name,patterns in items.items() if all(re.search(p,answer,re.I) for p in patterns)]
    return {'covered':len(hit),'total':len(items),'missing':[name for name in items if name not in hit]}
