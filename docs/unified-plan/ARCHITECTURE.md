# Architecture specification — UFP 2.0

## 1. Objective and proposed contribution

Build a collection-grounded retrieval and answering service for previously unseen PDF collections. Optimize the official answer/context precision and recall metrics together with measured latency and complete inference cost. The four 0.95 values are competition targets, not achieved results or plausible guarantees from architecture alone.

The proposed contribution is a **source-grounded evidence coverage executor**. It combines automatically qualified document identities, a recoverable document skeleton, finite page/section discovery, explicit entity/period/aspect evidence obligations and a claim-to-source support map. Its measurable hypotheses are fewer wrong-document/period answers and better complementary evidence coverage at comparable budgets. Dense search, lexical search and reranking provide candidates; their composition is the baseline, not the claimed innovation.

The pipeline has no retrieval back-edge. It does not repeatedly ask an agent whether it is satisfied. All scans, model batches, source-reference expansions and optional answer repair have limits set before execution. The service reports when those limits prevent completion. This is deliberately more conservative than the former plan's corrective retrieval passes.

## 2. Source audit informing the design

The supplied corpus contains 35 PDFs, 6,970 physical pages and 198,226,390 bytes. One 1,982-page framework dominates page count. The 100 questions have 8,777 gold passages; the median is 81 passages and 39 distinct document-pages, with maxima 352 and 125. Gold chunks vary greatly in length. These are label statistics, not a mandated return count or a valid runtime prior for an individual query.

All 92 pages of `SAMA_EN_3575_VER1.pdf` lack native extracted text. A rendered cover and sample OCR identify the problem-loan guidelines. A further low-text screening count of 177 pages is not an OCR requirement: blank pages and diagrams need classification first. Some PDFs lack bookmarks; a visible TOC, layout headings and fallback page ranges must still produce a navigable skeleton.

The benchmark references a missing `2026-05960.pdf`. There are 603 reference passages under that name across 25 questions; their combined gold passage count is 2,200. This does not prove 603 unique facts are unavailable: other supplied sources may support some facts. Do not alias it to `91fr14952.pdf`, whose identifier is FR Doc. 2026-05959, or `91fr14908.pdf`, FR Doc. 2026-05961. Another fact-sheet filename is a strong content-alias candidate, not a fully verified passage mapping. Runtime indexing must infer identities from source documents without reading gold.

## 3. Runtime and deployment layout

Use Python 3.11 as the initial target, within the statement's Python 3.10+ requirement. Build on the organizer server and lock the environment after capability checks. Default components are FastAPI transport, SQLite/FTS5, PyMuPDF with a page-preserving extraction adapter, selective OCR, FastEmbed/ONNX pretrained embeddings and reranking, a local FAISS page index, an OpenCode-compatible client, and Langfuse. Record licenses for code and model artifacts independently.

Default candidate models are `BAAI/bge-small-en-v1.5` and FastEmbed's `Xenova/ms-marco-MiniLM-L-6-v2`. These are resource-conscious candidates, not measured winners. Pin exact model/tokenizer/ONNX hashes before release. The PyTorch/Sentence Transformers equivalent is a fallback profile with its own lock manifest and benchmark; do not switch silently. Validate embedding dimension and normalization and the reranker's actual tokenizer pair limit. A character count cannot enforce a token limit.

Use a single API worker initially, bounded CPU/OCR jobs and a single process-wide provider scheduler with initial concurrency two. If multiple API processes are introduced, enforce a shared provider cap and collection reader leases across processes. Start with a simple deployment whose concurrency and memory can be measured honestly.

Application structure is specified in PLAN.md. Storage is under `data/collections/<collection_key>/generations/<generation_id>/`; query artifacts are separate under `artifacts/runs/`. Every query binds one immutable generation. New ingestion becomes visible only through atomic activation after validation. Old generations remain available to in-flight readers; cleanup is an explicit maintenance operation after reader-safety checks.

## 4. Ingestion: source compiler

### 4.1 Validate, isolate and fingerprint

Accept a ZIP and a collection name. Validate name length and allowed characters; derive a safe storage key. Reject path traversal, absolute paths, symlinks, encrypted or unsupported entries, excessive expansion and duplicate normalized archive paths. A configured resource limit returns a clear failure rather than silently dropping documents. Preserve relative source paths to disambiguate equal basenames.

Hash original bytes with full SHA-256. Use content hashes, parser/model revisions and configuration hashes for artifact reuse. Do not use truncated 40-bit identifiers, global filename identity, or a lowercased text hash as evidence identity. The same bytes can reuse immutable parsing artifacts across collections, but authorization and returned source names remain collection-scoped.

### 4.2 Recover pages and original evidence

For each physical PDF page, extract native text, blocks, bounding boxes and tables. Keep raw page artifacts and original PDF bytes. Detect reading-order problems, corrupt encodings and scan-like pages from multiple signals, not one text-length test. Use OCR only where needed; preserve the selected extraction and native/OCR alternatives with quality flags. OCR failure on a content-bearing page fails required ingestion by default. A genuinely blank page is a valid classified page.

Run a parser pilot across native prose, two-column pages, tables, scans and equations. Evaluate PyMuPDF4LLM's installed output shape before choosing it as the adapter; its page dictionaries and OCR defaults vary by version. Pass OCR behavior explicitly. Docling is an optional parser comparator for difficult pages, not a rejected technology based on another machine's timing. Do not blanket OCR clean text or assume Markdown export preserves every numeric cell.

### 4.3 Build the skeleton

Use PDF outline/bookmarks, visible TOC entries, numbered headings, typography, layout and page continuity. Validate that inferred section starts exist and ranges are ordered. Store parent/child sections and page membership. If no trustworthy hierarchy exists, use document → page with detected local headings, and mark confidence. Printed page labels supplement physical pages; they never replace the physical 1-based citation coordinate.

Preserve table headers, captions, units, currency, reporting periods, row/column labels and notes as explicit source anchors. A repeated short line can be a critical currency label. Boilerplate detection marks positional repetitions for scoring; it must not irreversibly delete source content or searchability. Reference edges must come from explicit source references and carry their origin, target candidates and confidence. Cap predeclared reference expansion depth at one in the default profile.

### 4.4 Canonical elements and search windows

Canonical evidence is a natural paragraph, list item, table block or source-anchored table fragment on one physical page. Preserve exact extracted text and source coordinates. Split very long tables at row boundaries, repeat headers only as separately identified source context, and record whether the fragment is complete. Never split decimals, signs, sentences or table rows merely to reach a chunk count.

Search windows are separate representations. Use the actual embedding tokenizer to window long elements/pages, accounting for identity prefix and special tokens. Suggested target window is 384 tokens with 64-token overlap, below the model's verified limit. A window maps to its parent source span; it does not redefine canonical evidence. Reranker pair windows include query and special tokens. Their logits are relevance scores, not probabilities or entailment.

### 4.5 Qualified metadata and navigation cards

Document cards include source-derived title, legal entity, issuer, identifier, document kind, jurisdiction, publication date, effective date, reporting period, accounting/regulatory scope and status. Every non-null substantive field carries a source anchor or explicit inference/confidence. Unknown stays null. A histogram of years mentioned in a report is not its reporting year. Keep “Holdings,” “Group,” jurisdiction and legal suffix distinctions where identity requires them. An issuer publishing two proposals in one year does not make them siblings or versions.

Resolve versions using verified identifiers, document kind, entity/scope and comparable dates. “Latest” means the latest comparable available document relevant to the request, not the highest year in any file. Explicit multi-year comparisons retain all requested years. An unavailable requested year is reported, without substituting last year's figures as the requested answer.

Page cards are cheap source-derived navigation records: section path, headings, caption/header vocabulary, deterministic excerpts spanning page regions, lexical terms, entity/period anchors and quality flags. They may omit relevant facts. Optional LLM enrichment is limited to ambiguous document identities or selected low-quality cards, cached by source/config/model hash and governed by an ingestion budget. An LLM call for every four pages would mean roughly 1,743 page batches before retries on this corpus; the default does not require that expense. Summaries are never evidence of complete coverage or collection-wide absence.

### 4.6 Materialize and activate

Build document/page/element SQLite tables, full-source FTS5 indexes, source-derived card search, and page-window vectors. Store normalized vector arrays plus stable window-to-page mappings. FAISS serves unrestricted exact normalized inner-product search. Filtered searches score the allowed subset exactly from the same vectors, avoiding “global top-k then filter” recall loss. Element vectors are optional and off by default; full element FTS remains available.

Validate page counts, source hashes, foreign keys, vector dimensions/counts, FTS synchronization, model manifests, quality failures and deterministic sample citations. Write a durable manifest marked complete, fsync, atomically replace `active.json`, then return indexing success. A failed build leaves the previous active generation untouched. An optional enrichment failure may degrade navigation but cannot silently lose required extraction or core indexes.

## 5. Query: fixed ten-stage execution

Every successful query produces these ten trace steps in order, including explicit skipped outputs. Internal finite batches remain children of their stage, not additional retrieval cycles. Inputs are user query, bound generation, configuration hash and a request-wide budget ledger.

### 5.1 `query_planning`

Parse the query into intent, explicit entities, periods, jurisdiction, document identifiers, negations, comparison axes, requested factual aspects and exhaustiveness. Build obligations as `(aspect, entity, period, scope)` slots, preserving original query spans. Up to eight aspect groups are a prompt convenience; groups do not discard entity/period slots. Default maximum 64 slots, with an explicit overflow record if exceeded. No hypothetical factual answer or gold-derived query expansion.

The planner emits generic lexical phrases per obligation from the query and source vocabulary. It never treats the question's allegation as a proven fact. Invalid structured output permits one schema repair within the request budget, then a deterministic query-derived fallback with uncertainty.

### 5.2 `routing_guard`

Match verified catalog metadata and explicit source identifiers. Preserve all explicit entities/periods and relevant counterpart documents for comparisons. Reject confirmed mismatches; soft uncertain metadata narrows rankings but cannot alone eliminate all candidates. Default document shortlist sizes 6 precise/12 broad are soft: explicit requirements bypass them. An empty or uncertain route activates a predeclared global lexical/vector escape branch in the next stage, not an immediate no-answer.

Do not let an LLM `answerable=false` based on cards terminate the request. Distinguish unavailable requested identity/year from unsupported factual content and unresolved routing. Record alternatives and reasons.

### 5.3 `candidate_pages`

Run source-text lexical search, page-window dense search, section/heading matching and explicit source-reference expansion within the eligible scope. Preserve numerical/identifier exact matches and negation in semantic inputs. Escape/quote user terms for FTS; never execute user-supplied FTS operators directly.

Fuse ranks with fixed RRF `sum(1/(60+rank))` over distinct search lists, then take the best window score per page per list before page fusion. Use obligation quotas so a dominant entity cannot consume every candidate. Precise/broad candidate defaults are 60/200 pages plus a bounded global escape of 20. These are internal budgets, not the number of pages the corpus can require.

For an exhaustive request over manageable routed documents, enumerate all source-derived page cards in that finite scope alongside search candidates. If a 1,982-page scope exceeds the survey budget, prioritize relevant sections but mark the unsurveyed scope explicitly. Broad scanning must not be described as guaranteed complete merely because all summaries were read.

### 5.4 `page_survey`

Batch page cards and section context to the LLM for possible relevance by obligation. Source candidates survive independently when lexical/identifier signals are strong, even if a lossy card was rejected. For ambiguous table pages, read bounded source excerpts instead of trusting summaries. Maintain a coverage ledger containing pages available, cards surveyed, raw source inspected, candidates omitted and reasons. Page-level relevance is a navigation decision, not claim support.

The finite survey budget is selected before execution. No re-query until satisfaction. Never equate “no selected card” with “the corpus does not contain the fact.”

### 5.5 `element_retrieval`

Read canonical elements from selected pages, scoped FTS matches and permitted structural neighbors/reference targets. Structural expansion carries table headers and sentence context but is only supporting behavior, not the architecture's contribution. Keep retrieval origin, obligation links, source identifiers and section paths for every element. Deduplicate by source anchor/window overlap within the same qualified scope; do not merge contradictory cross-period passages because their text is similar.

### 5.6 `element_triage`

Use lexical/metadata features and the CPU cross-encoder to order bounded verification work, default at most 400 pairs. Tokenize every pair; long elements receive multiple mapped windows. Unscored elements have an explicit pending status, not an accidental highest score because a Python value is null. Do not auto-keep high logits as verified evidence or auto-drop low logits by default. Threshold-based prefiltering requires development-only calibration and measured recall effects.

Allocate verification candidates across obligation slots and source scopes. Keep indispensable table headers/notes with their rows. Once the budget is exhausted, preserve omitted counts in the coverage ledger and return a partial result if material obligations remain unresolved.

### 5.7 `element_verification`

The model sees the **full source content of each accepted evidence fragment**, its qualified source header and obligation. It may select zero elements. Require structured selection, support snippets, relevance reasons, uncertainty and factual atoms with qualifiers. Validate selected IDs, quoted spans and source scope deterministically. A supporting heading/unit from another element must be included as its own evidence dependency.

For long tables, send all windows needed for the selected rows and their headers. Never show only 24,000 characters and then label the unseen remainder verified. Return a bounded source fragment if only that fragment was inspected. Track model-visible raw bytes/spans, not just nominal chunk IDs. Conflict sets preserve competing values with entity, period, basis and source. Relevant evidence can be insufficient to discharge an obligation.

### 5.8 `answer_generation`

Construct a coverage-aware portfolio of verified evidence under a fact/complex/broad token budget of 4k/16k/48k, subject to the provider's validated context limit. Use a deterministic greedy marginal-coverage selector with per-slot protection, relevance/quality tie-breaks and redundancy penalties; no claim of mathematically optimal coverage. Source content actually provided to the writer is recorded. Reserve budget for output and verification before selecting context.

Generate a structured answer and claim list from verified evidence only. Each substantive statement has evidence IDs, entity/period/scope and a support basis. Calculations use validated operands and explicit arithmetic, units and rounding. Distinguish standalone/consolidated, percentage/percentage-point and effective/proposed rules. Do not import external facts from model memory. Partial evidence supports a partial answer with named omissions; absence of retrieval is not evidence of absence.

### 5.9 `answer_verification`

Check every claim's source IDs, quoted support, scope and numeric derivation. A bounded semantic review compares nontrivial claims to the same source evidence; it cannot search for new evidence. Reject unsupported assertions, missing qualifiers and invalid arithmetic. One answer repair using the same verified evidence is permitted if reserved budget remains. Otherwise remove or qualify whole unsupported claims; never just remove a citation marker while retaining its assertion.

This stage adds explicit support checking to `final_plan`'s nine stages. It is not a generic self-reflection retrieval loop. Its benefit must be isolated by ablation; model agreement still does not prove entailment. Record accepted, rejected and unresolved claim counts.

### 5.10 `citation_render`

Render evidence IDs through immutable source records into actual supplied document names, relative paths and 1-based physical pages. Printed labels are optional. Unknown IDs cause claim rejection or a controlled error, not silent citation stripping. Return original canonical source text for the entire writer-visible source portfolio, including uncited context and cited source dependencies. Keep a separate detailed ledger of all earlier discovery/verification evidence.

The `chunks` set is the full writer-visible source portfolio; diagnostics report examined, rejected, writer-visible and returned counts. No fabricated or gold-copied snippets. If removing a claim changes its support set, recompute claim links while retaining every source fragment the writer saw. Do not hide irrelevant writer context to game context precision: the official adapter passes exactly the returned chunks, with original source content.

## 6. Bounded failure behavior

Statuses are `answered`, `partial`, `no_answer` for completed semantic outcomes. `no_answer` means no support found under the disclosed search coverage; avoid categorical corpus-absence claims without exhaustive support. Provider failure, corrupt collection or exhausted infrastructure is a typed HTTP error, not a semantic no-answer. A partially completed query may return verified partial content only if the response explicitly reports incompleteness and full spent resources.

Track global deadline, model attempts, input/output tokens and optional known-dollar cap. Unknown provider usage/pricing is null with a reason. A missing price cannot be treated as free or used to enforce an accurate dollar budget. Hard token/call/deadline caps remain active. Provider context limits override planning budgets.

## 7. Observability, security and truthfulness

Each response trace entry has exactly `step_name`, `description`, `input`, `output`. Put timing, counts, coverage, status, IDs and artifact references inside output, rather than adding fifth keys. Keep detailed execution records durably, without clipping evidence needed to reproduce decisions. Secrets are never recorded. Corpus text is untrusted task data; embedded instructions cannot change system behavior or initiate tools/web calls.

Langfuse records the root HTTP request, every stage, every model attempt/retry, embedding/reranking work, answer and verification calls. Missing tracing credentials or failed export is a visible deployment blocker for strict submission. A durable local event queue protects against transient outages, but local logging is not a substitute for the required export. Track ingestion resources separately and preserve unsuccessful attempts.

## 8. Ingestion performance and extension path

Ingestion cost is parsing/OCR plus indexing and optional enrichment. Estimate from measured page categories on the actual target server: `(native_pages * native_seconds + OCR_pages * OCR_seconds) / measured_effective_parallelism`, plus table work, vectors, serialization, API enrichment and observed contention. The equation is an estimate; full cold ingestion validates it. Do not reuse another machine's 0.6 s/page or API prices as promises.

Incremental artifact reuse helps repeat/updated collections by processing changed source/config hashes. Required new documents still finish before `/index` success; expose progress in private logs. Keep extraction caches and read-only model weights warm while measuring both cold and warm runs. Optional enrichment cannot create hidden post-success mutations of the active generation.

After the core is validated, test element vectors, a stronger pretrained embedding/reranker profile, selected visual retrieval or better parsing one at a time. Keep all model training/adaptation and recursive retrieval off in the strict profile. Adopt an extension only with a measured bottleneck, comparable budgets, clear resource cost and organizer eligibility where needed.
