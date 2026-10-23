import json
import math
from pathlib import Path
from .official import METRICS


def summarize(run_path,scores_path=None):
    rows=[json.loads(s) for s in Path(run_path).read_text().splitlines() if s.strip()]
    latency=sorted((r.get("metrics") or {}).get("latency_ms",r.get("capture_latency_ms",0)) for r in rows if not r.get("error"))
    known=[];unknown=0
    for row in rows:
        usage=(row.get("response") or {}).get("usage",{})
        if isinstance(usage.get("cost_usd"),(int,float)):
            known.append(usage["cost_usd"])
        else:
            unknown+=1
    output={"rows":len(rows),"query_failures":sum(bool(r.get("error")) for r in rows),"known_cost_total_usd":sum(known),
            "unknown_cost_rows":unknown,"latency_p50_ms":latency[len(latency)//2] if latency else None,
            "latency_p95_ms":latency[max(0,math.ceil(len(latency)*.95)-1)] if latency else None}
    if scores_path:
        scores=json.loads(Path(scores_path).read_text())
        output["scoring_summary"]=scores["summary"]
        output["worst_questions"]={m:[r["id"] for r in sorted(scores["per_question"],key=lambda r:r[m])[:10]] for m in METRICS}
    return output
