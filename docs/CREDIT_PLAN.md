# Credit plan: the $10 OpenCode key

Rule: **everything that can run on the PC runs on the PC first.** Only planning, page survey, element verification and the final answer need the LLM at query time. Doc cards are the only LLM work at ingestion.

## Where LLM credit goes (and what is $0)

| Step | Where it runs | Cost |
|---|---|---|
| Unzip, parse, OCR, segmentation, boilerplate, identifiers | PC CPU | $0 |
| Page cards (`KB_PAGE_CARDS=extractive`, default) | PC CPU | $0 |
| Page cards (`KB_PAGE_CARDS=llm`, optional) | LLM | ≈ $1.75 per 7k pages (872 calls × ~3.9k in / ~0.7k out) |
| Doc cards (one per document) | LLM | ≈ $0.05 for 35 docs |
| Embeddings, BM25, cross-encoder triage, citation rendering | PC CPU | $0 |
| Query: plan + survey + verify + answer | LLM | ≈ $0.01–0.05 per query (to be measured in dry-run mode) |
| Re-running the same prompt (any step) | `data/llm_cache.sqlite` | $0 |
| Re-indexing unchanged files | `data/cache/` | $0 |
| Evaluation judge (`Evaluation.ipynb`) | LLM, same key, **not cached** | ≈ $0.02–0.04 per question |

## Built-in protections
- **`KB_BUDGET_USD` (hard cap).** Before every call, `kb/llm.py` adds up `data/spend.jsonl` and refuses the call once the cap is reached. Every stage then degrades gracefully to its fallback. Raise the cap one stage at a time.
- **Response cache.** An identical model + prompt pair is paid for once. Temperature is 0, so reusing a cached answer is safe.
- **Ingestion cache.** Parsed pages, cards and vectors are reused for byte-identical files. Fallback cards are never cached.
- **Dry-run mode (`KB_LLM_MODE=dryrun`).** The whole pipeline runs with rule-based stand-in answers, no network and $0. It records *estimated* tokens and cost, so we can price a run before spending anything.
- **Isolated tests.** Tests never read `.env`, never touch the network and never spend.

## Stages (do them in order; stop and review after each)

| Stage | What | Cap to set | Expected spend |
|---|---|---|---|
| 0 | `python -m pytest -q`; full ingest + sample queries with `KB_LLM_MODE=dryrun` (once Track B lands) to get real token estimates | — | $0 |
| 1 | `python scripts/check_llm.py`: key, endpoint, model list, reasoning-token overhead | 0.05 | ≈ $0.0002 |
| 2 | Index the training set for real (doc cards only, extractive page cards) | 0.25 | ≈ $0.05 |
| 3 | 3 smoke queries (one fact, one broad review, one unanswerable) | 0.50 | ≈ $0.05–0.15 |
| 4 | Dev evaluation on **10 stratified questions** (≈4 A, 3 B, 3 C) | 1.50 | ≈ $0.4–0.8 |
| 5 | Optional A/B: re-index with `KB_PAGE_CARDS=llm`, then re-run the same 10 questions | 3.50 | ≈ $1.8 + $0.5 |
| 6 | Tuning iterations: only the failing questions, 1–3 at a time | 4.50 | ≈ $1 |
| — | **Reserve for the judges' hidden-set run: never touch** | — | **≥ $5** |

**Hidden-run estimate:** about $0.05 ingestion (extractive page cards) plus N queries × $0.01–0.05. For 100 questions that is about $1–5. Stage 0's dry-run figures replace these estimates with measured ones.

**Stop rules:**
- If any stage spends more than 2× its estimate, stop and check `data/spend.jsonl` (each line names the step).
- Never run all 100 benchmark questions during development.
- Never evaluate the same unchanged configuration twice (the judge is not cached).
