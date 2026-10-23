"""Check a live deployment against the PS §11.3 contract: POST /index, then POST /query, then the route list.

    python scripts/smoke_http.py --url http://SERVER:8000 --zip sample.zip --collection smoke --query "..."

Costs one real query (~$0.04) unless the server runs with KB_LLM_MODE=dryrun. Without --zip it only queries.
"""
import argparse
import re
import sys
import time
import httpx


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True); p.add_argument("--collection", required=True)
    p.add_argument("--query", required=True); p.add_argument("--zip")
    a = p.parse_args(); base = a.url.rstrip("/"); ok = True

    def check(name, cond):
        nonlocal ok
        ok &= bool(cond); print(("  OK   " if cond else "  FAIL ") + name)

    with httpx.Client(timeout=None) as http:
        if a.zip:
            t = time.time()
            with open(a.zip, "rb") as f:
                r = http.post(base + "/index", data={"collection_name": a.collection}, files={"file": (a.zip, f, "application/zip")})
            print(f"/index -> HTTP {r.status_code} in {time.time() - t:.1f}s: {r.text[:300]}")
            check("/index succeeded", r.status_code == 200)
        t = time.time()
        r = http.post(base + "/query", json={"collection_name": a.collection, "query": a.query})
        print(f"/query -> HTTP {r.status_code} in {time.time() - t:.1f}s")
        check("/query succeeded", r.status_code == 200)
        if r.status_code == 200:
            b = r.json(); chunks = b.get("chunks", [])
            got = {(c.get("document"), c.get("page")) for c in chunks}
            check("answer is non-empty text", isinstance(b.get("answer"), str) and b["answer"].strip())
            check("chunks returned", chunks)
            check("every chunk has document + int page", all(c.get("document") and isinstance(c.get("page"), int) for c in chunks))
            check("trace steps have exactly 4 keys", b.get("trace") and all(set(s) == {"step_name", "description", "input", "output"} for s in b["trace"]))
            check("answer cites only returned chunks", all((d, int(n)) in got for d, n in re.findall(r"\[([^\[\]]+?\.pdf) p(\d+)\]", b["answer"])))
            check("Langfuse trace id present", b.get("trace_id"))
            print(f"  status={b.get('status')} chunks={len(chunks)} usage={b.get('usage')}")
            print("  answer:", b.get("answer", "")[:300].replace("\n", " "))
        for path in ("/health", "/docs", "/openapi.json"):
            check(f"{path} not exposed (only /index and /query)", http.get(base + path).status_code == 404)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
