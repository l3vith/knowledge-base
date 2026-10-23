import argparse
import json
from pathlib import Path
from evaluation.runner import load_benchmark
from evaluation.splits import make_split


def main():
    p=argparse.ArgumentParser();p.add_argument("--benchmark",required=True);p.add_argument("--families",required=True)
    p.add_argument("--out",required=True);args=p.parse_args()
    result=make_split(load_benchmark(args.benchmark),json.loads(Path(args.families).read_text(encoding="utf-8")))
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"dev":len(result["dev"]),"holdout":len(result["holdout"]),"manifest_sha256":result["manifest_sha256"]}))

if __name__=="__main__":
    main()
