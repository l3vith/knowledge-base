# Person 2 implementation handoff

## Implemented scope

M6 compiles obligations and guards entity/period/identifier scope. M7 provides lexical/dense page candidates, complementary slot allocation, canonical element retrieval and token-aware CPU reranking. M8 surveys finite page cards and verifies exact source fragments with quote validation. M9 selects a coverage portfolio, generates structured claims, checks numeric derivations and semantic support, and renders citations deterministically. M10 executes ten ordered stages and exposes POST /query. M11 captures/evaluates runs, preserves official definitions, creates reviewed-family splits and conservative source-alignment diagnostics.

Person 1's M0/M1–M5 were fetched from the repository, with ingestion commit f8bdd6b as the initial integration base. Query modules accept its StoreProtocol structurally, without a second production database. `kb/routes/query.py:legacy_bind` binds Registry/Store once per request and closes the read handle after completion. It injects the query-owned OpenCode transport; custom deployments/tests may supply app.state.query_services returning BoundServices. M0 errors are accepted structurally at the route boundary. Tests use both isolated query fakes and the actual shared PDF/index/store stack.

## Intentional differences from the old plan

- Ten stages: answer_verification is inserted before citation_render. All trace entries retain exactly step_name, description, input and output.
- Claims are structured, supported by exact quotes and reviewed before rendering. Unknown citation IDs reject the whole assertion. Model errors cannot become false no-information answers.
- `/query` statuses are answered, partial and no_answer. All writer-visible source chunks are returned, including uncited context. `content` and `text` are raw source fragments; generated headers are not prepended as original evidence.
- The query transport requires an explicit model/key, validates whole JSON, enforces request-aware call budgets and treats unknown pricing/usage as null. It makes one transport attempt per model call; no hidden provider retries are performed. Failed billed JSON responses retain known usage.
- Explicit entity/year comparisons bypass soft routing caps. A year inside a regulatory identifier is not a requested reporting year. Uncertain legacy metadata remains soft, rather than falsely becoming a verified constraint.
- Cross-encoder logits order work only. A cloned tokenizer disables truncation/padding for counting; query+special tokens fit each scored window. Missing tokenizer support causes a disclosed skip. Source tails are never declared verified without visibility.
- Full attempt/evidence artifacts stay in ignored artifacts/runs. Root response includes bound generation and configuration hash; secrets are excluded from config snapshots.
- Shared API change: removed GET /health and made missing required router imports fatal. The updated foundation test checks exactly the two allowed routes. Other shared foundation/storage code is preserved.

## Files and seams

Query-owned records/defaults/runtime/client/tracing are under kb/query rather than replacing kb/models.py, kb/config.py, kb/llm.py or kb/tracing.py. The compatibility functions retain original filenames plan.py, screen.py, pipeline.py; they correspond to the unified plan's planner/routing, survey/verify and executor responsibilities. The unified schema's future source records are not falsely claimed to exist in the current legacy compiler.

The route may use the combined kb.api app. kb.query.demo_app is a one-route local test harness only, never the submission app. Production needs real storage, pretrained model artifacts, OpenCode credentials, Langfuse and a validated price record. Current query transport leaves prices unknown until configured; no guessed price is reported as verified.

## Verified in this work

Python 3.12 on Apple Silicon; exact shared direct dependency pins installed, pip check passed. Default combined suite: 105 passed, 7 slow tests deselected. Separately, the real pretrained embedding/reranker load-and-score test passed, as did the query adapter's real tokenizer/window/reranking test. Real PDF ingestion→SQLite/vector store→HTTP query was tested across two named collections; old-reader behavior after reindex and actual document/page citations passed. Official evaluator definition cells loaded unchanged and its supplied SHA-256 matched.

Langfuse credentials authenticated and a connectivity-only span was confirmed through the current v2 Observations API. The old trace-read endpoint returns 410 for this project; the check script uses v2 instead. This proves connectivity/export for that smoke, not official query metrics. No live OpenCode inference or official metric run was performed because the local organizer model key remained unset. No cost/latency/accuracy claim is inferred from synthetic replies.

## Offline evaluation commands

Prepare a manually reviewed JSON map of every question ID to a query family. Shared source documents mean family holdout is weaker than an unseen-corpus test; disclose that limitation. Freeze the split before tuning:

```bash
.venv/bin/python -m scripts.make_split --benchmark /path/benchmark_100.jsonl --families /path/reviewed-families.json --out artifacts/split.json
.venv/bin/python -m scripts.run_benchmark --benchmark /path/benchmark_100.jsonl --api http://127.0.0.1:8000 --collection train --split dev --split-file artifacts/split.json --out artifacts/dev.jsonl
.venv/bin/python -m scripts.run_benchmark --benchmark /path/benchmark_100.jsonl --local --mode baseline --env-file .env --collection train --split dev --split-file artifacts/split.json --out artifacts/baseline.jsonl
.venv/bin/python -m scripts.evaluate artifacts/dev.jsonl --notebook /path/Evaluation.ipynb
.venv/bin/python -m scripts.report artifacts/dev.jsonl --scores artifacts/dev.jsonl.scores.json
```

The evaluation command reads credentials from process environment; it never edits the notebook. It hashes the original, executes its definition cells verbatim, and skips the sample invocation. Failed query/judge rows remain visible. Official count-ratio context recall can exceed one; no clipping or altered scoring. Alignment requires reviewed identity aliases before overlap checks and never generates automatic hard negatives or factual-approval thresholds. No holdout-dependent rollback selection.

## Remaining Person 1/compiler and release work

The unified plan describes a stricter compiler than the original Track A implementation currently provides. Before claiming full submission readiness, address at least these known gaps: short SHA-1 source identities instead of full SHA-256; generated metadata without field-level source anchors; repeated-header/boilerplate recovery and full source searchability; deletion of extracted source originals after indexing; incomplete OCR being allowed to finish with warnings; mandatory all-page LLM card generation and its ingestion cost; and reader-safe retention beyond the existing limited old-generation cleanup. Metadata routing cannot assume these provenance upgrades already exist.

The existing shared LLM client/ingestion pricing and tracing behavior also need the unified audit's unknown-usage, verified-price and visible-export guarantees. Query processing uses its own stricter client; that does not repair ingestion accounting automatically. Pin exact model artifacts/revisions, measure complete cold ingestion on the actual organizer server, confirm event-window eligibility, run live OpenCode/dev evaluation, freeze once, inspect holdout once, export all required query traces and prepare the max 2–3-page write-up. No hidden data access or training is enabled by this track.

## Integration changes by Person 1 (2026-10-24)
Measured with `KB_LLM_MODE=dryrun` on 11 training questions; all tests pass.
- **Relevance order.** `candidate_pages` keeps pools in BM25+dense relevance order (it used to sort them by page number), and `survey_pages` reads the best batch of every document first. Before, the budget ran out on the first pages of the first document.
- **Budgets** (`kb/query/settings.py`, `runtime.py`):
  - `max_input_tokens` 200k → 480k bytes, with stage shares plan 0.1 / survey 0.3 / verify 0.72.
  - Writer context 16 KB → 64 KB (analytical), capped at half of what the budget has left.
  - `answer_output_tokens` 6000 → 8000.
  - Result: returned chunks rose from 293 to 1,019 against 897 gold (gold median is 81 chunks per question). Estimated cost ≈ $0.04 per query.
- **Deadline.** The survey stops at 35 % of the query deadline and verification at 65 %. The answer stages are never cut.
- **Parallel calls.** `QueryRuntime.call_many` reserves budget in order, then runs the survey and verify batches concurrently, each with its own client. `call()` is now `call_many` with a single payload.
- **Merged with your span-ID verifier (`bcef5b7`).** The first verification batch runs alone as a canary. Once it passes the schema check, the rest go out as one concurrent round. The factual fast path stays sequential. The split retry and stop-after-failure still apply; results already paid for are kept. Earlier stages now leave 2 model calls for the answer and claim check. Your DeepSeek 4,096-token floor, usage reset and raw-response artifacts are kept.
- **Local `.env`:** with `LLM_MODEL=deepseek-…` the 4,096-token floor limits verification to 5 batches. Use `qwen3.8-flash` as in `.env.example`.
- **Answer text.** No more "Coverage limitations: …" appendix in the answer (the judge scores every sentence as a claim). They remain in `coverage` and the trace.
- **No more 504 on budget stops.** Verification that runs out of budget with nothing kept now returns `no_answer` (HTTP 200) with a budget-specific answer text. A planner budget stop falls back to the query itself.
- **Claim check.** `answer_verify` now gets only the evidence the claims cite.
- **Cross-encoder speed.** `kb/embed.py` batches pairs of similar length: 23 → 74 pairs/s, identical scores.
