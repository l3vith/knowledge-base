import argparse
import json
import subprocess
from pathlib import Path
from evaluation.runner import load_benchmark,flatten_gold_chunks,select_rows,capture,digest


def main():
    p=argparse.ArgumentParser();p.add_argument("--benchmark",required=True)
    transport=p.add_mutually_exclusive_group(required=True);transport.add_argument("--api");transport.add_argument("--local",action="store_true")
    p.add_argument("--mode",choices=["full","baseline"],default="full");p.add_argument("--env-file")
    p.add_argument("--collection",required=True);p.add_argument("--out",required=True);p.add_argument("--ids")
    p.add_argument("--split",choices=["dev","holdout","all"],default="dev");p.add_argument("--split-file")
    args=p.parse_args();rows=load_benchmark(args.benchmark)
    if args.env_file:
        from scripts.check_langfuse import load_local_env
        load_local_env(args.env_file)
    if args.api and args.mode!="full":
        p.error("baseline is an offline control; use --local --mode baseline")
    ids=args.ids.split(",") if args.ids else None
    if args.split!="all" and ids is None:
        if not args.split_file:
            p.error("a frozen reviewed --split-file is required; use --ids only for explicit diagnostics")
        ids=json.loads(Path(args.split_file).read_text(encoding="utf-8"))[args.split]
    selected=select_rows(rows,ids=ids)
    if not selected:
        p.error("no benchmark rows matched the requested partition or IDs")
    query_fn=None
    if args.local:
        from kb.routes.query import legacy_bind
        from kb.query.pipeline import answer_query
        def query_fn(collection,query):
            s=legacy_bind(collection)
            try:
                return answer_query(collection,query,store=s.store,generation_id=s.generation_id,settings=s.settings,
                                    llm=s.llm,embedder=s.embedder,reranker=s.reranker,sink=s.sink,mode=args.mode)
            finally:
                if s.close_store:
                    s.store.close()
    commit=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True).stdout.strip() or "uncommitted"
    print(json.dumps(capture(selected,api=args.api or "local:",collection=args.collection,out=args.out,source_hash=digest(args.benchmark),
                             query_fn=query_fn,run_metadata={"mode":args.mode,"code_commit":commit}),indent=2))

if __name__=="__main__":
    main()
