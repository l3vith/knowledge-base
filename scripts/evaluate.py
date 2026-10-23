import argparse
import json
from evaluation.official import evaluate_file,load_notebook_namespace,EXPECTED_EVALUATOR_SHA256


def main():
    p=argparse.ArgumentParser();p.add_argument("run");p.add_argument("--notebook",required=True)
    p.add_argument("--expected-sha256",default=EXPECTED_EVALUATOR_SHA256);args=p.parse_args()
    result=evaluate_file(args.run,notebook=args.notebook,expected_hash=args.expected_sha256)
    print(json.dumps(result["summary"],indent=2))

if __name__=="__main__":
    main()
