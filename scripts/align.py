import argparse
import json
from pathlib import Path
from evaluation.alignment import align_reference
from evaluation.runner import load_benchmark


def main():
    p=argparse.ArgumentParser();p.add_argument("--benchmark",required=True);p.add_argument("--elements",required=True)
    p.add_argument("--verified-aliases");p.add_argument("--out",required=True);args=p.parse_args()
    elements=json.loads(Path(args.elements).read_text());aliases=json.loads(Path(args.verified_aliases).read_text()) if args.verified_aliases else {}
    result=[]
    for row in load_benchmark(args.benchmark):
        for name,chunks in row["benchmark_chunks_w_metadata"].items():
            for c in chunks:
                result.append({"question_id":row["id"],**align_reference(name,c["content"],elements,aliases)})
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"reference_passages":len(result),"automatic_thresholds_enabled":False}))

if __name__=="__main__":
    main()
