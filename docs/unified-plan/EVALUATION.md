# Evaluation and honest experimentation

## Protected inputs and exact official scoring

Never modify Train/Evaluation/Evaluation.ipynb or public gold data. Record their hashes before and after experiments. Keep the benchmark and any aligned labels out of runtime imports, indexes, prompt examples and answer caches. Runtime input is only a query and the selected source collection.

The supplied notebook decomposes AI and gold answers into points and uses model judgments. Its implemented answer precision is `(AI point count − valid distinct extra-AI-point IDs) / AI point count`; recall is `valid distinct matched gold-point IDs / gold point count`. Empty cases follow the original code, rather than a rewritten preferred definition. Use the unchanged evaluator for official numbers.

Context precision is `number of relevant verdicts / number of returned chunks`. Context recall is `number of relevant verdicts / number of benchmark chunks`, and zero when benchmark chunk count is zero. The implementation does not perform semantic matching to each gold chunk and does not validate/deduplicate all verdict IDs. Its count ratio can exceed one and depends on chunk granularity. Preserve that behavior; do not clip or silently repair official scores. Report anomalies separately and use independent source coverage diagnostics. Fragmenting evidence to inflate the numerator is not a valid retrieval improvement.

The adapter passes the exact API answer and the complete returned writer-visible source portfolio to scoring. It never strips uncited writer context, replaces content with gold passages or changes source chunk boundaries for a favorable score. Document/page metadata accompany the unchanged source text. Keep discovery-only inspected elements in a separate diagnostic artifact.

## Runner design

Load the notebook as data and execute only its unchanged import/client/evaluator definition cells in an isolated namespace. Identify expected definitions and verify the source hash; fail if the expected notebook changes. Skip its sample invocation. Set provider credentials/model configuration externally, never write them back. If the provider is unavailable, mark evaluation not run; do not invent scores from a local approximate judge.

Call POST /query once per evaluation row and persist the raw response before scoring. Retain transport/model/scoring failures with row ID and stage. Do not average only the successes and present that as the full-set score. Provide scored-row means with counts plus a clearly declared failure-inclusive view; the original evaluator's aggregate remains separately labeled. Log evaluator model cost separately from application query cost.

Each run manifest contains dataset/split hashes, row IDs, code commit, config hash, collection generation/source hashes, parser/model/tokenizer revisions, provider/judge model, date, hardware, all budgets and prompt versions. Save per-row metrics, raw judge outputs, anomalies, failures, token/cost/latency and aggregate output.

## Split and tuning boundary

Before tuning, group semantically related public questions into query families using question text only and manual dev-independent review. Freeze seed 20261023 and aim at 70 development/30 holdout without splitting a family. Record actual counts if family integrity changes the ratio. Within development use inner validation/folds for thresholds, prompts and budgets. Gold can be used for offline development diagnostics, not runtime behavior.

This benchmark's document-sharing graph is highly connected: 98 questions share a connected source component, with C26 separate and B32 having no chunks. A normal document-disjoint 60/20/20 split is therefore not honestly available. Query-family holdout still shares sources and is weaker than unseen-corpus testing; disclose this. Use renamed/reordered and cold second-collection tests for operational robustness, without claiming they prove semantic generalization.

Freeze the candidate and all settings before inspecting holdout results once. If it performs poorly, report that result. Subsequent tuning makes that holdout development data; a new external/organizer test is then required for an untouched final claim. Selecting a rollback because it scored better on holdout is also holdout tuning.

## Source alignment and missing evidence

Use verified identity, issuer, period, jurisdiction and explicit identifiers before passage overlap. Preserve actual supplied names in runtime results. Offline benchmark aliases are confined to evaluation artifacts. The fact-sheet alias is strongly supported by sampled content but requires page/span alignment before being declared complete. The missing FR Doc. 2026-05960 must not be mapped to 2026-05959 or 2026-05961.

603 reference passages across 25 questions use that missing filename. They are not 603 proven unique unavailable facts. Measure alternate supplied support and classify aligned, ambiguous, absent-by-filename and unsupported-by-inspected-sources separately. Preserve the original benchmark denominator in official scoring. Never label all gold-unlisted source evidence irrelevant or use uncertain alignment as hard negatives.

A36 requests an unavailable report year; B32 has empty gold chunks. Test faithful limited answers without hardcoding their IDs or wording in serving code. Gold chunks are single-page references but have heterogeneous lengths; natural evidence fragments and source offsets remain the runtime unit.

## Experiment ladder

B0 is a strong lexical+dense+rerank baseline using the same parser, answer model and comparable budgets. B1 adds qualified metadata/identity; B2 adds skeleton/page survey; B3 adds explicit coverage portfolio; B4 adds claim verification. Also ablate generated versus deterministic cards, page versus optional element vectors, and parser variants only when there is time and an identified failure.

Report all four official metrics, failure count, semantic no-answer/partial rate, cold/warm p50/p95 latency, input/output tokens, unknown-usage count, known cost with pricing provenance and ingestion resources. Use paired query-level differences and uncertainty estimates; small samples and multiple experiments cannot support sweeping statistical claims. Model/provider changes invalidate a one-factor comparison unless treated as a separate profile.

Independent diagnostics include correct-document discovery, correct-page discovery, aligned source-span coverage, explicit obligation coverage, wrong-entity/period contamination, table-header visibility, actual token-tail visibility, claim support, numerical consistency and source-output fidelity. Oracle source/page tests are offline diagnoses only; they never feed gold locations into production retrieval. If raw evidence is missing, a stronger writer cannot fix that bottleneck.

## Promotion gate

A candidate must pass correctness/compliance invariants, retain evaluation failures, improve a predeclared development objective or justify its quality/cost trade-off, and preserve untouched holdout provenance. No threshold or fine-tuning run is required by this plan. All model training/adaptation remains off in the strict submission profile. A reported target is achieved only after a comparable real run establishes it.
