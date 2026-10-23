import argparse
import json
from evaluation.report import summarize


def main():
    p=argparse.ArgumentParser();p.add_argument("run");p.add_argument("--scores");args=p.parse_args()
    print(json.dumps(summarize(args.run,args.scores),indent=2))

if __name__=="__main__":
    main()
