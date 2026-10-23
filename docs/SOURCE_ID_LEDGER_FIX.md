# Ledger repair: immutable source IDs

The fresh ledger benchmark lost seven valid findings when the model rewrote numeric Markdown punctuation. This repair removes model-owned fact strings from the normal ledger path. It also removes the separate extraction call.

## Source authority

`kb/query/anchors.py` builds frozen sentence/support/table-row and quantity anchors from the original source. IDs derive from document identity, parent element identity, absolute character offsets, kind and exact text. Raw quotations remain unchanged; display cleanup is separate. Different occurrences of the same value remain distinct. The catalog is read-only and can be rebuilt from indexed source.

The model sees short aliases such as A1 and V1. A saved per-call mapping resolves these to immutable source IDs; aliases are not reused as global identities. Catalogs and alias maps are stored in query diagnostics, without credentials. Quantity recognition is a bounded lexical helper, not a complete scientific-math parser; complete source sentences remain authoritative when a value pattern is unrecognized.

## Integrated verification

With `KB_ANALYTICAL_WRITER=ledger`, `KB_LEDGER_EXTRACTION=integrated` is now the ledger default. Existing source-verification calls select exact sentence IDs and may attach value/scope/metric/modality/qualification IDs. The model does not rewrite quantities, units or method labels. Fields it cannot establish can be omitted. Existing adapters without typed fields retain their exact verified source quotations as locally bound findings.

The standalone `ledger_extract` call is removed from this path. Only `KB_LEDGER_EXTRACTION=separate` opts into the historical extraction adapter for diagnostic ablations. Its value strings no longer own source facts either: values are rebound from exact source anchors, while invalid optional values produce warnings. Punctuation equivalence in this compatibility adapter never supplies generated source quotations or accepts a fabricated numeric value.

Invalid primary source IDs and mixed-document evidence are rejected. Invalid optional value/scope/metric labels do not delete a valid source finding: code resolves quantities from its anchors and resets unknown labels. Unresolved qualifications remain visible and force partial status. Unknown scope blocks unsafe comparisons. Metadata classifications remain hypotheses, checked against source in final semantic verification.

## Dependency-aware selection and rendering

Cross-element qualifications selected in the same verification batch retain their source evidence and create explicit portfolio dependencies. Parent findings and required qualifications consume the same real context budget; a parent cannot consume a slot without its available required evidence. Missing or oversized bundles remain omitted rather than receiving a free budget exemption.

Markdown table values retain their original row and required header. The ledger is built only from observed anchored findings; there is no invented Cartesian product of experiments, methods and metrics.

The answer-ordering model returns record/anchor IDs, never factual prose or reformatted values. Code renders original selected sentences and required value/qualification anchors. Invalid selections receive an exact-source fallback within the same output budget. A qualification already quoted in its parent bundle is not repeated just to count its separate record. Missing findings remain explicit. Every rendered claim still passes the existing semantic verifier, and all writer-visible original context remains returned.

This intentionally narrows the earlier free-synthesis experiment: concise source selection is preferred to unverified paraphrase. It prevents the demonstrated fabricated timing-range/mandatory-control behaviors by construction rather than relying only on the same model to notice them. Semantic relevance and extraction completeness are still not guaranteed.

## Compatibility and validation

The overall default remains `KB_ANALYTICAL_WRITER=extractive` pending a fresh accuracy benchmark. Factual queries retain their existing path. Public routes, the ten trace stages, index/source text/vectors, model restrictions, hard budgets and official evaluator are unchanged. No additional generative model or training is introduced.

- **217 non-slow tests passed; seven slow model tests deselected.** These include immutable/offset-stable IDs, repeated values, malicious optional fields, hard rejection of invented primary anchors, cross-document guards, source-owned rendered values, required qualifications, table headers, budgeted dependencies and a full mocked query through all ten stages.
- The integrated full-query test makes planning, source verification, answer ordering and final verification calls, with **no standalone ledger-extraction call**. This is a structural/mock check, not a live latency measurement.
- Replaying all 20 actual extraction rows from the previous full-document failure retains **20/20**, compared with **13/20** before. All seven numeric-format failures are recovered. Raw quotations and copied source values remain exact. The ID-contract replay explicitly maps the saved valid span references into immutable IDs; it does not claim that a new model run would select every correct ID.
- **Zero paid API calls and zero credit spent for this repair.** No new answer-accuracy/latency benchmark was run. The previous full-run 56.25% precision / 15.22% recall is historical evidence, not a score for this implementation.

Portable replay evidence: [diagnostic counts](diagnostics/source-id-fix/replay.json). Full source-containing replay artifacts remain local under `artifacts/source_id_fix/`.

## Remaining limits

A model can still omit relevant source IDs, assign an uncertain relationship, or classify background as relevant. Unknown scope cannot establish a verified comparison. Source-only rendering does not invent normative recommendations absent from the collection. Observed/selected ledger coverage is not exhaustive source recall or gold-cell recall. Schema-size/token behavior and live end-to-end quality need measurement before enabling the ledger by default.

## Fresh live benchmark

[Full query benchmark](diagnostics/source-id-full/REPORT.md): all 52 ledger records accepted with no validation warnings/rejections; no separate extraction call; analytical query 74.19s. Official analytical precision/recall were 0% / 100%, with all reference points matched and all answer points marked extra. This contradictory score is preserved and cannot establish an accuracy gain. The answer still exceeds useful length and leaves controls/monitoring unresolved. Total queries plus judging cost $0.02138573 computed. Default remains extractive.
