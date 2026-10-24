# Three previously unbenchmarked documents: first-pass results

**Results remain well below the required quality targets.** All four queries completed and were scored; no successful-only selection, replacement documents or score-driven reruns were used.

Measured code: `9eb518cc5047beecef89dc0248975480d542c88e`. Answers: Qwen3.8 Flash with thinking disabled. Judge: GLM 5.3 Flash with low reasoning effort. Each document was indexed from scratch into its own collection, with ingestion caches disabled, automatic metadata, local embeddings/reranker and real Langfuse query traces. No answer/context replay. Core code stayed unchanged during the run.

## Document-level metrics

Bhadora is the arithmetic mean of its two selected queries; the other documents each have one. These are raw official formulas/GLM judgments.

| Document | Queries | Answer precision | Answer recall | Context precision | Context recall |
|---|---|---:|---:|---:|---:|
| 10.1515_econ-2022-0073 (1).pdf | C26 | 11.76% | 25.00% | 97.14% | 106.25% |
| Bhadora Industries_Annual Report.pdf | A20, A21 | 31.87% | 16.47% | 92.00% | 43.46% |
| FDIC FAQ.pdf | C32 | 0.00% | 0.00% | 0.00% | 0.00% |

## Each query

| Query | Answer precision | Answer recall | Context precision | Context recall | Query seconds | Returned passages |
|---|---:|---:|---:|---:|---:|---:|
| C26 | 11.76% | 25.00% | 97.14% | 106.25% | 47.95 | 35 |
| A20 | 52.63% | 30.91% | 100.00% | 60.00% | 68.79 | 36 |
| A21 | 11.11% | 2.04% | 84.00% | 26.92% | 46.02 | 25 |
| C32 | 0.00% | 0.00% | 0.00% | 0.00% | 12.97 | 0 |

**Context recall may exceed 100%** because the organizer formula divides relevant returned-fragment counts by reference-fragment counts. C26 is 34 relevant returned fragments / 32 reference fragments = 106.25%; this does not establish complete semantic coverage. No score was clamped or corrected.

## Scope and selection

The cohort was frozen before indexing/scoring, based on available run history and the presence of self-contained benchmark questions, not predicted scores. A local scan found prior C18/C31 tests of `2012.07440v3.pdf`; the user's teammate report also established Heston/C17 and Basel/B30 testing, so those were excluded. The selected documents are new to the available benchmark history. Earlier dataset/planning inspections mean this is not a certified untouched or hidden holdout.

All single-document benchmark questions for these three sources were selected: ETF paper C26; Bhadora A20 and A21; FDIC FAQ C32. Questions requiring additional documents were excluded to avoid evaluating an incomplete source collection.

- **C26** — A business line wants to use the published neural-network classifier for predicting daily direction of emerging-market equity ETFs as a trading signal. What would a model validator flag about how the target was defined, how the data were prepared and split, the robustness of the reported accuracy, and how far the results can be generalised?
- **A20** — Bhadora Industries listed on the SME platform after a year of rapid growth. From a lender's perspective, how is that growth being financed and what do the quality of its receivables and working capital look like?
- **A21** — How reliable is the financial information Bhadora Industries gives its lenders and shareholders? Look for internal inconsistencies across the directors' report, auditor annexures and the notes.
- **C32** — According to the FDIC, by what percentage did US community banks' loan-loss allowances increase on the day they adopted the lifetime expected-loss standard?

## Observed failures

- **C26:** 179 source fragments checked, 35 writer-context passages returned, but answer precision/recall only 11.76% / 25%. The run had 15 draft-statement rejections and seven unaccepted final claims. The judge also dropped citation details and marked existing citation attribution missing; the diagnostics preserve that issue without replacing official scores.
- **A20:** 125 fragments checked, 36 passages returned. Precision 52.63% with recall 30.91% means much reference content was still absent. The pipeline rejected 33 draft statements and 12 final claims. Citation decomposition was flagged.
- **A21:** 61 fragments checked, 25 passages returned; answer recall only 2.04%. Context recall 26.92% also indicates weak retrieval by the official count-based measure. No judge-consistency flag excuses this score.
- **C32:** correctly routed to the FAQ and retrieved 72 candidate elements. The narrow factual path checked only 16 fragments, kept none, and left 56 candidates unchecked. It returned `no_answer` with zero passages, producing zeros on all four metrics. This is a bounded verification failure, not proof the requested information is absent from the full document. The unchecked count is visible in the trace; the public coverage limitations did not surface it.

These results do not establish that the original-document fixes generalize. They are not used here to tune the system or rerun the cohort. No implementation was changed during this test.

## Ingestion, cost and integrity

| Document | Pages | Cold index seconds | OCR pages |
|---|---:|---:|---:|
| 10.1515_econ-2022-0073 (1).pdf | 14 | 11.57 | 0 |
| Bhadora Industries_Annual Report.pdf | 89 | 33.30 | 1 |
| FDIC FAQ.pdf | 43 | 14.71 | 0 |

Known reported-token/catalog API cost **$0.05324337**; conservative upper bound **$0.06412013**, under the **$0.20 total cap**. Includes three document-card calls, all query generation/checking and 14 GLM judge calls. 86 total requests, zero failed requests. No unknown billed attempts in this run. Local parsing, OCR, embeddings and reranking incurred no API calls. These are calculated costs, not a billing receipt.

All four responses retain ten trace stages, each with exactly the four required fields. Original PDFs, benchmark and evaluator hashes remained unchanged. The 30-second setting bounds early query stages but final generation has grace, so measured query wall times can exceed 30 seconds. Ingestion and judging are excluded from the reported query times.

Full local evidence: `artifacts/three_unseen_20261024/`. [Portable summary](summary.json) includes the selected queries, source hashes, exact metrics, timings, trace IDs, limitations and audit flags; it omits raw reference answers and full source chunks.
