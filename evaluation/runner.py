"""M11: offline HTTP capture; all failures retained and resume inputs bound."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
import httpx


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_benchmark(path):
    rows=[json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids=[r["id"] for r in rows]
    if len(ids)!=len(set(ids)):
        raise ValueError("duplicate benchmark IDs")
    return rows


def flatten_gold_chunks(row):
    chunks=row.get("benchmark_chunks_w_metadata",{})
    if isinstance(chunks,dict):
        return [chunk["content"] for group in chunks.values() for chunk in group]
    return [chunk["content"] for chunk in chunks]


def select_rows(rows,ids=None,split=None,groups=None):
    allowed=set(ids) if ids is not None else set(split) if split is not None else None
    return [r for r in rows if (allowed is None or r["id"] in allowed) and (groups is None or r["id"][:1] in groups)]


def capture(rows,*,api,collection,out,source_hash,timeout=180,query_fn=None,run_metadata=None):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    manifest_path=out.with_suffix(out.suffix+".manifest.json")
    config={"dataset_sha256":source_hash,"ids":[r["id"] for r in rows],"api":api.rstrip("/"),"collection":collection,"schema":"track-b-2.0","run_metadata":run_metadata or {}}
    manifest={"config":config,"generation_id":None,"system_config_sha256":None,"created_unix":time.time()}
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["config"]!=config:
            raise ValueError("resume manifest differs: use a new output path")
    elif out.exists() and out.stat().st_size:
        raise ValueError("cannot resume unmanifested output")
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    done=set()
    if out.exists():
        records=[json.loads(s) for s in out.read_text(encoding="utf-8").splitlines() if s.strip()]
        done={r["id"] for r in records}
        if len(done)!=len(records):
            raise ValueError("duplicate rows in existing run")
    with httpx.Client(timeout=timeout) as client, out.open("a", encoding="utf-8") as target:
        for row in rows:
            if row["id"] in done:
                continue
            record={"id":row["id"],"query":row["question"],"benchmark_answer":row["benchmark_answer"],
                    "benchmark_chunks":flatten_gold_chunks(row),"error":None}
            start=time.monotonic()
            try:
                if query_fn is None:
                    response=client.post(api.rstrip("/")+"/query",json={"collection_name":collection,"query":row["question"]})
                    response.raise_for_status();body=response.json()
                else:
                    body=query_fn(collection,row["question"])
                record["response"]=body
                if not isinstance(body.get("answer"),str) or not isinstance(body.get("chunks"),list):
                    raise ValueError("invalid query response")
                generation=body.get("generation_id")
                if not generation:
                    raise ValueError("response missing bound generation")
                if manifest["generation_id"] is not None and manifest["generation_id"]!=generation:
                    raise ValueError("collection generation changed during evaluation")
                manifest["generation_id"]=generation
                system_config=body.get("config_sha256")
                if manifest.get("system_config_sha256") is not None and manifest["system_config_sha256"]!=system_config:
                    raise ValueError("system configuration changed during evaluation")
                manifest["system_config_sha256"]=system_config
                record.update(ai_answer=body["answer"],retrieved_chunks=[c["content"] for c in body["chunks"]],
                              generation_id=generation,status=body.get("status"),trace=body.get("trace"),
                              metrics=body.get("metrics"),response=body)
            except Exception as exc:
                record.update(error={"type":type(exc).__name__,"message":"Query capture failed; no row silently excluded"},
                              ai_answer="",retrieved_chunks=[])
            record["capture_latency_ms"]=round((time.monotonic()-start)*1000,3)
            target.write(json.dumps(record,ensure_ascii=False)+"\n");target.flush()
            manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest
