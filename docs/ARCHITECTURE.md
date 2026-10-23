# Smart Knowledge Base for Agents — FINAL Architecture Spec

Version: final-1.0 · Date: 2026-10-23 · Companion: `docs/PLAN.md` (module-by-module build instructions)

This is the authoritative **spec**: what we build and why. `docs/PLAN.md` is the authoritative **how**: files, signatures, prompts, tests. When they disagree, this file wins on behaviour and PLAN.md wins on names and signatures.

This version merges two independent designs:
- Our "Route → Survey → Verify → Write" design, with a CPU-first retrieval funnel.
- The "Evidence Coverage Retrieval" (ECR) handoff package (`knowledge-base-plan 2.zip`).

Section 9 lists what was adopted from ECR and what was deliberately left out.

---

## 1. Problem

Build a service with two endpoints:
- `POST /index` takes a zip of unlabelled documents (PDFs in random order) and a `collection_name`.
- `POST /query` takes `collection_name` and `query`. It returns a grounded answer, the chunks used (each with document name and physical page), and a step-by-step `trace`.

Scoring:
- Answer Precision, Answer Recall, Context Precision and Context Recall on a hidden corpus and hidden questions (target ≥ 0.95 each).
- Cost and latency, observed via Langfuse.

Not acceptable as the core: plain embed → top-k → rerank, hybrid+rerank alone, HyDE, multi-query, CRAG, parent-document, vanilla GraphRAG, agentic re-query loops.

Source: `Problem Statement 1/Problem Statement 1/Hackathon_Problem_Statement_Final.docx`.

## 2. Verified data facts (all measured on 2026-10-23)

| Fact | Value | Design consequence |
|---|---|---|
| Questions | 100: A×36 corporate annual-report credit reviews, B×32 Basel/US capital rules, C×32 CECL/ECL accounting + quant models | Generic pipeline, no domain code. Prefixes are not runtime signals. |
| Corpus | 35 PDFs, 6,970 pages, ~198 MB; largest `BaselFramework.pdf` 1,982 pages | Query work is bounded per document; ingestion is page-parallel. |
| Scanned PDF | `SAMA_EN_3575_VER1.pdf`: 92/92 pages have no text layer (cover reads *Guidelines on Management of Problem Loans*, SAMA, January 2020) | OCR is mandatory. |
| Outlines | 15/35 PDFs have no bookmarks | Section paths come from headings when no outline exists. |
| Gold evidence format | `benchmark_chunks_w_metadata` = `{file: [{section_name, content, metadata:{page_numbers:[int], document}}]}` | Gold units are paragraph/table elements on a single page. |
| Gold passages per question | min 0 · median 81 · mean 87.8 · max 352; distinct pages median 39, max 125 | **Context recall needs dozens to hundreds of relevant chunks.** Top-k=20 cannot reach 0.95. |
| Gold passage length | p25 196 · median 427 · p75 879 chars (big tables up to 14k) | Our chunk = one natural paragraph or table. |
| Page numbering | Gold = 1-based physical page index (verified on 4 samples) | `page_no = index + 1`. |
| Gold answers | median ~5,000 chars (~754 words), markdown with headings, tables, citations | Answers must be comprehensive and contain nothing unsupported. |
| Unanswerable | `B32`: 0 gold chunks, gold text "No information was retrieved for this question." | Abstain path. |
| Partially answerable | `A36` asks for Aldar's 2025 report; corpus has only `aldar_annual_report_2024.pdf`. Gold says the 2025 figure is not in the excerpts and reports 2024 as context only | "partial" status: never relabel a 2024 document as 2025. |
| Renamed files | `SAMA_EN_3575_VER1.pdf` = gold's "Guidelines on Management of Problem Loans.pdf"; `fact-sheet-SUMMARY.pdf` ≈ gold's `fact-sheet-20260319.pdf` | Identity comes from content; cite the file name **as supplied in the zip**. |
| **Missing source** | Gold cites `2026-05960.pdf` in **25 questions (603 of their 2,200 gold passages)**. It is NOT in the corpus: `91fr14952.pdf` is FR Doc. 2026–05959 and `91fr14908.pdf` is FR Doc. 2026–05961 (verified in text) | Hard recall ceiling on those questions. Never alias documents by topic. Report scores with and without these 25. |
| Near-duplicate families | Metal Coatings FY2025/FY2026; three 2026 US capital proposals + fact sheet + board memos; Basel (Framework, Endgame, Market Risk, CVA); CECL (ASU 2016-13, ASC 326 update, FDIC FAQ, FDIC statement, OCC handbook, Implementation Handbook) | Failure Mode 1 is real: routing must use issuer, document type, period and identifiers explicitly. |
| Question/document graph | Shared documents connect 98 of 100 questions into one component | No document-disjoint split exists. Use a stratified query split and say so. |

### 2.1 What the evaluator computes (`Train/Train/Evaluation/Evaluation.ipynb`, never modified)

- **Judge setup:** `deepseek-v4.1-flash` at `https://opencode.ai/inference/openai/v1/chat/completions`, JSON mode, temperature 0, 60 s timeout, 3 retries.
- **Answer P/R:** both answers are split into atomic points.
  - Precision = (agent points − points flagged extra) / agent points. True facts absent from the gold answer can count as "extra".
  - Recall = matched gold points / gold points.
- **Context P/R:** one judge call sees the query and the *text* of every returned chunk, and marks each relevant or not.
  - Precision = relevant / returned.
  - Recall = relevant / number of flattened gold passages. It is **not capped at 1** and does no matching to gold.
  - A question with 0 gold passages always gets recall 0.
- **Consequences:**
  1. Each returned chunk's text carries a provenance header, so the judge can see why it is relevant.
  2. Chunk granularity is fixed at ingestion (natural elements). **Never split chunks at query time to inflate recall.**
  3. Never pad results with unverified chunks: every irrelevant chunk lowers precision.

## 3. Research basis (searched 2026-10-23)

| Source | Finding | Adopted as |
|---|---|---|
| HiREC, ACL Findings 2025 ([arXiv 2505.20368](https://arxiv.org/abs/2505.20368)) | Near-duplicate filings confuse flat retrieval. Document-first retrieval using cover-page summaries (company, type, period), then passages, improves accuracy by 13% | Doc cards + routing before passage search |
| Semantic File Routing / HDRR ([arXiv 2603.26815](https://arxiv.org/html/2603.26815)) | Metadata routing then scoped chunk retrieval: avg 7.54 vs 6.02, failures 6.4% vs 22.5%, 5–15K tokens/query, fallback when routing fails | Routing guard + lexical fallback + escape search |
| MimirRAG ([arXiv 2605.25030](https://arxiv.org/html/2605.25030v1)) | Front-matter metadata narrows candidates; table-aware chunking helps | Doc card from opening pages + outline + identifiers |
| Tree reasoning vs vector ([arXiv 2604.14222](https://arxiv.org/pdf/2604.14222)); PageIndex (vendor claim, unverified) | On FinanceBench, structural LLM navigation scored 0.938 vs 0.821 for vector RAG | LLM page survey over the structural index |
| READ, Beyond Top-K ([arXiv 2608.06305](https://arxiv.org/pdf/2608.06305)) | Units and fiscal year sit in headers far from the figure; dense top-k 15.7% vs 58.8%; BM25 ≈ agentic | Lexical first-class; table captions carried; whole-page reading |
| Contextual Retrieval ([Anthropic](https://anthropic.com/news/contextual-retrieval)) | Context prefixes cut retrieval failures by 35–67% | Deterministic provenance prefixes (doc/period/section/page) |
| Ingest-time compilation ([arXiv 2608.20845](https://arxiv.org/pdf/2608.20845)) | Compile once at ingest: 85.2% vs 72.5% accuracy at about 7× fewer tokens | Page cards at ingest |
| Listwise selection ([arXiv 2604.15621](https://arxiv.org/html/2604.15621), [2510.11358](https://arxiv.org/html/2510.11358)); Provence ([2501.16214](https://arxiv.org/html/2501.16214v1)) | Listwise selection with a "none" option beats pointwise; variable-size pruning | Listwise LLM verification that may keep 0 |
| Retrieval gap in financial QA ([PMLR v318](https://proceedings.mlr.press/v318/kobeissi26a.html)) | Separate document / page / chunk discovery and use oracle diagnostics | Page stage + per-stage diagnostics in evaluation |
| Evidence-unit fairness ([arXiv 2608.00183](https://arxiv.org/abs/2608.00183)) | Dense encoders silently see truncated units; adaptive fusion gave no reliable gain | Token-budgeted embedding inputs; fixed RRF fusion |
| BM25 → CRAG on text+table ([arXiv 2604.01733](https://arxiv.org/abs/2604.01733)) | Hybrid+rerank is a strong baseline | Hybrid + CPU cross-encoder as a *supporting* layer and an eval-only baseline control |
| NVIDIA chunking study; element chunking ([arXiv 2402.05131](https://arxiv.org/abs/2402.05131v3)) | Page-level and element-level chunking beat fixed size on FinanceBench | Page = unit of selection; element = unit of evidence |
| PDF parsing study ([arXiv 2604.12047](https://arxiv.org/pdf/2604.12047)); 2026 parser comparisons | PyMuPDF is fast and competitive; Docling has better tables but takes ~0.76 s/page | PyMuPDF + pymupdf4llm 1.28; Docling rejected for time |
| LongCite ([arXiv 2409.02897](https://arxiv.org/pdf/2409.02897)); ECR | Inline citations reduce hallucination; never trust model-written page strings | The model cites evidence IDs `[E12]`; the renderer maps IDs to file/page |
| Long context vs RAG token tax ([arXiv 2606.20898](https://arxiv.org/pdf/2606.20898)) | Long context ≈ $0.118/run vs ≈ $0.005 for RAG | Never dump whole documents |
| Rejected | ColPali (GPU, ~2k vectors/page); RAPTOR clustering; HippoRAG/GraphRAG; proposition/claim compilation at ingest; recursive readers; learned fusion or page scorers | Too costly or unproven for 12 h; ECR also marks them optional experiments |

## 4. Architecture: "Route → Survey → Triage → Verify → Write"

Core principle: **recall comes from structured, exhaustive coverage of a small, correctly routed pool. Precision comes from verifying every returned element.**
- CPU layers (lexical, dense, cross-encoder) find candidates and settle the clear cases cheaply.
- LLM calls are spent on routing, page surveys and the uncertain middle.

It is a fixed DAG with a bounded number of LLM calls: no re-query loop, and no top-k cut of the final evidence.

```
INGEST (per collection, one immutable "generation")
  zip ─ safe extract ─ page jobs (50 pages each, process pool):
        pymupdf4llm markdown per page │ OCR (RapidOCR) for image-only pages
  ─ segment → ELEMENTS (paragraph | table; heading path; table caption/unit line)
  ─ CPU flags: boilerplate (repeated header/footer text) excluded from search
  ─ CPU identifiers: FR Doc / docket / RIN / ASU / CIN / arXiv / DOI regex
  ─ LLM DOC CARD per document (title, type, issuer, entities, period, jurisdiction, topics, summary)
  ─ LLM PAGE CARDS (4 pages per call) → doc-card topics augmented with frequent page topics
  ─ sibling groups (same normalised issuer, different period)
  ─ indexes: SQLite FTS5 (pages, elements) + bge-small vectors on page cards (element vectors optional, off by default)
  ─ validate → atomic promotion of the generation

QUERY (bounded; parallel where possible)
  1 query_planning      LLM: catalogue of doc cards + CPU hints (years, entity matches) → intent, aspects, docs
  2 routing_guard       CPU: drop unknown ids; add named-entity docs (sibling-aware); lexical fallback
  3 candidate_pages     CPU: all pages of routed docs within budget; else BM25+dense RRF; + lexical net
  4 page_survey         LLM: page cards in batches of 60 → pages per aspect (high/medium); lexical pages added
  5 element_retrieval   CPU: elements of surveyed pages ∪ element-level hybrid hits (per aspect) ∪ escape hits
  6 element_triage      CPU: cross-encoder (MiniLM-L6 ONNX) score per element vs its aspect;
                        < τ_low → drop · ≥ τ_high → keep · between → LLM (τs calibrated offline; default: everything to LLM)
  7 element_verification LLM: listwise keep/drop of the middle band in char-budgeted batches
  8 answer_generation   LLM: answer from kept elements only, citing [E#] ids; status answered|partial|not_answerable
  9 citation_render     CPU: [E#] → [file.pdf pN]; invalid ids removed and reported
```

### 4.1 Why this handles both failure modes
- **Failure Mode 1 (near-duplicates):**
  - Routing reasons over cards that state issuer, document type, period and identifiers, and it is told which documents are siblings.
  - "This year's report" resolves to the latest sibling. A comparison selects both.
  - The guard never adds a second sibling by itself.
  - Similarity never has to tell FY2025 from FY2026.
- **Failure Mode 2 (chunk-size dilemma):**
  - The survey reads every page card of the routed documents (capped only for huge documents), so evidence spread over 30–125 pages is found by construction.
  - Triage and verification then keep only relevant elements, so precision does not fall as coverage grows.
  - Cost scales with the routed pool, not with a blindly chosen k.

### 4.2 Intents and budgets (tuned only on the dev split)

| intent | meaning | survey pages/doc | survey cards/query | verify pages | LLM-verify chars | max evidence |
|---|---|---|---|---|---|---|
| `factoid` | one or a few facts | 300 | 600 | 15 | 60,000 | 40 |
| `analytical` | explain / compare / assess | 1,000 | 2,000 | 80 | 240,000 | 250 |
| `exhaustive` | "every…", red-flag reviews, full reviews | 2,000 | 3,000 | 200 | 480,000 | 450 |

- When a document exceeds its per-doc cap, or the query exceeds its card cap, the pool is bounded by BM25 + dense RRF, and lexical-net pages are always kept.
- Element triage looks at most at `max_ce_pairs` = 800 pairs per query (measured ~105 pairs/s on CPU, so ≈ 8 s).

### 4.3 Models and expected cost
- **LLM:** one OpenAI-compatible OpenCode endpoint. Default `deepseek-v4.1-flash` (the judge model). Price, listed by third parties and to be confirmed on the day: $0.30/M input, $1.20/M output.
  - Unknown prices are recorded as `null`, never 0.
  - `ANSWER_MODEL` can point to a stronger model if the key offers one.
- **CPU models via fastembed 0.9 (ONNX, no torch):** embeddings `BAAI/bge-small-en-v1.5` (384-d, 512-token window); cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2`. All embedding inputs are budgeted to ≤ 1,500 characters including the prefix.
  - Measured on the dev laptop: ≈ 45 texts/s embedding and ≈ 105 pairs/s cross-encoder.
  - So dense vectors cover page cards only; elements are found through FTS5, the survey and the lexical net.
- **Parsing/OCR:** pymupdf4llm 1.28.2 with pymupdf-layout. Measured ≈ 0.6 s/page native and ≈ 5 s/page OCR, with its own RapidOCR and header/footer removal; page-parallel processes. Its markdown style matches the gold passages.
- **Per-query estimate (unverified until measured):** about 5–25 LLM calls, about $0.01–0.06, about 20–60 s.
- **Ingestion estimate for 7k pages (unverified until measured):**
  - Parse and OCR: 6,970 × 0.6 s + 92 × 5 s ≈ 78 CPU-min, so ~10–15 min on 7 worker processes.
  - Page cards: ~1,750 calls, ~10–20 min, depending on the provider's rate limit.
  - Embeddings: ~7k page cards, ~3 min.
  - Cost: $3–6.
  - The stated ingestion time is taken from the measured full training ingest × 1.5.

## 5. External API contract

### 5.1 `POST /index`
- **Request:** `multipart/form-data` with `file` (zip) and `collection_name` (`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`). Blocking: it returns only after the new generation is validated and promoted.
- **Validation:**
  - Reject absolute paths, `..`, NUL bytes, symlinks, encrypted members, and a total uncompressed size above `max_archive_bytes` (default 8 GB).
  - Index every `.pdf` (case-insensitive) at any depth. Skip `__MACOSX/`, dot-files and non-PDFs, listing them in `warnings`.
  - Byte-identical duplicates are indexed once. Distinct files that share a basename stay distinct: their display name is the relative path inside the zip.
- **200:** `{"status":"ready","collection_name","generation_id","documents","pages","elements","ocr_pages","ocr_unavailable_pages","warnings":[...],"llm_usage":{...},"ingestion_seconds"}`.
- **Errors (shape §5.3):**

| HTTP | code | when |
|---|---|---|
| 422 | `INVALID_COLLECTION_NAME` | name fails the pattern |
| 400 | `INVALID_ARCHIVE` | bad zip, encrypted, unsafe members |
| 400 | `NO_DOCUMENTS` | no PDFs in the zip |
| 413 | `ARCHIVE_TOO_LARGE` | uncompressed size over the limit |
| 409 | `COLLECTION_BUSY` | indexing of the same name already in progress |
| 500 | `INDEXING_FAILED` | internal failure (the previous generation stays active) |

### 5.2 `POST /query`
- **Request:** JSON `{"collection_name": str, "query": str}`. Query length is 1–32,000 characters.
- **200:**
```json
{
  "request_id": "req_…",
  "collection_name": "train",
  "generation_id": "gen_…",
  "status": "answered | partial | not_answerable",
  "answer": "markdown with [file.pdf p12] citations",
  "chunks": [
    {"chunk_id": "d1a2b3c4d5:p0012:e003", "evidence_id": "E3",
     "content": "[file.pdf p.12 · Notes > Borrowings]\n<element text>",
     "text": "<same as content>", "raw_text": "<element text only>",
     "document": "file.pdf", "page": 12, "page_numbers": [12], "section": "Notes > Borrowings",
     "kind": "text | table", "aspects": ["a1"], "selected_by": "llm | auto_keep", "note": "why kept"}
  ],
  "coverage": {"aspects": [{"aspect_id": "a1", "text": "...", "status": "supported | unsupported", "evidence_ids": ["E3"]}]},
  "trace": [{"step_name": "...", "description": "...", "input": {}, "output": {}}],
  "metrics": {"latency_ms": 0, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "cost_status": "priced | unknown_price"},
  "trace_id": "langfuse id or null"
}
```
- **Chunks:**
  - `content` and `text` are identical (header + element text), so any organiser adapter that reads either field gets the same judge-visible text.
  - `chunks` contains exactly the evidence the answer model saw (no hidden extra context, no unseen padding).
- **Trace:** every element has exactly the four keys. Step names, in order: `query_planning`, `routing_guard`, `candidate_pages`, `page_survey`, `element_retrieval`, `element_triage`, `element_verification`, `answer_generation`, `citation_render`. All nine are always present; skipped steps have `output: {"skipped": "<reason>"}`.
- **Errors:**

| HTTP | code | when |
|---|---|---|
| 422 | `INVALID_COLLECTION_NAME` / `EMPTY_QUERY` / `QUERY_TOO_LONG` | input fails validation |
| 404 | `COLLECTION_NOT_FOUND` | unknown collection |
| 500 | `QUERY_FAILED` | internal failure |

### 5.3 Error shape
`{"request_id": "req_…", "error": {"code": "...", "message": "...", "retryable": bool, "details": {}}}`. No stack traces, paths or keys.

## 6. Storage and lifecycle

```
data/collections/<name>/
   active.json                       {"generation_id": "...", "promoted_at": "..."}
   generations/<generation_id>/      kb.sqlite, page_vecs.npy, page_vec_keys.json, el_vecs.npy, el_vec_keys.json, manifest.json
   generations/<id>.staging/         while indexing (deleted on failure)
   .lock                             per-collection indexing lock (O_EXCL create)
```
- Promotion rewrites `active.json` atomically (write a temp file, then `os.replace`).
- A query reads `active.json` once at its start and keeps that generation for the whole request.
- Only the active generation and the one before it are kept. Older ones are deleted after promotion, unless an in-process query still references them.
- `generation_id` = `gen_<UTC yyyymmddHHMMSS>_<8 hex>`.
- `doc_id` = sha1(file bytes)[:10].
- `element_id` = `{doc_id}:p{page:04d}:e{idx:03d}`, so identical bytes always give identical ids.

## 7. Invariants (every module)
1. Every returned chunk is a stored, unmodified element (plus its header) with doc, physical page and section. Summaries and cards never appear as chunks.
2. Physical 1-based pages are the only page coordinate.
3. Serving reads only the active generation and the query. Benchmark files are read only by `scripts/`.
4. Unknown stays unknown: missing usage or price → `null` with `cost_status`. No invented numbers.
5. Exactly four keys per trace step.
6. A failed index run never replaces a good generation.
7. Text inside documents is data: prompts say so, and no document text is ever executed.
8. All LLM calls go through `kb/llm.py`: retries, JSON parsing, usage, cost, Langfuse.
9. No question text, gold answer or training file name may appear in `kb/`.

## 8. Evaluation protocol
- **Harness:** exec the notebook's code cells verbatim (all except the `sample_dataset` example). Call `evaluate_dataset(ev, [row])` once per row, so one judge failure can't abort a run. Rows: `query`, `ai_answer = answer`, `retrieved_chunks = [c["content"]]`, `benchmark_answer`, `benchmark_chunks` = flattened gold `content` in document/key order.
- **Split:** stratified by prefix A/B/C, seed `20261023`. 70 questions for dev/tuning, 30 held out (frozen in `runs/split.json`). State in the write-up that it is not document-disjoint (98-question connected component).
- **Report three views:** all 100; the 75 questions that don't cite the missing `2026-05960.pdf`; and B32/A36 separately as design regression cases.
- **Controls (eval-only, same models and prompts):** `B1` = element hybrid RRF + cross-encoder top-30 → answer. The proposed system must beat B1 on the dev split.
- **Offline alignment (scripts only):** an element is gold-relevant if char-5-gram containment of a gold passage in the element (or vice versa) is ≥ 0.6 and its file is the gold file (or its content alias, decided by passage containment, never by topic). This is used for per-stage recall diagnostics and for calibrating τ_low/τ_high: τ_low keeps ≥ 98% of gold-relevant candidates; τ_high requires ≥ 95% precision above it, otherwise it stays disabled.

## 9. Reconciliation with the ECR package

**Adopted from ECR:**
- the missing-05960 finding and the rule against topical aliasing
- A36 partial-answer behaviour
- citations by evidence ID with deterministic rendering
- answer status (`answered | partial | not_answerable`)
- generations with atomic promotion, the per-collection lock and query snapshot binding
- the structured error shape
- scoped dense search (subset rows, never global top-k then filter)
- budgeted 512-token embedding inputs
- boilerplate filtering that keeps the raw text recoverable
- deterministic identifiers in the identity metadata
- the global escape search
- the B1 baseline control
- the honest split disclosure, unknown-price → `null`, and the prompt-injection stance

**Deliberately not adopted for the 12-hour build:**
- the claim ledger with quote-offset verification and Decimal arithmetic DSL
- repair passes (they resemble the banned corrective/agentic loops)
- the 48-obligation coverage matrix (we cap at 8 aspects)
- Tesseract (not installable without system packages; RapidOCR is pip-only)
- the ECR concurrency default of 2 (ours is 8, measured and lowered on HTTP 429)
- the Qwen3 accuracy profile, page-scorer training and visual retrieval (stretch only)

**Disagreement resolved:** ECR proposes ~240-token target units. We keep natural paragraph/table elements, because gold granularity is paragraph/table (median 427 chars) and the count-based recall rewards matching that natural granularity without artificial splitting.

## 10. Known limits (state these in the write-up)
- **Missing source:** about 27% of the gold passages for 25 questions are unattainable (`2026-05960.pdf` absent).
- **Visuals:** VLM image descriptions in the gold (<1% of passages) are not reproduced.
- **Judge variance:** the LLM judge varies between runs; repeat a fixed 10-question subset 3× to estimate it.
- **Not blind:** the dev/held-out split shares documents.
