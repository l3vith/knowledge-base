# Ledger: full single-document query benchmark

**The fresh full-pipeline ledger run regressed analytical recall. Keep the ledger off by default.**

Commit `4914234458c41f2f15c1352c27dc977e672a27b4`. One 24-page source document, `2012.07440v3.pdf`. Qwen3.8 Flash, thinking disabled. Existing enriched index reused without ingestion/model calls. Both questions ran fresh planning, routing, source retrieval, reranking, evidence verification, answer construction, final semantic verification and citation rendering. The analytical question additionally ran fresh ledger extraction and synthesis. No saved plans, ledger extraction, synthesis or writer evidence were replayed.

## Results

- **C31 factual:** **18.54s**, answer precision **100%**, recall **66.67%**, context precision/recall **100% / 100%**. One passage, one cited claim. Correct 60,000 paths and page-15 citation. The judge still marked page attribution missing despite its presence; official scores are preserved.
- **C18 analytical:** **102.51s**, answer precision **56.25%**, recall **15.22%**, context precision/recall **95.92% / 95.92%**. 107 candidate fragments verified; 49 writer-visible fragments returned; 13 final cited claims. Status **partial**. Both context ratios happen to be below 100% here, but the official count-based context-recall formula is unchanged.

The prior default full-query result was **20.00% precision / 34.04% recall at 66.48s**. Thus ledger precision rose while recall fell and latency increased. The earlier guarded saved-evidence result (**54.55% / 45.65%**) did not generalize to this fresh end-to-end pass. This is still one public development case with stochastic generation/judging, not held-out accuracy or a causal ablation.

## Failure isolated

The model emitted 20 extraction records; 13 passed and **seven failed `non_exact_value` validation**. Those seven included proxy accuracy, calibration accuracy, evaluation/calibration timings and a cost comparison. The actual rejection was numeric Markdown reformatting: for example, source `0 _._ 05%` became model output `0 . 05%`, and source `40 _,_ 000` became `40 , 000`. They were not exact substrings, so the guard correctly refused to call them exact source values, but the pipeline lost useful evidence instead of recovering a canonical source anchor.

The downstream writer therefore saw mostly construction-cost/qualification records. It explicitly reported missing accuracy and speed evidence even though those source passages existed earlier in the pipeline. The source-copy fallback cannot recover a record already rejected during extraction. Seven rejections should not be interpreted as seven hallucinated numerical values; this run's examples show formatting differences.

The next repair should make the extractor select precomputed value/span IDs so code copies original values, or use a tightly bounded reversible punctuation normalization to locate the original exact source substring. Do not broadly relax exact anchoring or accept paraphrased values. That repair was not applied/rebenchmarked during this benchmark-only request.

## Integrity and spend

Both responses retain the ten required trace stages. The official evaluator/benchmark were unchanged; protected-input check: **True**. Judge responses were capped at 2,000 tokens without changing official formulas/decomposition. Diagnostic query deadline was 180s, as in prior comparisons; production default remains 120s. The observed query times are not evidence that a production hard deadline is enforced.

Total cost including both queries and judging: **$0.01536447 computed**, **$0.01844757 conservative upper bound**, below the shared **$0.05** ceiling. 30 paid requests; 0 thinking blocks. No inference retries or extra rejudges.

Default `KB_ANALYTICAL_WRITER` remains **extractive**. The ledger experiment is available behind its switch but should not be promoted on these results. Full local artifacts are under `artifacts/single_document_ledger_full/`; [portable results](summary.json) omit raw gold answers and full source chunks.
