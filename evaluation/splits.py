"""Family-preserving split. Human-reviewed family assignments are required."""
import hashlib
import json
import random


def make_split(rows,families,seed=20261023,fraction=0.3):
    ids={r["id"] for r in rows}
    if set(families)!=ids or any(not isinstance(v,str) or not v for v in families.values()):
        raise ValueError("families must map every row ID to a reviewed nonempty family")
    groups={}
    for row in rows:
        groups.setdefault(families[row["id"]],[]).append(row["id"])
    names=sorted(groups);random.Random(seed).shuffle(names)
    target=len(rows)*fraction;holdout=[]
    for name in names:
        members=groups[name]
        if abs(len(holdout)+len(members)-target)<abs(len(holdout)-target):
            holdout.extend(members)
    if not holdout or len(holdout)==len(rows):
        raise ValueError("family grouping cannot produce a nonempty independent partition")
    result={"seed":seed,"dev":sorted(ids-set(holdout)),"holdout":sorted(holdout),"families":families,
            "warning":"Sources may overlap. Do not tune on holdout. Grouping requires human review."}
    result["manifest_sha256"]=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result
