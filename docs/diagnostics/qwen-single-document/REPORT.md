# Qwen single-document benchmark

**Outcome: factual answer works; analytical request reaches the end but yields no usable answer.** No token-budget, transport or JSON failures occurred. This is a two-question public development smoke on one reused 24-page document, not held-out accuracy or a full-corpus result.

Model: `qwen3.8-flash`; thinking disabled; local page selection; commit `909ae3d934bf6dc81021af5e9e50f9f904e12fb0`. No indexing calls. The five-cent ceiling includes judging. Query deadline was 180 seconds, matching previous single-document runs; production defaults to 120 seconds, so analytical latency remains a deployment concern.

## C31

Question: How many Monte Carlo paths did the rough Bergomi pricing routine use to generate prices in the Chebyshev-tensor calibration study?

Status **answered**; latency **19.13s** (query wall time including trace flush, excluding judging); returned passages **1**.

Query usage: 4 calls, 3,508 input and 740 output tokens; cost **$0.00087400**. Judging cost **$0.00025205**.

Raw official metrics: answer precision **0.6667**, answer recall **0.6667**, context precision **1.0000**, context recall **1.0000**.

Returned answer:

The rough Bergomi pricing routine used 60,000 Monte Carlo paths to generate prices in the Chebyshev-tensor calibration study. [2012.07440v3.pdf p15]

The answer correctly renders **60,000 paths**, cites physical page 15 and returns one supporting passage. The first baseline took 82.75 seconds; the subsequent DeepSeek run took 36.23 seconds. This Qwen run took 19.13 seconds. The judge matched two of three decomposed points; its decomposition distinguishes wording about prices generated in tests from prices generated in the calibration study. The required 0.95 answer metrics are not met.

## C18

Question: Bank supervisors' model-risk expectations stress conceptual soundness, ongoing monitoring, outcomes analysis and care when a model is used outside its original purpose. Apply that lens to a desk that wants to calibrate a rough-volatility model daily by replacing its slow Monte Carlo pricer with a fast polynomial surrogate built offline: what evidence does the research offer on accuracy, speed and build cost, and what controls and limitations would you insist on before production use?

Status **partial**; latency **120.36s** (query wall time including trace flush, excluding judging); returned passages **26**.

Query usage: 17 calls, 33,611 input and 7,050 output tokens; cost **$0.00835515**. Judging cost **$0.00131715**.

Raw official metrics: answer precision **0.0000**, answer recall **0.0000**, context precision **0.9231**, context recall **0.4898**.

Returned answer:

No supporting information was found within the searched collection scope.

All **10** generated claims had empty `aspect_ids`; therefore all failed the nonempty obligation-support requirement. **Three** also contained at least one quote that was not an exact source substring, including paraphrasing/ellipsis. Source element IDs themselves were valid. These checks must not be disabled to force a nonempty answer.

The pipeline returned the generic abstention text with `partial` status because writer context existed but no draft claims survived. Its generic wording is misleading here: supporting technical evidence was retrieved, and generation/validation failed. No LLM final claim-check call ran because there were no accepted draft claims. Reaching the final pipeline stages is not a successful analytical answer.

The local path retrieved and verified **114** candidates across **15 sequential verification calls**; **70** were retained, **26** supplied to the writer, **44** omitted by the context budget. Evidence verification took **82.16s** and draft generation **25.66s**. Token usage fell from **21,118** completion tokens in the last failed DeepSeek attempt to **7,050**, but latency remains high. The evidence portfolio is still broad and should select complementary facts rather than repeatedly rewarding the same obligations.

## Integrity and next work

Total known reported-token/catalog cost: **$0.01079835**; conservative admission ledger **$0.01291260**, below $0.05. All **28** paid calls used Qwen3.8 Flash; **0** failed responses and **0** returned thinking blocks. Original benchmark and evaluator hashes unchanged: **True**.

Fix generation to require valid nonempty obligation IDs and select source-span IDs rather than reproducing long quotations. Permit at most one bounded repair of invalid claims, using the same already supplied evidence and reserved budget. Keep final semantic verification and exact-source checks. Distinguish generation failure from corpus absence in status/message. Reduce redundant analytical evidence and sequential model calls before rerunning. No repair or second paid benchmark was performed in this turn.

The official context recall is the supplied relevant-chunk count ratio, not a semantic gold-coverage estimate. Metrics are reported as returned, without citation stripping or evaluator changes.

Raw results: `report.json`, `C31-response.json`, `C18-response.json`, `cost-ledger.json`, and private per-query artifacts under `query_runs/`.

Portable evidence is checked in alongside this report in `summary.json` and `analytical-draft-validation.json`. The raw files listed above remain local under the ignored `artifacts/single_document_qwen/` folder and are not part of a fresh clone. No credentials, auth export, raw source PDFs, gold benchmark dataset or private full writer contexts are included in this diagnostics directory.
