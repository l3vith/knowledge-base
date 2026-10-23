# Implementation plan — UFP 2.0

## 1. Scope, authority and starting conditions

Implement a general retrieval and answering engine from source PDFs, not an answer lookup for the public 100 questions. This plan is ready to assign to implementers with no conversation history. The present deliverable is planning only. Follow COMPLIANCE.md before moving core work into the event submission: the statement requires all core work within the twelve-hour window and forbids a prebuilt solution. It does not explicitly settle pre-event tooling/planning or AI-assistant eligibility.

Specifications apply in this order: supplied problem statement; this package's COMPLIANCE.md; CONTRACTS.md; ARCHITECTURE.md; this module plan; PROMPTS.md; agent briefs; configuration defaults. No document may silently weaken a higher authority. Configuration values are initial engineering budgets and may be tuned on development data; they are not organizer limits.

The implementation root is a new configurable `smart_kb/` directory. Preserve `Train/`, both input plans and the root statement. Use a local environment rather than modifying the system Python. Check the actual target OS, Python, CPU/RAM, disk, provider model/context capabilities and Langfuse credentials. A secondhand Windows installation report is not a deployment prerequisite.

## 2. Target source tree and ownership

| Module | Owned application paths | Purpose |
|---|---|---|
| M0 | `kb/contracts.py`, `config.py`, `errors.py`, `llm.py`, `tracing.py`, `textutil.py`, `testing.py`, `api.py`; dependency files | Frozen interfaces, budgets, clients, fakes and fail-closed application setup |
| M1 | `kb/ingest/parse.py`, `ocr.py`, `quality.py` | Page/block extraction, selective OCR, source provenance |
| M2 | `kb/ingest/segment.py`, `structure.py` | Recoverable sections, natural elements, table dependencies |
| M3 | `kb/storage/store.py`, `registry.py`, `vectors.py`; `kb/models/embedding.py`, `rerank.py` | Immutable collections, lexical/vector stores, pretrained adapters |
| M4 | `kb/ingest/cards.py`, `identity.py` | Qualified metadata, navigation cards, version rules |
| M5 | `kb/ingest/indexer.py`, `archive.py`; `kb/routes/index.py` | Safe ZIP to complete atomic generation |
| M6 | `kb/query/planner.py`, `routing.py` | Obligations, explicit scope preservation, routing guard |
| M7 | `kb/query/candidates.py`, `elements.py`, `triage.py` | Page candidates, bounded structure expansion, source retrieval and CPU ordering |
| M8 | `kb/query/survey.py`, `verify_evidence.py`, `coverage.py` | Finite page survey, source verification, coverage ledger |
| M9 | `kb/query/answer.py`, `verify_answer.py`, `citations.py`, `portfolio.py` | Supported synthesis, calculations, claim checks, faithful source output |
| M10 | `kb/query/executor.py`; `kb/routes/query.py` | Ten-stage execution and request assembly |
| M11 | `evaluation/runner.py`, `adapter.py`, `alignment.py`, `splits.py`, `diagnostics.py`; evaluation tests | Untouched official scoring, clean experiment manifests and diagnoses |
| I1 | `tests/integration/`, fixture archive builder, `scripts/smoke.py` | Real boundary integration and collection isolation |
| M12 | `scripts/benchmark.py`, `scripts/preflight.py`, deployment files, `docs/submission.md` | Server measurements, release gates, export and write-up |

Each owner also owns its directly named unit/contract tests. M0 owns common test fixtures. I1 may update shared wiring only through the lead's review. Each directory has `__init__.py`; package imports are explicit. Avoid a module importing another worker's unfinished concrete implementation: depend on the M0 protocols and receive services through injection. M10 and M5 perform assembly after contracts stabilize.

Required non-source outputs live under `data/` and `artifacts/`, excluded from source commits. Keep benchmark-derived evaluation artifacts under `artifacts/evaluation/`, never under the serving collection store. A release manifest references exact dependency/model/config/source hashes. Do not commit API keys, generated indexes, model weights or private traces to a public repository.

## 3. M0 — foundation and frozen seams

Create the common types and protocols exactly as CONTRACTS.md defines. Implement strict configuration validation, environment-based secrets, full-digest identities, tokenizer-aware budgets and request-scoped state. Load `reference-config.json`, validate schema/types/caps and resolve paths relative to the project root. Null prices/model revisions are unresolved deployment requirements; do not fabricate values. Development may use fakes, while strict startup rejects them.

Build the provider wrapper with one shared bounded scheduler, deadline-aware admission, transient retries, bounded JSON schema repair, per-attempt accounting and complete result validation. Missing usage remains unknown. Use a verified price record only. Reject unsupported response schemas rather than retrieving arbitrary brace substrings. Limit output through provider-supported parameters validated at startup; if JSON mode is unsupported, use text plus strict local validation and record the capability.

Implement Langfuse nested observations plus durable attempt/event records. Trace failures are observable, not swallowed. Create the API with only the two routers, automatic docs disabled and mandatory dependency initialization. Missing router imports fail startup. Use private CLI output for health checks. Build deterministic test fakes without loading production weights or requiring credentials.

Acceptance: route inventory exact; four-key traces; concurrency/deadline tested across nested calls; retries and unknown cost semantics correct; fake rejection in strict mode; secrets redacted; invalid schemas fail clearly; no network required for contract suite. Freeze `ufp-2.0` contracts and fake records before other workers integrate.

## 4. M1 — page extraction and selective OCR

Implement PDF opening from retained original bytes and return page records in physical order. Extract text, blocks, tables and coordinates while preserving raw/native artifacts. Add multi-signal quality classification: native text density, replacement characters, image coverage, layout integrity and blank-page detection. Keep threshold values configurable and record the decision basis per page.

Pilot the chosen adapter against a small stratified source sample and synthetic fixtures. Explicitly set OCR behavior; check installed API/documentation and output shapes. OCR only scan-like/corrupt pages, with bounded workers, timeout and quality flags. A broken OCR executable or missing language model is a startup/preflight failure for scan-required corpora. Do not consider a blank string a successful OCR result on a content-bearing page.

Persist native and OCR alternatives, extraction provenance, selected mode and raw page images where needed. Do not erase original bytes after staging. A content-hash cache key includes parser/OCR versions, DPI/language/options and source hash. A cache hit validates checksums before reuse. Rendered OCR files use a real writable temporary directory and are cleaned safely; do not depend on the Mac's `/tmp` alias behavior.

Acceptance: mixed native/scan/blank PDF preserves page count and order; OCR runs on the intended subset; a rotated scan remains traceable; corrupt PDFs and OCR failures cannot yield a ready collection; source anchors resolve; repeat parsing is deterministic within a fixed environment. Corpus-specific sample checks are diagnostics, not hardcoded runtime rules.

## 5. M2 — structure, natural elements and source dependencies

Build the section tree from verified outline ranges, visible TOC candidates and heading/layout evidence. Fall back to page-local headings with explicit uncertainty. Validate tree bounds and page membership; reject loops and invalid intervals. Preserve printed labels independently from physical page numbers.

Segment paragraphs/list items/tables on a single page. Retain numerical formatting and reading order. Long tables use row-bounded fragments with explicit header, unit and note dependencies. Record cross-page continuation as an edge, never as an element spanning an untracked page range. Annotation and data are separate: positional boilerplate flags cannot delete definitions, captions or table units from the raw/searchable source.

Create search windows with a tokenizer injected from M3, preserving offset maps. The canonical element's text is immutable. Prefixes and repeated contextual headers are separate from exact text. Reference extraction recognizes explicit section/table/note/page references and returns candidates/confidence without inventing semantic relations.

Acceptance: a table row still resolves its unit and period; source round-trip is exact; no numeric or row splitting; fallback works without bookmarks; repeated critical headers survive; different scopes with identical text remain distinct; source mapping of every indexed window is valid.

## 6. M3 — storage, collection registry and pretrained models

Implement SQLite records/FTS with foreign keys and read-only query handles. Preserve all source text, store navigation text separately and parameterize FTS expressions. Define ranked hits as stable IDs plus scores/ranks, never raw arbitrary record ordering. FTS fallback cannot interpret user input as syntax or drop semantic negation.

Load the pinned FastEmbed model profile only after verifying supported names, tokenizer limit, normalization, dimensions and actual ONNX artifact. Store normalized page-window vectors and IDs; exact FAISS unrestricted search and exact allowed-subset scoring use the same matrix. A filter must precede selection. Avoid a “retrieve global 200 then filter” implementation. Optional element vectors are feature-flagged and not required to make element FTS available.

Build the registry with staging directories, owner-checked lock files, complete manifests, atomic active pointers and snapshot leases. Failed builds never modify active. Queriers retain their resolved generation even if another is activated. Keep old generations until a separate safe cleanup command proves no readers need them. No blind time-based stale-lock removal.

Acceptance: concurrent old/new generation reads, failed rebuild retention, restart recovery, equal basenames, absent collection, empty/null allow-set distinction, scoped top-k matches brute-force reference, vector/ID checksum corruption rejected, and test fakes cannot enter strict production.

## 7. M4 — automatic identity and page cards

Derive identity from cover/front matter, embedded metadata, trustworthy headings and identifiers. Retain alternative candidates and provenance when sources conflict. Fields are individually source/inferred/unknown. Do not make the most frequent year the reporting period; do not collapse distinct legal entities or different regulatory proposals because the issuer/year match.

Build source-derived page cards without mandatory model calls. Preserve source excerpt anchors and quality flags. Optional enrichment receives source text and must return anchored values or unknown. Cache optional enriched outputs by all relevant hashes; output is navigation-only. An enrichment failure yields a recorded fallback card when required source extraction is valid.

Version matching requires entity, kind, scope, identifiers and comparable periods. Explicit multi-year/multi-entity queries preserve each request. “Latest” never crosses to a different legal entity or unrelated document class. Runtime identity routines cannot import benchmark alias maps. Offline filename alignment belongs exclusively to M11.

Acceptance: ambiguous identity stays uncertain; missing year is not invented; subsidiaries remain distinct where appropriate; renamed PDFs still route from content; false proposal aliases are refused; page cards work without an LLM; generated fields never appear as original evidence.

## 8. M5 — blocking index orchestration

Implement archive validation before extraction. Enforce resource caps, safe relative paths, encrypted-file policy and supported types. Ignore only known benign archive metadata entries with a manifest entry explaining exclusion; do not silently ignore an unsupported user document. Reject duplicate normalized paths and preserve distinct same-basename subpaths.

Run parse → structure/elements → identities/cards → FTS/vectors → validation → manifest/atomic activation. Each required document/page/index component must finish. Use staged, restart-safe writes; record page counts and failures. Optional LLM enrichment is a bounded pre-activation phase only when enabled. Do not mutate active generation after success.

Return `/index` success only after commit. Client/proxy timeout settings must cover measured long ingestion; HTTP keep-alive is not the request processing timeout. Private progress logs show page/category counts and estimated completion without adding public endpoints. Handle aborted/disconnected requests without leaking a ready partial generation.

Acceptance: malicious ZIP rejected; injected mid-build failure preserves old collection; scan-required archive cannot pass without OCR; mixed supported/unsupported input fails clearly; successful response implies all manifest checks pass; a cold second collection leaves the first intact.

## 9. M6 — query obligations and routing guard

Implement the planner prompt and strict schema. Preserve explicit entity, period, scope, identifier and negation requests. Build coverage slots without collapsing comparison axes. Use at most eight aspect groups but retain every explicit slot within the configured 64-slot budget; exceeding it becomes an explicit limitation. Deterministic fallback extracts constraints from the actual query, not canned public-question templates.

Route from content-derived metadata. Hard exclusions require verified mismatches; uncertain fields remain soft. Explicit scopes bypass shortlist soft caps. Empty/ambiguous routes schedule the fixed global escape branch. An LLM card-level no-answer recommendation cannot skip raw source search. Missing requested periods remain visible rather than substituted with old data.

Acceptance: synthetic comparison retains two entities and two periods; no-year/unknown catalog falls back; known wrong regime excluded; misleading filename does not override content identity; empty route does not become unsupported refusal; queries carry no A/B/C IDs into runtime behavior.

## 10. M7 — page/element retrieval and CPU triage

Implement the source lexical, page vector, heading/section and bounded reference candidate generators. Preserve raw per-generator scores and origin; fuse page ranks using fixed RRF. Apply scope before top-k and per-obligation quotas before global cap. Exact identifiers/numeric vocabulary have explicit signals without treating numerical equality as full support.

For broad queries enumerate available source-derived cards within routed documents up to a predeclared survey budget; preserve all omission counts. Read selected-page elements plus scoped element FTS hits and source dependencies. Do not just expand top-k parents and call that coverage innovation. Similar text in two scopes remains separate evidence.

Order verification candidates with actual-token pair windows and the pretrained CPU ranker. Default no auto-keep/drop thresholds. Respect configured pair cap and mark unscored candidates. Keep dependency groups intact and protect at least one plausible candidate for each covered slot where possible. Budgets that preclude this produce a visible partial-coverage state.

Acceptance: correct scope survives near-duplicate distractors; broad multi-section fixture visits evidence outside top similarity pages; long source tail can enter through a token window; null scores do not win sorting; negation survives model input; repeated contexts do not inflate the evidence list; cap behavior is explicit.

## 11. M8 — finite survey, verification and coverage ledger

Implement page-card survey batches with IDs/obligation relevance and source-inspection escalation for ambiguity. The budget is fixed before execution; do not add iterative retrieval. A rejected lossy card cannot veto independently strong source matches. Record eligible/surveyed/raw-read/omitted counts and distinguish those kinds of visibility.

Verification batches contain full bounded source fragments and required table/header dependencies, not clipped unseen tails. Output selection may be empty. Validate IDs, support quote offsets, source scope and schema. Record factual atoms with entity/period/units/basis; conflicting values remain qualified alternatives. Evidence relevance alone cannot mark an entire broad obligation complete.

Implement CoverageLedger updates as append-only decisions with deterministic summaries. Scope overflow, failed model batches and missing source are distinct limitations. Do not label all dropped evidence negative in an offline training dataset. No training is enabled by default.

Acceptance: header-dependent numeric fixture is supported only with its header; zero-relevant batch selects none; a fabricated quote is rejected; unseen table tail cannot be verified; summary omission remains discoverable via raw source branch; a provider failure is not labeled corpus absence.

## 12. M9 — portfolio, synthesis, answer verification and citations

Select verified evidence under the writer context budget using marginal obligation coverage and redundancy control. Protect source dependencies and explicit scope slots. Count tokens with the provider tokenizer when available; otherwise use a conservative estimate labeled as such and enforce a validated safety margin. Reserve output/verification budget before context construction. There is no arbitrary 200-word answer cap when the task requires broad synthesis.

Return structured claims plus answer, using evidence IDs only. Validate calculations through a small allowlist of deterministic arithmetic operations, not executable model code. Include period, currency, units and accounting/regulatory basis. Distinguish supported conclusions from uncertainty and avoid claiming requested data exists when it does not.

Check claim support using exact anchors, IDs, numeric derivation and a bounded semantic pass on the same evidence. One same-source answer repair is permitted within reserved budget; no new retrieval. Remove/qualify complete unsupported claims. Render actual source names/pages deterministically. Return the entire writer-visible source portfolio, including uncited context, so context scoring reflects real answer context. Keep discovery-only evidence in the detailed ledger.

Acceptance: unknown citation ID cannot leave an uncited factual assertion; different-year figures are not merged; percentage-point calculations are correct; writer-visible unused context is still returned; output fragments match source text; partial answer names omitted obligations; no evidence produces a grounded search-limited refusal.

## 13. M10 — executor and query API

Assemble the ten fixed stages with explicit QueryContext, bound generation, budget ledger, trace and dependency injection. Each stage executes once, with bounded internal batches. Include skips in order. Pass deadlines through CPU/model work and never schedule a model call after exhaustion. A failed stage preserves the completed execution/usage record.

Build the public response and typed errors from CONTRACTS.md. A useful verified partial result can be delivered with limitations; a raw infrastructure failure is not a no-answer. Resolve collection once per request, use immutable source mappings, and ensure no cache key omits generation/config/model identity. Do not cache answers by public question ID or load gold labels.

Acceptance: route/schema tests, ten-step order, missing collection, concurrent requests do not mix state, a reindex cannot alter an in-flight query, deadline/429/retry costs are retained, Langfuse IDs reconcile with the response and privacy checks pass.

## 14. M11 — offline evaluation and source alignment

Read EVALUATION.md first. Keep the notebook untouched and hash-verified. A runner invokes its unchanged definition cells in an isolated namespace, sets credentials/config externally and skips sample demonstration execution. Snapshot the actual evaluated dataset and model/config manifest. Preserve all query failures and denominators in the result bundle.

Create a frozen query-family split with seed 20261023, aiming at 70 development/30 holdout without breaking families. Inspect dev/inner-validation only for tuning. Document shared source documents and the fact that a fully document-disjoint split is impractical on this benchmark's connected source graph. Exact counts may move with family integrity; record manifest IDs before tuning.

Offline alignment uses verified identity/identifier first, then page/span support with conservative confidence. Missing/ambiguous references remain unresolved. A text overlap threshold alone cannot alias distinct proposals. Gold-unlisted retrieved evidence is not automatically irrelevant. Keep benchmark content entirely outside runtime stores.

Implement official metric export plus independent document/page/span/obligation/claim support diagnostics. Evaluate baseline controls and source/identity/coverage/verification ablations at comparable budgets. No training, threshold calibration or prompt changes based on the final holdout.

Acceptance: notebook hash unchanged, exact API chunks passed to scorer, all failures retained, missing-source references counted honestly, split family boundaries held, no holdout-derived tuning artifact, baseline and candidate manifests comparable.

## 15. I1 — integration and adversarial correctness

Construct small synthetic PDFs/archives that test real boundaries: native text, scanned page, table with unit header, repeated paragraphs in different years, two entities with near-identical names, a missing period, explicit cross-reference and an unanswerable query. Synthetic expected facts come from the fixtures, not hardcoded public benchmark answers.

First integrate the service with deterministic fakes for contract correctness. Then run real PDF/OCR/vector adapters without paid calls. Finally, when actual provider credentials are configured, run a small real model/Langfuse smoke and clearly distinguish it from mock success. Contract pass alone is not evidence of live model success.

Test API route inventory, blocking index completeness, multiple collections, failed reindex, restart, source-round-trip citations, injection text in PDFs, token tails, context return fidelity, provider failure and budget omissions. Store request/response artifacts and generation hashes. Lead resolves shared wiring changes, not each worker independently modifying contracts.

## 16. M12 — performance, tuning and release

Measure cold and warm ingestion by native/scan/table categories on the actual provided server. Record CPU/RAM/disk/model cache/API rate limits, page counts, wall time, failures and total ingestion token/cost. Use the full corpus to validate the declared expected ingest time; add honest variability headroom rather than inferring a universal SLA from a tiny pilot.

Run a dev experiment ladder: strong hybrid/rerank control; qualified identity; source structure/page survey; coverage portfolio; claim verification. Change one mechanism at a time, preserve model/budget comparability and show quality/cost/latency trade-offs. Freeze release config before final holdout. If the holdout is poor, report it; do not use it to select a rollback and call the selected result untouched.

Perform cold named-collection indexing, renamed/reordered source checks, concurrency/restart tests, route/schema/source invariants and Langfuse export reconciliation. Verify protected input hashes. Prepare max 2–3-page architecture write-up describing the actual final system, measured evidence, limitations, server/API details and declared ingestion time. Include repo link and trace/export link in submission instructions; do not fabricate a submission or model result.

Acceptance: all checklist gates have artifact evidence; output claims match implementation; required endpoints reachable on provided server; no unresolved default model revision/price masquerading as verified; unknown pricing clearly reported and resolved for cost-scored submission; holdout provenance intact.

## 17. Build waves and dependency gates

Wave 0: M0 contracts/config/fakes/client/event skeleton. Gate G0 freezes records and imports.

Wave 1: M1, M2, M3, M4 and M6, M7, M8, M9 can develop against M0 fakes. They are logical parallel tasks, not a requirement for more than two human team members. M2/M4 use fake parsed pages initially; M7–M9 use MemoryStore and fake model responses. M11 freezes splits and adapter contracts independently.

Wave 2: M5 assembles ingestion from M1–M4; M10 assembles query from M6–M9. Gate G1 is a synthetic archive → real stores → fake-query end-to-end pass with source fidelity.

Wave 3: I1 executes real-boundary tests; M11 establishes the baseline and diagnostics; M12 measures server performance and prepares export. Gate G2 is real provider plus Langfuse smoke, not just local mocks.

Wave 4: development-only ablations/tuning, freeze, one holdout evaluation, release checklist and write-up. Gate G3 is evidence-backed release readiness. Time pressure may reduce optional enrichment/models/UI; it must not remove required source preservation, two routes, traces, account logging or evaluator integrity.

## 18. Required implementation artifacts

Deliver code and lockfiles, dependency/model/license manifest, safe collection compiler, ten-stage runtime, API contract tests, synthetic boundary fixtures, untouched official evaluator reference, split/experiment manifests, per-query metrics and failures, complete Langfuse export, measured ingestion report, release configuration and short write-up. Each worker completion report names owned files, test commands/results, unresolved risks and interface changes. An unchecked item remains incomplete; do not replace measurements with design confidence.
