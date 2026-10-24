# C32 / C26 task worksheet development run

Measured corrected code: `88dae8d7b2b9ea5c5b8d9381126dbc5c342f9d2e`. Earlier implementation attempt: `ed7413e02c0583c60b10d43ca42cc0a62fca579b`. Baseline: `9eb518cc5047beecef89dc0248975480d542c88e`.

Qwen3.8 Flash with thinking disabled; independent GLM 5.3 Flash judge with low reasoning. Existing document indexes were reused, so new ingestion cost was zero. These are previously diagnosed development queries, not an untouched holdout. Original evaluator, reference data and PDFs are unchanged. Scores are the original official outputs; no regrading or correction was performed.

## All attempts

Metric order below: answer precision / answer recall / context precision / context recall.

### Original baseline

- **C26**: 11.76% / 25.00% / 97.14% / 106.25%. Query 47.95s; 35 returned chunks.
- **C32**: 0.00% / 0.00% / 0.00% / 0.00%. Query 12.97s; 0 returned chunks.

### Initial worksheet attempt

- **C32**: 33.33% / 28.57% / 0.00% / 0.00%. Query 51.50s; 3 returned chunks.
- **C26**: 0.00% / 0.00% / 0.00% / 0.00%. Query 21.40s; 0 returned chunks.

### Corrected scheduling attempt

- **C32**: 60.00% / 42.86% / 0.00% / 0.00%. Query 53.28s; 4 returned chunks.
- **C26**: 80.00% / 34.21% / 100.00% / 90.62%. Query 106.34s; 29 returned chunks.

## What changed and what the run shows

The implementation removes the inventory whitelist as a source of truth, builds query-anchored operations and source roles, retrieves independently for those roles, and produces a source-bound task worksheet in the writer call. Final checking separates factual support from operation completion. Factual questions can retain verified counterevidence/explanations and use up to two extra targeted verification batches. Exact-source repair requires a fresh semantic verdict and is limited to one call. See [implementation notes](../../next-iteration/IMPLEMENTATION.md).

The initial C26 attempt exposed a scheduling bug: its 17.6-second planner exceeded the previous 16.5-second cumulative verification cutoff, admitting zero evidence checks. Its all-zero scores are preserved above. The corrective pass changed verification to use the remaining original 30-second early-stage deadline; final-stage grace is unchanged. This is a corrective rerun, not an independent accuracy replicate. Both attempts are charged to one aggregate cap.

### C32 remaining coverage

Coverage counts: `{"candidate_pages": 43, "cards_surveyed": 0, "elements_retrieved": 105, "raw_candidate_pages": 9, "raw_fragments_verified": 32, "recovery_batches": 2, "verification_budget_omitted": 0, "verification_candidates": 105, "verification_remaining": 73}`.

- 32 source fragments verified; 73 remain unchecked (bounded verification)
- The query asks for a specific statistic (percentage increase) which is not present in the provided text.
- The provided evidence consists of FAQs explaining why such statistics cannot be forecasted or benchmarked generally.
- 1 unsupported or uncertain claims removed

The answer now explains why the requested percentage is not established and cites institution-specific factors and the agencies' inability to forecast the impact. The official context judge nevertheless labelled every explanatory fragment irrelevant, including the page-18 paragraph also used by the reference answer. The answer matcher credited three reference points. This is an observable mismatch between the two judge tasks, not grounds to replace the zero context scores. The reference's illustrative numerical example is still not supplied in the answer, and not all retrieved candidates were inspected.
### C26 remaining coverage

Coverage counts: `{"candidate_pages": 14, "cards_surveyed": 0, "elements_retrieved": 179, "raw_candidate_pages": 14, "raw_fragments_verified": 72, "recovery_batches": 0, "verification_budget_omitted": 107, "verification_candidates": 179, "verification_remaining": 107}`.

- Evidence verification budget exhausted
- 72 source fragments verified; 107 remain unchecked (bounded verification)
- 107 source fragments not verified within budget
- 3 unsupported or uncertain claims removed
- Requested topics not fully supported by final claims: Identify how the prediction target (daily direction) was formally defined and labeled in the study., Examine the data preparation steps and the strategy used for splitting training, validation, and testing sets., Evaluate the reported accuracy metrics and any statistical tests or cross-validation methods used to establish robustness.
- Some requested operations remain unresolved; see task worksheet

C26 improved answer precision substantially, but the system checked only 72 of 179 candidate fragments and publicly reports 107 unverified fragments. The final operation audit leaves target-definition, data-preparation/split and robustness tasks unresolved; only the generalisation task is marked complete. One failed finding formulation recovered its original source core and passed a separate check. Three original statements were rejected, including one marked background. These are remaining coverage and synthesis limitations, not a complete resolution of the original accuracy problem.

## Verification, cost and reproducibility

- Offline suite: **276 passed**, 7 slow tests deselected. Both attempts preserve ten trace stages with exactly four fields each.
- Actual aggregate cost, including the initial failed attempt and all judging: **$0.02322440**. Conservative charged upper bound: **$0.02803088**, under the **$0.10** aggregate admission cap.
- 41 provider calls in total; 0 failed calls. Unknown usage, if present, is charged conservatively by the driver. Prior-attempt charges are carried into admission for the corrective pass.
- Protected source/evaluator hashes and per-case cost, calls, omissions and judge flags are in [summary.json](summary.json). Full local response, writer context, worksheet, raw judge inputs/outputs and cost ledgers remain in the ignored artifact folders.
- Reproducer: [benchmark_task_worksheet.py](../../../scripts/benchmark_task_worksheet.py). It requires the original local corpus and existing indexes, uses CLI credentials only in memory, and refuses to overwrite an existing report. Use a fresh output directory; pass the prior cost ledger when continuing an attempt.
- Raw local folders: `artifacts/task_worksheet_20261024/` and `artifacts/task_worksheet_corrective_20261024/`.
- The 30-second setting remains a soft overall target because writer/checker completion has explicit grace. These measured latencies are not a claim of meeting a 30-second service target. Changing several components together does not establish which component caused a metric difference. No broad unseen-document accuracy claim follows from these two cases.

## Follow-up: dynamic selector removed

The LLM-driven next-batch selector was removed after a capped C32/C26 rerun showed that C26 stopped after its first eight-fragment tranche: 0.00% / 2.78% / 100.00% / 12.50%, 66.64 seconds, with 171 candidates left unchecked. On C32 the selector did make two follow-up choices, but returned 60.00% / 42.86% / 0.00% / 0.00% in 56.27 seconds.

A deterministic 12-fragment batch experiment also underperformed: C26 checked 36 fragments and scored 71.43% / 27.03% / 100.00% / 62.50%, versus the earlier eight-fragment static run's 80.00% / 34.21% / 100.00% / 90.62%. The 12-fragment change was discarded. With the original eight-fragment size restored, the latest C32 run scored 75.00% / 50.00% / 0.00% / 0.00% in 43.32 seconds. Its C26 run was refused before a provider request by the cumulative per-query $0.035 admission limit; the earlier static eight-fragment C26 result is therefore the best completed measurement for that configuration, not a fresh replicate.

The C32 context scores are zero because the official evaluator's context judge marked all three retrieved chunks irrelevant. One retrieved chunk contains the same page-18 "depends on many factors / cannot reasonably forecast" material as a gold chunk, and the answer judge credited that fact. Context scoring asks the judge about query relevance without showing it the gold chunks, so this is a judge inconsistency rather than evidence that retrieval returned no context. The original evaluator was left unchanged.

The latest cumulative billed upper bound across carried-forward runs is $0.06591522, below the $0.10 experiment cap. Raw artifacts for the follow-up runs remain in ignored local directories `artifacts/dynamic_selection_c32_c26_rerun_20261024/`, `artifacts/ranked_batches_c32_c26_20261024/`, and `artifacts/ranked_batches_8_c32_c26_20261024/`.
