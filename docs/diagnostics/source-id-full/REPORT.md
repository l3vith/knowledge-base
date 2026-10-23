# Source-ID ledger: fresh single-document benchmark

The source-ID fix removed the observed extraction-format failures, but this run does not establish an answer-accuracy improvement. Keep the ledger experimental and off by default.

Measured implementation: `58cf205db9aa23496ce4d46b5287c439fb6e4f05`. Document: `2012.07440v3.pdf`, 24 pages. Qwen3.8 Flash with thinking disabled. Existing enriched index reused; both queries ran fresh planning, retrieval, verification, answer construction and final checking. No saved model outputs were replayed. This is two public development questions on one document, not held-out accuracy.

## Official results

- **C31 factual:** 17.58 seconds; answer precision **50%**, recall **40%**; context precision/recall **100% / 100%**. One passage. The answer correctly states **60,000 paths**, with the page-15 citation.
- **C18 analytical:** 74.19 seconds; answer precision **0%**, recall **100%**; context precision **96.15%**, context recall **102.04%**. 52 returned fragments, status **partial**; final answer 7,939 characters.

Preserve these raw scores, but do not interpret the analytical result as perfect coverage or completely wrong content: the judge marked all **48** reference points matched while simultaneously marking all **77** answer points extra. The diagnostic audit flags this contradictory matching. It does not compute a replacement score. Context recall exceeds 100% because the official evaluator divides a relevant-returned-fragment count by a reference-fragment count; it is not bounded semantic recall.

The factual answer is byte-identical to the preceding full-ledger run, which received 100% precision / 66.67% recall. This judge decomposed the reference into five points and marked document/page attribution missing despite the citation in the answer. The raw score is retained, without rejudging.

## What the fix achieved

All **52 ledger records** passed source-ID validation, with **zero rejections and zero warnings**. The separate paid `ledger_extract` call is absent. Source-owned rendering retained calibration/build/timing numbers, including under-5-minute and under-8-minute builds as separate passages, rather than rejecting numeric Markdown formatting. This confirms the previous failure mechanism is addressed in this run; it does not prove every useful finding was retrieved or selected.

Analytical latency fell from **102.51 seconds to 74.19 seconds** (about 28%). This is a single-run comparison with changed retrieval/model outputs, not an isolated causal speed measurement. Analytical query used 16 paid calls; factual used four.

## Remaining problems

- The source ledger contains 19,586 quoted characters, exceeding the 8,000-character answer budget. **32 selected records were omitted at rendering; 33 were absent after final semantic verification.** A valid ledger does not ensure a useful final answer.
- Five attempted selections mixed unresolved scopes and were repaired or limited. One unsupported/uncertain claim was removed.
- The answer remains long and repetitive. Background, figure captions and overlapping findings consume space that should serve required evidence and qualifications.
- Conceptual soundness, ongoing monitoring, outside-original-purpose use and controls remain unresolved. Pure source copying cannot supply clearly labeled analytical recommendations absent from the source.
- The official matching output is inconsistent. Score comparisons on this development example cannot establish a reliable improvement without examining evaluator behavior and broader untouched cases.

Next work should prioritize a compact, topic-balanced selection of distinct findings with their qualifications, and a separately checked analytical layer for requested recommendations. Do not enlarge output budgets or weaken source anchoring to conceal omissions. The production default remains `extractive`.

## Integrity and cost

Both responses retain all ten public trace steps. Protected organizer benchmark/evaluator hashes stayed unchanged. Index reuse incurred zero ingestion/model calls. Diagnostic deadline was 180 seconds; production default remains 120 seconds. Query times exclude judging and ingestion.

Total including judging: **$0.02138573 computed**, **$0.02618483 conservative upper bound**, below the aggregate $0.05 cap. 28 paid requests, zero returned thinking blocks, no inference retries or repeated judges. These are reported-token/catalog calculations, not a billing receipt.

Full local evidence: `artifacts/single_document_source_ids/`. [Portable summary](summary.json) excludes raw gold answers and full source chunks. No inference code was changed during this benchmark.
