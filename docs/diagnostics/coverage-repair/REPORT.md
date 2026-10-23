# Analytical coverage repair: measured results

One 24-page document, two public development questions. Qwen3.8 Flash, thinking disabled. Existing index reused. Official evaluator and gold inputs unchanged. Diagnostic query deadline 180 seconds; production default remains 120 seconds.

## Final measured configuration

- Factual C31: **19.06 seconds**; answer precision **100%**, recall **66.67%**; context precision/recall **100% / 100%**; one returned passage. It correctly answers 60,000 paths and includes the page-15 citation. The judge nevertheless counts the page-attribution point as missing; the separate audit flags this without altering the score.
- Analytical C18: **66.48 seconds**; answer precision **20%**, recall **34.04%**; context precision **100%**, official context-recall count ratio **104.08%**; 51 writer-context fragments, 12 final cited claims, 6,062 answer characters. Status is **partial**, with ongoing monitoring and controls unresolved.

The official context-recall formula is a relevant-returned-fragment count divided by benchmark-fragment count, so it can exceed 100%. It is not exhaustive semantic recall. All writer-visible context remains returned; unused context is not hidden to improve scores.

The immediately preceding benchmark had factual 16.60s / 50% precision / 66.67% recall and analytical 43.32s / 0% precision / 21.74% recall. The factual answer remains identical across these judging passes, demonstrating score instability. Analytical precision and recall improved over that run but remain poor. Speed is slower than 43.32s, while still faster than the older 118.22s result. These comparisons combine changes in code and model outputs; they do not isolate one feature's effect.

## First repair attempt retained

The first repair overcorrected: analytical output took **139.11 seconds**, had 41 cited claims / 18,728 characters, and scored **2.97% answer precision / 68.18% recall**. Context precision was 98.11%; the official context-recall count ratio was 106.12%. The high matched-point count alongside nearly all answer points labelled extra is flagged for review. This result is preserved rather than replaced silently.

A local-only replay then applied the output bound to saved selections: 47 selections reduced to 18 / 7,943 source characters with no API calls. The follow-up live run selected only 13 draft passages within the bound; one was rejected by the final semantic check. The output bound did not discard further selections in that live run. Only the analytical query was repeated; factual query execution was not repeated.

## Evaluation completion and cost

The follow-up's first judging attempt completed three requests, then the conservative budget guard refused the last request because of its 10,000-token response allowance. No over-budget request was sent. A judge-only completion used a 2,000-token response ceiling, the same unchanged official evaluator, no query rerun and no inference retries. The incomplete judge's cost is included below. The judge-only completion necessarily repeated the three earlier judge calls because their outputs had not been persisted; completion outputs are now saved locally. No additional rejudging was performed after completion.

**All repair attempts and judging combined: $0.03678748 computed cost; $0.04444388 conservative upper bound**, below the aggregate **$0.05** ceiling. 51 paid requests; 0 thinking blocks. Protected benchmark and evaluator inputs unchanged: True.

## Shipped changes and limits

Broad analytical metadata boosts ranking without narrowing the source search. Literal requested topics get independent source-page matches. Direct findings and qualifications are distinguished from background. An exact-source writer uses topic coverage and bounded output; final semantic verification checks completeness separately from support. Missing checks fail closed. Decimal formatting is repaired only in display text; raw source quotations remain exact. A separate zero-call judge audit flags contradictions without modifying official scores.

**183 tests passed; seven slow model tests deselected.** The changes do not establish winning accuracy. Important analytical details remain omitted and other material is still scored extra. Generic checklist recognition is heuristic, evidence verification remains model-dependent, and a one-document collection cannot supply missing policy documents. Further selection/relevance work and held-out evaluation are required before submission readiness can be claimed.

See [machine-readable results](summary.json) and [implementation notes](../../ANALYTICAL_COVERAGE_REPAIR.md). Full private source/context artifacts remain local under `artifacts/single_document_coverage_repair/` and `artifacts/single_document_coverage_bounded/`.
