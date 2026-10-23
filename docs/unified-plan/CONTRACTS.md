# Frozen implementation contracts — UFP 2.0

This file takes precedence over interface examples in the source plans. Freeze these contracts in M0 before independent module work. Changes require a schema version increment, migration notes, fake-store updates and all contract consumers passing again. The package is a specification, not executable application code.

## 1. Common types and identity

Use typed Python records, preferably frozen dataclasses for persisted objects and Pydantic request/response models at the API boundary. IDs are opaque strings. Do not parse business meaning from an ID. Dates are ISO 8601 strings when known, null otherwise; timestamps are UTC. Numeric model scores are finite floats or null with a reason; never NaN.

`CollectionRef`: `collection_name`, `collection_key`, `generation_id`, `manifest_sha256`, `config_sha256`, `schema_version="ufp-2.0"`.

`SourceAnchor`: `doc_id`, `physical_page` (1-based), `element_id` (nullable for page metadata), `char_start`, `char_end` (half-open offsets into selected canonical page/element text, domain stated), `bbox` (nullable `[x0,y0,x1,y1]` in PDF points), `extraction_variant`, `source_sha256`. A quote must match its declared text domain; page offsets and element offsets cannot be interchanged.

`MetadataValue`: `value` (string/list/null), `origin` (`source`, `inferred`, `unknown`), `confidence` (nullable float in [0,1]), `anchors` (list of SourceAnchor), `reason` (string). Empty anchors are permitted for an inference, never represented as source confirmation. Runtime consumers must inspect origin/confidence before applying hard filters.

`doc_id = "doc_" + SHA256(original_pdf_bytes)` using the full digest. Generation-scoped database keys are `(generation_id, doc_id)`. Duplicate files with equal bytes create one content document and multiple `SourceFile` records, preserving all original names. Select the lexically first normalized source path as deterministic display name unless caller specifies a source path. Different bytes are different documents even if semantically similar.

`page_id = SHA256(doc_id + physical_page + extraction_config_hash)` with unambiguous length-prefixed serialization. `element_id = SHA256(page_id + parser_revision + element_kind + canonical_anchor + exact_text_hash)`. `window_id` similarly includes parent ID, tokenizer revision and token/span bounds. A formatting-normalized fingerprint may aid candidate deduplication but cannot replace these identities. IDs never depend on benchmark rows or gold filenames.

## 2. Persisted source records

| Record | Required fields and invariants |
|---|---|
| SourceFile | `source_file_id`, `doc_id`, `original_name`, `relative_path`, `bytes`, `sha256`; path is ZIP-relative and safe; actual supplied name retained |
| Document | `doc_id`, source file IDs, `page_count`, `pdf_artifact`, extraction/config revisions, `quality_flags`, metadata map; original bytes retained |
| DocumentCard | `doc_id`, title/entity/issuer/kind/identifier/jurisdiction/reporting-period/publication/effective-date/status/scope MetadataValues, topics, navigation summary, `derived_from`, enrichment provenance |
| Section | `section_id`, `doc_id`, nullable parent, `title`, physical page interval, source heading anchors, method, confidence; valid ordered bounds |
| Page | `page_id`, `doc_id`, `physical_page`, nullable printed label, width/height, raw/native/OCR artifact refs, selected text, extraction mode, quality class, section IDs, text hash |
| Element | `element_id`, `page_id`, `doc_id`, page, kind, exact `text`, source anchors, section path, table/continuation IDs, header/footnote dependency IDs, quality flags, token counts by tokenizer |
| SearchWindow | `window_id`, parent element/page, exact source span mapping, generated prefix stored separately, model input text, tokenizer/model revision, tokens before/after windowing, truncation=false |
| PageCard | page/doc IDs, source headings/captions, deterministic excerpts with anchors, terms, source metadata refs, optional generated summary, card quality; never evidence itself |
| ReferenceEdge | edge ID, source anchor, relation (`explicit_reference`, `table_continuation`, `section_membership`), target candidates, resolution confidence; no inferred factual equivalence |

Store all core records in SQLite with foreign keys and generation metadata. Tables: `source_files`, `documents`, `document_cards`, `sections`, `pages`, `elements`, `windows`, `page_cards`, `reference_edges`, `metadata_anchors`, `build_events`. FTS virtual tables index source text and navigation descriptors separately. Join through stable IDs; parameterize all SQL. Rebuild FTS or update it transactionally with its source table; verify synchronized counts before activation.

Vector artifacts include float32 normalized arrays, `window_ids.json`, FAISS index, model/tokenizer/ONNX manifest and checksums. Empty or zero-norm embeddings are typed build failures unless tied to a classified blank page with no vector. Multiple page windows are aggregated by page; recording one vector per long page after silent truncation is prohibited.

## 3. Query records

`Obligation`: `obligation_id`, `aspect`, `query_spans`, entity refs, period constraint, scope/jurisdiction constraints, `required`, `exhaustive`, exact lexical phrases. Source-confirmed facts cannot originate here.

`QueryPlan`: original query, intent (`fact`, `complex`, `broad`), aspect groups, obligations, explicit entity/period/identifier requests, uncertainty, overflow, fallback flag, immutable budget profile. An “eight aspect” limit does not truncate explicit comparison slots.

`RouteDecision`: eligible document IDs, excluded IDs with confirmed mismatch reasons, unresolved identities, explicit missing requests, global-escape flag, score explanations. Routing does not emit final semantic no-answer.

`PageCandidate`: page ID, per-obligation matched signals, per-generator ranks/scores, section/reference origin, card/raw-inspection state. Rank fusion scores are not probabilities.

`ElementCandidate`: element ID, source scope, obligation IDs, search origin, lexical scores, cross-encoder window scores, score status, dependency IDs. Do not map null score to infinity or a selected decision.

`VerifiedEvidence`: element/fragment ID, source IDs/anchors, exact content, source-header dependencies, obligation IDs, support quotes and checked offsets, relevant/uncertain decision, factual atoms, conflict IDs, complete-visibility flag. If only a fragment was inspected, a fragment record with its exact bounds is required.

`Claim`: claim ID, rendered text, entity/period/basis/units, evidence IDs, source quote spans, nullable calculation record, verification outcome/reason. A calculation stores operation, operand values/units/evidence, result and rounding. Arbitrary model-generated code is never executed.

`CoverageLedger`: one row per obligation with eligible/routed documents, cards available/surveyed, raw pages inspected, evidence considered/verified/writer-visible, status (`supported`, `partial`, `unresolved`, `out_of_scope`), limitations and budget omissions. Aggregate scope counters accompany per-slot rows. “Supported” means the selected evidence supports that slot; it is not proof that every relevant fact in the corpus was found.

`QueryContext`: request ID, CollectionRef, configuration snapshot, monotonic start/deadline, BudgetLedger, stage recorder, Langfuse root, durable artifact writer, evidence ledger. Pass this explicitly; never use a mutable global “current collection.”

## 4. Budget and model interfaces

`BudgetLedger.reserve(stage, expected_input_tokens, output_limit, attempts)` returns a reservation or a typed budget denial. `charge(attempt_record)` records actual usage and reconciles reservation. Scheduling reserves output and verification before answer context is packed. Failed attempts and retries remain in usage. Admission check precedes provider semaphore acquisition and rechecks after waiting. A denied model call cannot be charged as zero successful work.

`LLMClient.json_call(stage, system, payload, schema_name, max_output_tokens, ctx) -> LLMResult` and `text_call` with equivalent parameters. `LLMResult` contains validated value/text, model/provider revision, attempt IDs, known usage/cost or null, finish reason, latency and schema repair status. Network timeout uses remaining request time. Retry only transient HTTP/network failures and bounded schema errors; honor Retry-After within deadline. Do not parse arbitrary first-to-last braces as trusted JSON: accept a complete JSON value or one complete fenced JSON block, then validate schema and reject extra unparsed content.

`EmbeddingModel.embed_documents(texts, ctx) -> EmbeddingBatch`; `embed_query(text, ctx) -> Vector`; `token_count(text) -> int`; model formatting/instructions follow the pinned card and are tested for no double-prefix. The adapter enforces preflight window length, tracks actual model-visible inputs and materializes generator outputs before shape validation.

`Reranker.score_pairs(pairs, ctx) -> list[PairScore]`; each pair has query, mapped evidence window and actual token count. Return order must match submitted pair IDs, not a backend's implicit sorting. Logits are used for ordering. Unsupported model backends fail startup, never silently substitute a hash embedder in production.

`TraceRecorder.stage(name, description, input_summary)` owns one output entry and its child work. `complete(output_summary)` finalizes it. Detailed evidence/attempt artifacts remain durable and are referenced by request-local IDs. `FakeLLM`, `HashEmbedder`, `FakeReranker`, `MemoryStore`, `FakeClock`, `FakeTraceSink` are test-only injection targets; strict startup rejects them.

## 5. Storage and dependency interfaces

`CollectionRegistry.resolve(collection_name) -> CollectionRef`: binds one ready generation or raises not-found/not-ready. `begin_build(name, source_manifest, config) -> BuildHandle`; `commit_ready(handle, validated_manifest) -> CollectionRef`; `abort(handle, error)` leaves active unchanged. Names are normalized once; collisions after normalization are rejected. Lock owner records include process identity/start identity and unique token; release only a lock owned by the caller. Age alone never authorizes lock theft.

`Store.get_documents(ids=None) -> list[Document]`; `get_document_cards(ids=None)`; `get_page_cards(doc_ids)`; `get_pages(page_ids)`; `get_elements(page_ids=None, element_ids=None)`; `get_dependencies(element_ids)`; `get_sections(doc_ids)`; `get_reference_targets(source_ids, depth)`.

`Store.search_pages(terms, allowed_doc_ids, limit) -> list[SearchHit]`; `search_elements(terms, allowed_page_ids, allowed_doc_ids, limit)`; `dense_pages(query_vector, allowed_doc_ids, limit)`. Empty allow-set means search nothing; null allow-set means all documents in this bound generation. This distinction has a dedicated contract test. Dense scope is applied before top-k; returned IDs cannot cross the allowed set. `Store` is read-only for queries.

Stage functions use these names and return typed records:

| Owner | Function | Result |
|---|---|---|
| M6 | `plan_query(query, catalog, llm, ctx)` | QueryPlan |
| M6 | `route_documents(plan, catalog, ctx)` | RouteDecision |
| M7 | `find_candidate_pages(plan, route, store, embedder, ctx)` | candidates + scope ledger |
| M8 | `survey_pages(plan, candidates, store, llm, ctx)` | selected page IDs + survey ledger |
| M7 | `retrieve_elements(plan, page_selection, store, ctx)` | ElementCandidates |
| M7 | `triage_elements(plan, candidates, reranker, ctx)` | bounded candidate batches + omission ledger |
| M8 | `verify_elements(plan, candidates, store, llm, ctx)` | VerifiedEvidence + CoverageLedger |
| M9 | `generate_answer(plan, evidence, llm, ctx)` | DraftAnswer + writer portfolio |
| M9 | `verify_answer(draft, portfolio, llm, ctx)` | VerifiedAnswer |
| M9 | `render_citations(answer, portfolio, store, ctx)` | QueryResponse |
| M5 | `index_archive(zip_stream, collection_name, services, ctx)` | IndexResponse after activation |
| M10 | `execute_query(request, services, ctx)` | QueryResponse with all stage traces |

M0 creates these protocols and deterministic fakes first. Producers and consumers may be implemented independently using those fakes. Production imports cannot swallow missing router/module imports and appear healthy; startup fails closed if a required component is missing.

## 6. Public HTTP contract

Expose exactly two method/path pairs, with automatic documentation routes disabled. There is no public health/status/metrics endpoint. Use CLI/private logs for liveness. Keep any authentication scheme configurable to the organizer harness; the brief does not specify an HTTP auth format. Do not invent a mandatory bearer format that breaks the caller.

`POST /index`: multipart `file` containing the ZIP, form `collection_name` string. These field names are this team's explicit convention because the brief specifies inputs but not multipart keys. Integration must adapt to the organizer's caller if its keys differ. Do not change semantic behavior. Block until required ingestion, validation and durable activation complete; return HTTP 200 only then.

```json
{
  "success": true,
  "collection_name": "demo",
  "generation_id": "gen_example",
  "documents": 2,
  "pages": 8,
  "elements": 31,
  "indexing_seconds": 4.2,
  "warnings": []
}
```

The values above illustrate schema only; they are not measured results. No background-ready 202 response. If a collection name exists, build and atomically replace its active generation according to the same contract; concurrent conflicting builds return 409. Retain old generations while readers use them.

`POST /query`: application/json with exactly required `collection_name` and `query`; optional fields are not required by the organizer. Reject empty/oversized strings with 422. Example completed no-support schema:

```json
{
  "request_id": "req_example",
  "collection_name": "demo",
  "generation_id": "gen_example",
  "status": "no_answer",
  "answer": "No supporting information was found within the searched collection scope.",
  "chunks": [],
  "trace": [],
  "coverage": {"obligations": [], "limitations": ["Example only"]},
  "usage": {"input_tokens": null, "output_tokens": null, "cost_usd": null, "unknown_reason": "Example only"},
  "latency_ms": 0,
  "langfuse_trace_id": null,
  "observability_status": "example"
}
```

For compactness this schema example has an empty trace; a real successful response must contain all ten ordered stage entries, including skips. A submitted service requires a real Langfuse trace ID/export, not the example nulls. Status `partial` carries verified content and explicit coverage omissions; unsupported provider failure alone cannot produce this example as if it were a corpus fact.

Each real chunk contains `chunk_id`, actual `doc_id`, `document` (supplied filename), `source_path`, `page` (1-based physical), `content` (exact canonical source text), source anchors, kind, `evidence_role` (`claim_support`, `context_dependency`, `writer_context`), and `cited_by_claim_ids`. Optional printed label and source-derived header are separate fields. The entire writer-visible **source portfolio** is returned, including writer context that ends up uncited, to prevent hiding irrelevant evidence. All cited support must be in that set. Discovery-only rejected elements remain in the durable execution ledger and trace counts, not masquerading as final used chunks.

One source fragment has one stable chunk ID regardless of the number of claims citing it. If the writer needs a source header, return that header as its own anchored dependency or within a genuinely contiguous source fragment; do not fabricate a source paragraph by concatenating disjoint text. Generated explanatory prefixes are separately marked and never evaluated as original content. The official adapter passes exactly this API `chunks[].content` list, without cherry-picking only cited chunks.

## 7. Step trace and observability

Every trace object has **exactly** four keys:

```json
{
  "step_name": "element_verification",
  "description": "Check source evidence against requested obligations",
  "input": {"candidate_count": 12, "obligation_ids": ["o1"]},
  "output": {"verified_count": 4, "uncertain_count": 1, "duration_ms": 180, "artifact_id": "artifact_example", "complete": true}
}
```

The ten names are `query_planning`, `routing_guard`, `candidate_pages`, `page_survey`, `element_retrieval`, `element_triage`, `element_verification`, `answer_generation`, `answer_verification`, `citation_render`. Additional per-stage details belong inside input/output, not as fifth keys. Skipped output includes `skipped=true`, reason, zero work counts and duration. Root request timing includes queueing, local models, provider retries, rendering and serialization.

Durable attempt records include request/generation/stage, attempt number, actual provider/model, start/end, status, usage values or null/reason, verified price-record ID, cost or null, input/output artifact hashes and token visibility. Redact authorization keys, cookies and environment secrets. Public artifacts use opaque IDs; no absolute host paths, credentials or writable URLs. Keep private full details for export.

Langfuse is required, independently of the response trace. Flush/drain on shutdown and before export verification. Explicitly surface export failures and durable queue depth. Strict release requires successful query trace reconciliation, not merely client initialization or swallowed exceptions. If provider-reported tokens are unavailable, label estimates separately; never present them as actual usage. Prices have currency, per-token units, source, effective date and model ID; null is the initial price state.

## 8. Error semantics

Error body: `error.code`, `error.message`, `request_id`, optional retryable flag and completed-stage diagnostics. Do not echo secrets or raw stack traces publicly.

| HTTP | Codes and handling |
|---|---|
| 400 | `INVALID_ARCHIVE`, `UNSUPPORTED_DOCUMENT`, `UNSAFE_PATH`, `RESOURCE_LIMIT`; explain offending safe path without extraction outside staging |
| 404 | `COLLECTION_NOT_FOUND`; no fallback to a default collection |
| 409 | `INDEX_IN_PROGRESS`, `COLLECTION_NOT_READY`; old ready generation still queryable where present |
| 422 | `INVALID_REQUEST`; empty query, invalid collection name, malformed transport |
| 503 | `PROVIDER_UNAVAILABLE`, `MODEL_UNAVAILABLE`, `OBSERVABILITY_UNAVAILABLE`; distinguish infrastructure from absence of evidence |
| 504 | `QUERY_DEADLINE`, `INDEX_DEADLINE`; preserve spent usage, no false indexing success |
| 500 | `INDEX_BUILD_FAILED`, `CORRUPT_GENERATION`, `INTERNAL_ERROR`; active generation remains consistent |

A token/call cap can return a verified `partial` response if useful supported content exists and its limitations are explicit. Otherwise return a typed resource/budget error rather than an unsupported answer. Do not automatically retry a non-idempotent index request after an ambiguous client disconnect; inspect private build logs and generation state.

## 9. Required compatibility invariants

1. Every source citation resolves to a retained document and valid physical page in the bound generation.
2. Every returned source fragment matches its persisted text/anchor; every claim has valid support IDs or is removed/qualified.
3. Every writer-visible source fragment is returned, and every returned chunk was actually provided to the writer or is a transparent cited source dependency.
4. No query crosses generation/collection boundaries through stores, IDs, caches or global variables.
5. No benchmark/gold/evaluator input is imported by serving code or accessed during `/index` or `/query`.
6. Empty scope means empty search; unknown metadata cannot silently hard-exclude all documents.
7. Actual tokenized model inputs fit verified limits, including prefixes, query, separators and output reservation.
8. All retries/verification calls are accounted; unknown cost/usage remains null with explanation.
9. Index success follows complete durable validation and atomic activation; failure preserves the previous active generation.
10. Route inventory is exactly the two allowed method/path pairs; step traces have the four required keys.
