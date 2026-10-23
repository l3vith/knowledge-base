"""Explicit connectivity check. Never prints keys or creates model usage records."""
import argparse
import json
import os
from pathlib import Path
import time
from datetime import datetime, timedelta, timezone
import httpx


def load_local_env(path):
    for line in Path(path).read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#"):
            continue
        key,sep,value=line.partition("=")
        if sep and key.replace("_","").isalnum():
            os.environ.setdefault(key,value.strip().strip('"').strip("'"))


def check(env_file=None):
    if env_file:
        load_local_env(env_file)
    from langfuse import Langfuse
    base=os.getenv("LANGFUSE_BASE_URL",os.getenv("LANGFUSE_HOST","https://cloud.langfuse.com"))
    public=os.environ["LANGFUSE_PUBLIC_KEY"];secret=os.environ["LANGFUSE_SECRET_KEY"]
    client=Langfuse(public_key=public,secret_key=secret,base_url=base,sample_rate=1.0)
    if not client.auth_check():
        raise RuntimeError("Langfuse authentication failed")
    with client.start_as_current_observation(name="track-b-connectivity-smoke",as_type="span",input={"kind":"connectivity-only; no model inference"}) as span:
        trace_id=client.get_current_trace_id()
        span.update(output={"status":"connectivity smoke; not an accuracy/cost benchmark"})
    client.flush()
    received=False
    with httpx.Client(timeout=15,auth=httpx.BasicAuth(public,secret)) as http:
        for attempt in range(8):
            now=datetime.now(timezone.utc)
            response=http.get(base.rstrip("/")+"/api/public/v2/observations",params={
                "traceId":trace_id,"fields":"core,basic","limit":100,
                "fromStartTime":(now-timedelta(hours=1)).isoformat(),"toStartTime":(now+timedelta(minutes=5)).isoformat()})
            if response.status_code==200 and any(row.get("traceId")==trace_id for row in response.json().get("data",[])):
                received=True;break
            if response.status_code not in (200,404,429):
                break
            time.sleep(3)
    result={"authentication":"passed","trace_id":trace_id,"remote_trace_received":received,"base_url":base,
            "trace_url":client.get_trace_url(trace_id=trace_id),"model_inference":"not_run"}
    path=Path("artifacts/checks/langfuse-connectivity.json");path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+"\n")
    client.shutdown()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument("--env-file");args=p.parse_args()
    print(json.dumps(check(args.env_file),indent=2))

if __name__=="__main__":
    main()
