# Smart Knowledge Base for Agents: write-up

**Team:** two people, twelve hours. **API:** exactly `POST /index` and `POST /query` (PS §11.3).
**Repository:** _⟨link⟩_ · **Server:** _⟨URL⟩_ · **Langfuse export:** _⟨link⟩_

Fields marked _⟨…⟩_ are filled after the real-key evaluation run. Every number below that isn't marked is measured.

## 1. The problem we designed for
One-shot top-k similarity fails in three ways the brief names: an answer spread over 30+ pages (k is too small), near-duplicate documents (the FY2025 report retrieved for an FY2026 question), and chunks that look similar without containing the fact. Gold answers in the training set cite a **median of 81 chunks** (maximum 352) and run to about 5,000 characters. So retrieval has to be wide and the answer has to be grounded claim by claim, not cut from a top-5 prompt.

## 2. Architecture: route → survey → triage → verify → write
**Ingestion (`POST /index`, runs on CPU, ≈ $0.05 of LLM per index):**
1. **Safe unzip:** path traversal, symlinks and encrypted entries are rejected, and macOS junk and non-PDFs are skipped.
2. **Page-accurate parsing:** pymupdf4llm Markdown per physical page, with tables kept as Markdown. RapidOCR runs only on image pages with under 50 characters of text: 110 of the 6,970 training pages.
3. **Natural elements:** paragraphs, tables and list items, each tagged with its section path; text repeated across pages is flagged as boilerplate. Training corpus: 54,728 elements.
4. **Automatic metadata** (no hand labels):
   - one LLM **document card** per file: title, type, issuer, period, jurisdiction, topics, summary;
   - regex **identifiers** (FR Doc, RIN, ASU, CIN, arXiv, DOI);
   - **sibling groups** linking the same issuer across years;
   - an extractive **page card** for every page, built at $0.
5. **Storage:**
   - SQLite FTS5 (BM25) over pages and elements;
   - bge-small vectors over page cards;
   - each re-index builds a new *generation* and promotes it atomically, so a failed index never replaces a working one.

**Query (`POST /query`, ten traced steps):**

| # | Step | What it does |
|---|---|---|
| 1 | query_planning | The LLM turns the question into *obligations* (entity, period, scope, keywords) and routes documents from the document-card catalogue. |
| 2 | routing_guard | Checks identity and reporting period, so a near-duplicate year is excluded rather than silently substituted. |
| 3 | candidate_pages | Per document, BM25 + dense search fused with RRF, plus a lexical net per obligation. Pages are relevance-ordered and shared fairly across documents. |
| 4 | page_survey | Local by default: lexical matches per obligation plus the top-ranked pages per document. An LLM survey of page cards, most relevant first, is available with `KB_PAGE_SELECTION=llm`. |
| 5 | element_retrieval | All elements of the chosen pages, plus hybrid element hits per obligation. |
| 6 | element_triage | The cross-encoder (MiniLM) orders candidates, round-robin per obligation. Scores only *order* the work; they never prove anything. |
| 7 | element_verification | The LLM checks exact source fragments. A kept item needs a quote that is a verbatim substring of the fragment. |
| 8 | answer_generation | Coverage-weighted evidence selection, then structured claims, each carrying exact supporting quotes. |
| 9 | answer_verification | The LLM checks each claim against its quotes, and deterministic arithmetic checks any calculation. Unsupported claims are removed. |
| 10 | citation_render | Deterministic `[file.pdf pN]` citations. The returned chunks are exactly the evidence the writer saw. |

**Why this goes beyond RAG:**
- Retrieval is an **obligation-driven, budgeted search** over pages, not a single top-k.
- **Evidence is verified before writing.** The answer is a list of **checked claims** with page-exact provenance.
- **Document identity and period are guarded**, which addresses the near-duplicate failure mode.

## 3. Cost and latency controls
- **Per-query budget.** Input is capped at 480 KB of prompts (≈ 120k tokens). Each stage stops at a cumulative share of it: plan 10 %, survey 30 %, verify 72 %. The writer then gets whatever remains, so a broad question can never starve the answer.
- **Time shares.** The survey stops at 35 % of the deadline and verification at 65 %. The answer steps are never cut off.
- **Spend controls.** A hard spend cap (`KB_BUDGET_USD`) with a per-call ledger, plus a response cache, so a repeated prompt costs $0.
- **Parallel model calls.** After one canary batch passes the schema check, the remaining verification batches run as one concurrent round, with the budget reserved in order first. A 14-batch verification is therefore 2 model round-trips instead of 14.
- **Dry-run mode** runs the full pipeline at $0 with token estimates. All tuning before the key was done this way.
- **Graceful degradation.** A budget stop returns HTTP 200 with the limitation stated, never a timeout. A provider failure returns 503 and is never reported as "not in the documents".

## 4. Measured results
| Quantity | Value |
|---|---|
| Ingestion, 35 PDFs / 6,970 pages, 16-thread PC | **18.1 min** (parse 14.0, embeddings 4.0). Declared estimate on the server: _⟨measured × 1.5⟩_ |
| Ingestion, 2 PDFs / 238 pages | 49 s |
| Query prompt volume (dry run, 6 training questions, qwen3.8-flash) | ≈ 170 KB ≈ 45k input tokens + ≈ 10k output → ≈ **$0.01 per query** (estimate) |
| Chunks returned vs gold (dry run) | 459 vs 530 on 6 questions; 293 vs 897 on 11 questions before the budget fix |
| Query latency | _⟨real p50 / p95⟩_ (dry run, CPU only: 4–9 s, down from 12–27 s) |
| Answer precision / recall | _⟨…⟩_ / _⟨…⟩_ on _⟨n⟩_ held-out training questions, official evaluator unmodified |
| Context precision / recall | _⟨…⟩_ / _⟨…⟩_ |
| Hidden-run cost (all queries) | _⟨Langfuse total⟩_ |

## 5. Engineering decisions
- **Natural elements, not fixed windows.** Tables stay whole and page numbers stay exact, so the citations and chunk pages are correct by construction.
- **Extractive page cards instead of LLM page cards.** This saves about $1.75 per index. An LLM variant exists behind `KB_PAGE_CARDS=llm` for an A/B test.
- **Limitations go in the response's `coverage` field and the trace, never in the answer text.** The evaluator scores every answer sentence as a claim.
- **Cross-platform.** Explicit UTF-8 everywhere and LF line endings (Windows and macOS team), enforced by a test.

## 6. Limitations (honest)
- _⟨Fill from the evaluation: which question types fall short of 0.95, and why.⟩_
- Our elements (median ≈ 300 characters) are smaller than the gold chunks (median 427), so the chunk count is not a measure of coverage.
- No model training or fine-tuning (out of scope per the brief). All models are pretrained and run inference only.
