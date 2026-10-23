# Deployment

## The official endpoint is the organisers' server (PS §11.3, §11.4, §16)
- The organisers give each team a server, and the submission confirms that `/index` and `/query` are live **on that server**.
- Judging: the organisers `POST /index` with the hidden zip and their own `collection_name`, then call `/query` once per hidden question. We never see the hidden documents, so **ingestion runs on the judged host**. Nothing can be prebuilt on the PC.
- We must state a tentative ingestion time, and the organisers' timeout is that time plus a buffer. Measure it on the server itself at $0:
  ```bash
  KB_LLM_MODE=dryrun python scripts/index_local.py --src Train/Train/Documents --collection timing
  ```
  Then add about 1 min for the real doc-card calls and a 1.5× safety margin.
- `/index` is blocking, but indexing runs in a worker thread. If the caller's HTTP client gives up, indexing still finishes and promotes the collection.
- Server setup: `pip install -r requirements.txt`, `python scripts/prefetch_models.py`, put the keys in `.env`, then the `startCommand` from `render.yaml`. Leave `KB_RERANKER` and `KB_PARSE_WORKERS` at their defaults if the server has ≥ 2 GB RAM.

### Organiser-server checklist (in order)
1. `git clone` the repo, then `pip install -r requirements.txt` and `python scripts/prefetch_models.py`. The models are downloaded once, so the hidden run doesn't download anything.
2. Authenticate OpenCode on the server: either run `opencode auth login` there (with `OPENCODE_API_KEY` left empty, the app reads the CLI login in memory via `opencode auth export`), or set `OPENCODE_API_KEY`. Every call is locked to `qwen3.8-flash` with thinking disabled, and any other model name refuses to start. Then create `.env` with `LLM_MODEL=qwen3.8-flash`, the Langfuse keys and `LANGFUSE_BASE_URL`, `PRICE_INPUT_PER_M`/`PRICE_OUTPUT_PER_M`, and `KB_BUDGET_USD` set to the credit left for the hidden run. Keep `KB_REQUIRE_LANGFUSE=1`, since every query must be traced.
3. Measure ingestion at $0 (the command above) and state the result × 1.5 as the tentative ingestion time.
4. Start the server reachable from outside: `python scripts/serve.py --host 0.0.0.0 --port 8000` (it loads `.env`). Keep it running with `nohup`/`tmux` or a service.
5. From another machine, verify the contract (one real query ≈ $0.04):
   ```bash
   python scripts/smoke_http.py --url http://SERVER:8000 --zip one_doc.zip --collection smoke --query "Which rating agency rates the company?"
   ```
   It checks `/index`, `/query`, chunk document + page, the 4-key trace, the citations and the Langfuse trace id, and that `/health`, `/docs` and `/openapi.json` return 404.
6. Submit the URL. Don't re-index or restart during judging: the active generation and caches live in `data/`.

**Render, Atlas and Vercel below are only a public demo or backup for `/query`. They are not the judged endpoint.**

## Measured on the dev PC (16 logical cores), 2026-10-24
| Quantity | Value |
|---|---|
| Full fresh ingest of the 6,970-page training corpus (classic parse, extractive page cards, no LLM) | **18.1 min** (parse 14.0 min, embeddings 4.0 min). The layout parser took 31.6 min. |
| Re-index of unchanged files (content-hash cache) | seconds for parsing |
| Ingestion CPU work | ≈ 75 CPU-minutes (parse + 110 OCR pages + embeddings) |
| Query-side RAM (FastAPI + embedder + cross-encoder + index vectors) | ≈ 490 MB (≈ 390 MB with `KB_RERANKER=0`) |
| One generation of the training index | 155 MB raw (smaller gzipped in Atlas) |

| Host (free tier) | Limits | Consequence |
|---|---|---|
| Render | 512 MB RAM, 0.1 CPU, sleeps after 15 min idle (~1 min wake-up), ephemeral disk; HTTP requests reportedly capped at 100 min (community forum, not official docs) | **Serving queries works.** Indexing a 7k-page zip would take many hours (≈ 75 CPU-min at 0.1 CPU), well past the request cap, so a judged `/index` would fail there. |
| Vercel | serverless, 300 s max per request, 2 GB RAM, 500 MB Python bundle | Can't run a blocking multi-minute `/index`, and every cold start would re-download models and the index. Use it for a static UI only. |
| Atlas | one free cluster, ≈ 512 MB storage | Holds the active generation of each collection (only the active one is kept remotely). |

## Demo / backup workflow (free tiers)
1. **Add the keys** to `.env` at the repo root: `OPENCODE_API_KEY`, `MONGODB_URI`, the Langfuse keys and `KB_BUDGET_USD` (see `docs/CREDIT_PLAN.md`).
2. **Index on the PC.** The heavy CPU work happens here, and the result is uploaded to Atlas automatically when `MONGODB_URI` is set:
   ```bash
   python scripts/index_local.py --src Train/Train/Documents --collection train
   ```
   An existing local index can be pushed without re-indexing (no LLM calls):
   ```bash
   python scripts/push_collection.py --collection train
   ```
3. **Deploy Render** from `render.yaml` (Render dashboard → New → Blueprint → this repo). Then set the secret env vars (`OPENCODE_API_KEY`, `MONGODB_URI`, `KB_BUDGET_USD`, Langfuse keys).
   - The build bakes the CPU models into `./models` (`scripts/prefetch_models.py`).
   - The service starts with `KB_RERANKER=0` and `KB_PARSE_WORKERS=1`.
4. **First query after a cold start:**
   - Render wakes (~1 min).
   - It downloads the active generation from Atlas into `/tmp/kb-data`, then answers.
   - Later queries use the local copy until the instance sleeps again.

## MongoDB Atlas setup
1. Create a free cluster, then a database user.
2. Under **Network Access**, allow `0.0.0.0/0`, because Render's outbound IPs are not fixed.
3. Copy the `mongodb+srv://…` connection string into `MONGODB_URI`. The database name defaults to `knowledge_base` (`MONGODB_DB`).

**What it stores:** GridFS bucket `kb_files` holds `<collection>/<generation>/<file>.gz`, and the `collections` collection holds one pointer document per collection. The pointer switches only after every file has uploaded, so a failed upload never activates a partial index.

## Vercel (optional)
Host a static page that calls the Render API's `/query` and renders the answer, the cited chunks and the trace. That is the bonus UI the problem statement mentions. Don't host the Python API itself on Vercel (300 s limit, cold-start downloads).
