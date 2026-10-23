"""Zero-call diagnostics alongside, never replacing, unchanged official scores."""
import re


def judge_consistency(metrics, answer):
    detail=metrics.get('answer_detail',{})
    bp=detail.get('benchmark_points',{});ap=detail.get('agent_points',{})
    matched=set(detail.get('matched_ids',[]));missing=set(detail.get('missing_ids',[]))
    extras=set(detail.get('extra_ids',[]));flags=[]
    if matched & missing:
        flags.append({'kind':'contradictory_benchmark_labels','ids':sorted(matched & missing)})
    if ap and set(ap)<=extras and matched:
        flags.append({'kind':'all_answer_points_extra_despite_benchmark_matches',
                      'matched_benchmark_count':len(matched),'extra_answer_count':len(extras)})
    elif ap and len(extras & set(ap))/len(ap)>=.9 and len(matched)>=3:
        flags.append({'kind':'possible_inconsistent_matching_nearly_all_answer_points_extra',
                      'matched_benchmark_count':len(matched),'extra_answer_count':len(extras)})
    for key in missing:
        point=bp.get(key,'')
        pages=re.findall(r'\bpage\s+(\d+)\b',point,re.I)
        names=re.findall(r'[\w.-]+\.pdf',point,re.I)
        for page in pages:
            for name in names:
                if re.search(re.escape(name)+r'\s+p'+page+r'\b',answer,re.I):
                    flags.append({'kind':'citation_present_but_judge_marks_missing','benchmark_id':key})
    return {'official_scores_unchanged':True,'flags':flags,
            'interpretation':'Flags require review; they do not compute corrected scores or prove semantic equivalence.'}
