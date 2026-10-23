# Implementation and release checklist

All items begin unchecked because this package is design/audit work. The implementation repository must attach evidence before marking them complete.

## Contracts and environment

- [ ] M0 interfaces and fakes frozen.
- [ ] Actual server Python/dependencies/models/tokenizers pinned.
- [ ] Provider model/context/JSON capability verified.
- [ ] Secrets excluded and current prices sourced or explicitly unknown.
- [ ] Required Langfuse authentication and export verified.

## Source compiler

- [ ] Safe ZIP validation and expansion caps.
- [ ] Original PDFs/raw page artifacts retained.
- [ ] Every physical page classified; scan-required OCR complete.
- [ ] Section fallback without bookmarks.
- [ ] Natural evidence fragments/table-header dependencies.
- [ ] Metadata fields source-anchored or explicitly uncertain.
- [ ] Actual tokenizer windows and stable full-digest IDs.
- [ ] FTS/vector mappings validated before activation.

## Query execution

- [ ] All explicit comparison scopes preserved.
- [ ] Confirmed identity mismatches excluded; uncertainty escape tested.
- [ ] Finite page survey and raw-read omissions visible.
- [ ] Cross-scope source deduplication prevented.
- [ ] No reranker score used as factual verification.
- [ ] Full visible source fragments verified; unseen tails excluded.
- [ ] Coverage portfolio/claim support/calculations checked.
- [ ] All writer-visible source context returned.
- [ ] Ten trace steps in exact order with exactly four keys.
- [ ] Provider failure distinct from corpus absence.

## API and isolation

- [ ] Exactly POST /index and POST /query; no docs/health.
- [ ] Index blocks until durable complete generation.
- [ ] Failed build leaves old collection intact.
- [ ] Cold second collection and simultaneous queries isolated.
- [ ] In-flight reader survives reindex and restart tested.
- [ ] Private errors/logs redact credentials.

## Evaluation

- [ ] Gold/evaluator hashes unchanged.
- [ ] No runtime access to gold/alias maps.
- [ ] Reviewed family split frozen before tuning.
- [ ] All query/judge failures retained.
- [ ] Official metric behavior preserved including anomalies.
- [ ] Strong baseline/ablations at comparable budgets.
- [ ] Frozen holdout inspected once without selection.
- [ ] Source alias uncertainty and missing references disclosed.

## Submission

- [ ] Cold target-server ingestion time measured and realistically declared.
- [ ] Complete per-query cost/latency/Langfuse export reconciled.
- [ ] Repository matches deployed generation/config.
- [ ] Live provided-server routes verified.
- [ ] Write-up maximum 2–3 pages matches actual system.
- [ ] Event/team/build-window conduct provenance verified.
- [ ] Submission links and files provided before deadline.

