# Major issues: Smart Knowledge Base repair handoff

**Current status after the repair rerun:** factual scores are now 100% on this one case; analytical output now contains 18 verified claims, but its precision is only 25.93%. Sections describing zero claims/66.7% factual scores are historical baseline evidence. Read the final “Latest live repair result” section and its report first; analytical over-inclusion, latency and deployment/accounting gaps remain open.

This is a self-contained handoff for the next agent. The benchmark details below are the historical Qwen baseline at `909ae3d`; subsequent source-selection repairs are described in the implementation update at the end. **Historical baseline only:** that earlier analytical response had no accepted claims and zero answer quality; the earlier factual response missed the required metrics. The latest live repair result supersedes those outcomes but still has poor analytical precision.

## 1. Project, current branch and scope

- Repository: `git@github.com:l3vith/knowledge-base.git`.
- The implementation evaluated here is commit **`909ae3d934bf6dc81021af5e9e50f9f904e12fb0`**, pushed to both `main` and `track-b`. This handoff is a later documentation commit. Check the current branch and remote before editing; another teammate contributes foundation/ingestion/deployment work.
- Current development machine: macOS, repo at `/Users/smit/Downloads/Hackathon/knowledge-base`. Python **3.12** environment: `.venv312/bin/python`. Relative commands below run from the repository root. Python 3.13 is unsuitable for the installed OCR dependency path. A fresh clone needs its own environment and organizer input files.
- User authorized fixing the project and pushing code to GitHub. Their remaining OpenCode budget is limited: the original allocation was **$10 including the demo**. Do not infer the current remaining balance from this document.
- Active model: **`qwen3.8-flash` with thinking disabled**. Do not revert to reasoning-heavy DeepSeek or select a more expensive model without user authorization.
- Latest work did **not** change the benchmark, original evaluator notebook or gold answers. This handoff requests repairs; none of the remaining issues below should be described as fixed merely because tests pass.
- This repository implements a retrieval/answer system, not a newly trained foundation model. No training or fine-tuning was performed.

Read [README.md](README.md), [docs/QWEN_LOCAL_INFERENCE.md](docs/QWEN_LOCAL_INFERENCE.md), [docs/BENCHMARK_FIX_PLAN.md](docs/BENCHMARK_FIX_PLAN.md), and [docs/unified-plan/COMPLIANCE.md](docs/unified-plan/COMPLIANCE.md). The unified plan is a specification/history reference; current source and measured artifacts determine what actually runs.

## 2. Evidence available in a fresh GitHub clone

The `artifacts/` and `data/` directories are ignored. Do not assume that a GitHub checkout contains the development machine's corpus, active collection, full writer context, cached models, credentials or custom benchmark driver.

Portable diagnostics committed with this handoff:

- [Benchmark report](docs/diagnostics/qwen-single-document/REPORT.md): measured behavior and limitations.
- [Machine-readable summary](docs/diagnostics/qwen-single-document/summary.json): exact questions, returned answers, official metrics, coverage, usage, stage traces and analytical call counts. It contains **no raw source chunks or gold answers**.
- [Analytical draft validation](docs/diagnostics/qwen-single-document/analytical-draft-validation.json): the ten generated claims, empty obligation IDs, evidence IDs and exact-quote validation flags. Full source quotations are omitted.

Full local evidence, if working on the same machine:

- `artifacts/single_document_qwen/report.json`, `REPORT.md`, `cost-ledger.json`.
- `artifacts/single_document_qwen/C31-response.json` and `C18-response.json`.
- `artifacts/single_document_qwen/query_runs/req_96647f6b5e974c1ebd193a23522c27ec/`: factual call inputs, outputs and attempt ledger.
- `artifacts/single_document_qwen/query_runs/req_30bc06870d0449c4a7df0f23843f691a/`: analytical call inputs, outputs, writer context and attempt ledger. `call_17_input.json`/`call_17_output.json` are the analytical writer request/response.
- Previous attempts: `artifacts/single_document/` is the original DeepSeek baseline; `artifacts/single_document_rerun/` is the later DeepSeek attempt that exhausted finishing tokens.

These diagnostics describe public development cases. They must **never** be imported into runtime retrieval, indexed as source, used as an answer cache, or used to hardcode document/question IDs. New regression tests should normally reproduce the failure with synthetic source text.

**Reporting correction:** the analytical Qwen run used **15**, not 14, sequential evidence-verification calls. Some earlier local notes said 14. The attempt ledger is authoritative: 1 planning + 15 verification + 1 drafting = 17 calls. There was no final semantic verifier call because all draft claims had already been rejected.

## 3. What the latest one-document benchmark actually measured

Document: **`2012.07440v3.pdf`**, 24 physical pages, source SHA-256 `dfbea8f46eb77a10d21bde81e6986d65856ae35ba9752c722f6fb176dc225dc3`. Existing collection: `single_doc_smoke`. Reused indexing; no ingestion calls during the run. Legacy source `doc_id` is `ad8116cccf`, which is diagnostic metadata only, not a valid runtime constant to special-case.

Exactly two public questions were run once with Qwen, local page selection and no model thinking. This is **not held-out or whole-corpus accuracy**. The measured query wall times include tracing/flush overhead but exclude the separate judge calls. The custom diagnostic driver used a **180-second query deadline**; production defaults to 120 seconds.

### Factual question C31

> How many Monte Carlo paths did the rough Bergomi pricing routine use to generate prices in the Chebyshev-tensor calibration study?

Returned answer:

> The rough Bergomi pricing routine used 60,000 Monte Carlo paths to generate prices in the Chebyshev-tensor calibration study. [2012.07440v3.pdf p15]

- Status `answered`; **19.1277 seconds**.
- One returned source passage, physical page 15. Eight candidates semantically verified out of 56 locally retrieved; no paid page survey.
- Four query model calls: plan, evidence verification, answer, answer verification.
- Query usage: **3,508 input / 740 output tokens**; query cost **$0.00087400**.
- Official answer precision **0.6666667**, answer recall **0.6666667**, context precision **1.0**, context recall **1.0**.
- The answer contains the correct numeric fact, but it does **not** meet the problem's 0.95 answer-metric targets.

### Analytical question C18

> Bank supervisors' model-risk expectations stress conceptual soundness, ongoing monitoring, outcomes analysis and care when a model is used outside its original purpose. Apply that lens to a desk that wants to calibrate a rough-volatility model daily by replacing its slow Monte Carlo pricer with a fast polynomial surrogate built offline: what evidence does the research offer on accuracy, speed and build cost, and what controls and limitations would you insist on before production use?

Returned answer:

> No supporting information was found within the searched collection scope.

- Status `partial`; **120.3565 seconds**; 26 writer-context passages returned.
- **114** candidates verified in **15** sequential model calls; **70** retained; **26** supplied to the writer; **44** omitted from writer context by its budget.
- Writer emitted **10** claims. **All 10 had `aspect_ids: []`**. All were rejected. **Three claims also had at least one non-exact quotation.** Evidence IDs themselves existed.
- No final semantic claim-check model call ran: `verify_answer()` skipped because there were no surviving claims. Completion of the ten pipeline stages is not evidence that an analytical answer was verified.
- Official answer precision **0.0**, answer recall **0.0**, context precision **0.9230769**, context recall **0.4897959**.
- Query usage: **33,611 input / 7,050 output tokens**, **17 calls**, query cost **$0.00835515**.
- Stage times: planning **9.70s**, local triage **2.36s**, evidence verification **82.16s**, drafting **25.66s**. Local candidate/page work itself was negligible.

Combined run including official judging: **28 paid calls**, known reported-token/catalog cost **$0.01079835**, conservative admission ledger **$0.01291260**, below the run's **$0.05** cap. No failed JSON/transport responses, token-budget exceptions or returned thinking blocks. The original protected input hashes stayed unchanged.

The report's machine status `completed` means the driver finished and collected metrics for both rows. It does **not** mean both answers succeeded.

## 4. P0 — Analytical claim schema is not followed

**Observed defect.** In `kb/query/answer.py::generate_answer()`, a claim needs valid nonempty `aspect_ids` drawn from the query's obligations. Qwen produced ten claims with empty arrays, even when the quotes and evidence IDs were otherwise valid. All ten are dropped. This alone explains the zero analytical answer score.

The writer prompt sketches `aspect_ids` but does not strongly enforce a nonempty enum of the actual allowed IDs. `kb/model_api.py::request_spec()` asks for valid JSON but does not supply a schema that enforces these fields. Valid JSON is not sufficient schema compliance. Do not assume that other models will obey the example automatically.

Relevant code:

- `kb/query/answer.py`: `ANSWER_SYSTEM`, `evidence_block()`, `generate_answer()`.
- `kb/query/types.py`: `Aspect`, `Claim`, `AnswerDraft`.
- `kb/model_api.py`: Messages request construction.
- `kb/query/pipeline.py`: writer and verifier stage integration.

Repair direction:

1. Tell the writer exactly which obligation IDs are allowed and require a nonempty mapping for each factual claim. Source rows currently call these `obligation_ids`, while output calls them `aspect_ids`; make the correspondence explicit.
2. Evaluate native structured output/schema support on this exact OpenCode/Qwen route rather than assuming upstream SDK syntax works. Keep a validated prompt-only path if the gateway cannot enforce it.
3. Consider one bounded schema-repair call using the same evidence, provided its tokens/cost are reserved beforehand. No new retrieval or open-ended retry loop.
4. Deterministic inference of missing mappings is acceptable only when unambiguous and source-grounded; never attach every obligation to every claim to make coverage appear complete.
5. Record per-claim rejection reasons instead of only the aggregate `invalid source support` count.

Acceptance: synthetic and recorded-shape regressions cover missing/empty/unknown mappings. The real analytical smoke must yield supported, cited technical claims; relevant claims must pass semantic verification. Missing governance evidence remains explicitly unresolved rather than invalidating every supported technical fact.

## 5. P0 — Writer quotations are fragile and some are not exact

**Observed defect.** Three of the ten analytical draft claims contained a quote that failed exact substring matching. The writer sometimes combined sentences, paraphrased punctuation or inserted `...`. For example, the first claim's E3 quote included an ellipsis joining source sentences. Exact quotation checks correctly rejected it.

The evidence selector already uses deterministic `S1`, `S2`, ... source-span IDs, reconstructing exact source text in code. The **writer still has to reproduce free-text quotations**, reintroducing the same failure class downstream.

Relevant code: `kb/query/screen.py::verify_elements()`, `kb/query/utils.py::support_spans()`, `fragment()`, `quote_valid()`, and `kb/query/answer.py::generate_answer()`/`verify_answer()`.

Repair direction: provide the writer with stable evidence/span identifiers and have it select support IDs; reconstruct immutable quotations locally. Preserve the complete necessary source context and source offsets. If output contains an invalid ID, reject/repair it within a fixed budget. A quotation with an ellipsis is not an exact source quote.

Acceptance: quotes round-trip to the original source even with mathematical markup, Unicode, escaped backslashes, tables and repeated text. Test nested fragment offsets and distinct occurrences. Do not accept approximate matches as exact evidence, mutate raw evidence, or silently manufacture quotations.

## 6. P0 — Generation failure is presented as corpus absence

**Observed defect.** The analytical response says no supporting information was found even though 70 source fragments were retained and 26 were shown to the writer. This misdiagnoses a generation/validation failure as missing corpus support.

`kb/query/answer.py::render_verified()` returns `ABSTAIN_TEXT` whenever no claims remain. `kb/query/pipeline.py` selects `partial` when writer context exists but the claim set is empty. The public API combines a plausible partial status with a misleading no-information message.

Acceptance: distinguish actual retrieval absence, exhausted search budget, provider/schema failure, all claims rejected, unsupported requested scope and a valid partial answer. Preserve the public contract/trace shape; use structured coverage/error fields and truthful wording. Do not leak credentials or private source data in errors. When part of the question has usable source support, preserve verified supported claims and disclose the rest.

## 7. P1 — Factual answer metrics are still below target

**Observed result, with judge interpretation uncertainty.** The latest factual answer has the correct 60,000-path value and correct page, yet official answer precision and recall are both 2/3. Context metrics are 1.0. The current judge split the answer/reference into points about the path count, generation of prices in the tests and the page citation. It matched the number and citation, but treated wording about the calibration study as an extra/missing-point distinction.

Earlier runs showed different decompositions: the original DeepSeek answer had answer precision 1/3 and recall 1; another DeepSeek run copied `60 _,_ 000` and scored recall 1/3. These are LLM-judge point decompositions, not stable independent human truth labels. Do not claim the metric shortfall proves the numeric answer is wrong, and do not claim the score should be ignored.

Factual work to do:

- Keep the answer minimal and source-faithful, including the distinction between which routine generated which prices and in what experiment. Avoid additional claims that the question does not require.
- Preserve required filename/page citations and all writer-visible context. Do not strip citations for scoring or inflate chunks to manipulate count metrics.
- Normalize only unambiguous extraction markup for displayed numeric claims. The original PDF text contains `60 _,_ 000`; the latest Qwen answer rendered 60,000 correctly, but there is no general deterministic normalization guarantee. Preserve exact raw source/quotes and units; do not conflate decimal commas, signs, ranges or different entities/periods.
- Investigate judge wording/decomposition with a fixed development protocol and report raw outputs. Do not repeatedly pay for judging until a lucky score occurs, rewrite the evaluator, copy a reference answer into serving code, or hardcode this fact/question.

Acceptance: factual output is correct, minimal, grounded and well formatted on varied synthetic formatting/identity cases and an agreed development set. Report all four official metrics honestly against the stated 0.95 targets; two examples cannot establish general performance.

## 8. P1 — Analytical over-retrieval, redundant context and serial latency

**Observed defect.** Reaching the end of the query now consumes fewer tokens, but requires 15 sequential evidence checks and about two minutes on one 24-page PDF. Retaining 70 passages for two broad obligations and sending 26 to the writer is excessive for a concise analytical answer. The writer still misses the expected answer because schema/selection problems remain.

Relevant code:

- `kb/query/candidates.py`: `candidate_pages()`, `element_retrieval()`, per-aspect lexical nets, dense/lexical fusion.
- `kb/query/triage.py::element_triage()`: local cross-encoder and obligation-fair ordering.
- `kb/query/screen.py::verify_elements()`: batches of at most eight; every prepared analytical candidate is attempted until bounds stop the loop.
- `kb/query/answer.py::select_portfolio()`: greedy gain remains positive for another passage on an already-covered aspect; it keeps filling the budget. Numeric dedup applies only to a qualified narrow factoid.
- `kb/query/settings.py`: finite caps and conservative byte budgets.

Repair direction:

1. Select complementary evidence per obligation/fact, not merely many relevant passages on the same topic. Preserve conflicting values, periods, exceptions, tables and source dependencies.
2. Use the existing local reranker and source structure to prioritize the strongest evidence before paid semantic checking. A relevance score is navigation, not proof of support.
3. Define sufficiency and marginal-evidence stopping criteria. Keep a bounded reserve for unresolved obligations from the initial retrieval pool; no open-ended repair retrieval.
4. Re-evaluate batch sizing now that reasoning is disabled. Fourteen/eight-item reasoning-era rules should not be blindly retained; use actual source size and expected output. The measured count here was **15 calls**.
5. If adding limited concurrency, enforce total request/credit/deadline limits and deterministic result identity. Do not multiply concurrency just to hide work or lose failed-call accounting.
6. Reduce context before drafting using evidence novelty/coverage, with full actual writer context returned. Do not hide unused writer evidence afterward to make precision look better.

The `raw_token_budget_analytical=16000` budget uses conservative UTF-8 byte units, **not 16,000 actual tokenizer tokens**. The current portfolio omitted 44 verified fragments. Raising that constant alone is not a principled coverage or cost fix.

Acceptance: fewer paid checks, less duplicate context and a shorter real analytical response time, while retaining needed benchmark-supported facts and honest coverage limitations. Validate quality as well as speed. Do not remove semantic verification solely to pass latency.

## 9. P1 — Deadline margin and meaningful analytical scope

The custom benchmark allowed 180 seconds. Production `QuerySettings.query_deadline_s` is 120. The measured analytical wall time was 120.36 seconds; internal stage completion was close to that boundary. Do not claim production would definitely fail from wall time alone (flush adds overhead), but there is no useful safety margin, and the benchmark is not evidence of a successful production-default HTTP request.

The two planned analytical obligations were roughly (a) technical accuracy/speed/build-cost evidence and (b) governance/controls/limitations. The source is a research paper, not a bank-supervisor policy corpus. The writer correctly noticed that formal supervisory frameworks were absent. That does not justify losing all supported technical content.

Acceptance: test the real configured deadline through `POST /query`; do not quietly increase it to hide inefficiency. Separate source-supported technical findings, unavailable formal governance evidence, and clearly labeled recommendations derived from supported limitations where the answer contract permits them. Do not invent regulations or use outside/web facts at query time to fill missing corpus material.

## 10. P1 — Serving auth, credit controls and accounting need deployment validation

These are confirmed code/configuration limitations and validation gaps, distinct from the measured claim bugs:

- On the development machine at handoff, `get_settings().opencode_api_key` is **empty**. The OpenCode CLI is authenticated, and custom diagnostic scripts used its active credential **only in process memory**, plus the provider's required organization header. A successful diagnostic call is **not proof that the normal server is authenticated**. `legacy_bind()` uses the shared client, which expects an organizer key in configuration. Either provision the authorized key through the established environment path or implement a narrowly scoped authorized CLI-auth adapter; do not commit/print auth exports or assume CLI login automatically configures the API server.
- `kb/llm.py::spent_usd()` checks recorded historical spend before a call and caches totals per process. It does not atomically reserve the next call's maximum cost across requests/processes. A call can overshoot the stated `KB_BUDGET_USD`, and independent processes can race. The custom benchmark had a separate conservative admission ledger; that hard per-run ceiling is not automatically the serving client's behavior. Unknown billed attempts/retries must remain accounted for.
- `kb/model_api.py::response_parts()` includes Messages cache reads/writes in input token counts. Shared `_cost()` applies the configured ordinary input/output prices to all input, which does not reproduce cache read/write pricing when nonzero. Latest benchmark calls had no thinking blocks; the portable benchmark ledger used the live catalogue rates. Preserve unknown/conservative pricing provenance rather than calling all estimates exact bills.
- Shared retries remain enabled for some non-query ingestion calls; query `SharedQueryClient.scoped()` limits transport to one attempt and query schema recovery is explicit. Do not accidentally reintroduce silent paid retries or stale per-call usage while repairing schemas.
- The official notebook remains unchanged; `evaluation/official.py::OfficialJudgeTransport` only adapts the transport to Qwen's Messages route. Preserve that distinction. The run-level judge/driver is not the production API.

Acceptance: a real environment-configured server request works and traces correctly; auth is never leaked; cost admission/failed usage/cache pricing behavior is tested under concurrency and unknown-charge conditions. Coordinate shared foundation changes with the teammate instead of overwriting their work.

## 11. P2 — Validation gaps and benchmark status can mask failure

- Current checked-in offline suite last passed **136 tests, 7 slow tests deselected**. Synthetic responders emit valid mappings/quotes by default, so these tests did not expose the real model's empty-ID behavior. Add model-shaped negative fixtures and classification assertions.
- The custom run directly called `answer_query()` with real models, storage and Langfuse. It did not verify the complete public HTTP path, server key loading, deployment memory or endpoint deadline behavior.
- Langfuse SDK flushing is not remote receipt confirmation. Keep `sdk_flushed_receipt_unverified` honest unless checking exported observations. A previous connectivity test is not proof of this run's remote trace receipt.
- A driver can report `completed` and HTTP can return a response while the answer is an abstention with zero accepted claims. Reports must show per-row answer status, accepted claim count, official quality metrics and failures. Never drop failed rows from aggregate statistics.
- Full 35-document corpus, hidden/second-corpus retrieval, OCR/table fidelity and target-host performance have not been demonstrated by this two-question run. These are unmeasured areas, not proof of defects in every component. Local page selection changed navigation and needs quality comparisons before claiming parity with the paid survey.

## 12. Already implemented — preserve these fixes

Do not waste demo credits re-discovering or undoing the following:

- Qwen Flash uses OpenCode's **Anthropic-compatible Messages** endpoint, not the original OpenAI Chat Completions route. `kb/model_api.py` is the shared request/response adapter. `thinking: {type: disabled}` is explicit; the live model catalogue advertised this variant. Simply changing the model string on the old payload is insufficient.
- The `.env` model pins, checked-in defaults, example config and deployment model pin were switched to Qwen. Current checked catalogue prices were $0.15/M input, $0.47/M output, $0.016/M cache reads, $0.20/M cache creation. Recheck metadata before a future paid run; prices can change. No expensive fallback.
- BGE-small (`BAAI/bge-small-en-v1.5`) embeddings and MiniLM (`Xenova/ms-marco-MiniLM-L-6-v2`) reranking run locally via CPU/ONNX. SQLite FTS5/BM25, exact quote/ID matching, arithmetic and citation rendering need no generative model. Page cards are extractive by default. Local page selection is now the default; `KB_PAGE_SELECTION=llm` opts back into the paid page survey for comparison.
- Evidence verification already selects stable source-span IDs instead of reproducing quote text, validates IDs and permits at most one split recovery before stopping repeated schema failures. Extend the reliable span mechanism to the writer; do not disable it.
- Narrow single-document/single-obligation facts skip paid page surveying and verify a bounded initial/reserve set. Factual duplicate-value merging preserves conflicts/dependencies. It is not a general analytical novelty selector.
- The earlier finishing-token reserve bug is fixed in `kb/query/runtime.py`: effective model limits apply to future answer/check reservations, and drafting reserves its final verifier. The old 4,096-token minimum remains DeepSeek-specific; do not apply it to Qwen's small JSON calls. The latest run did not exhaust the token budget.
- Raw response content, stop reason, per-call usage and elapsed time are retained privately, including failed JSON responses. Known failed-call usage is charged once. Nested source offsets are absolute. Dense search uses finite-checked accumulation instead of the locally warning-prone BLAS path.
- Keep exactly ten ordered public trace stages, each with `step_name`, `description`, `input`, `output`.

## 13. Reproduce safely without hidden history

### Offline first

From the current development repository:

```sh
.venv312/bin/python -m pytest -q -m 'not slow'
git diff --check
```

On a fresh machine, create a Python 3.12 environment and install `requirements.txt`; do not assume the macOS lockfile is portable to Linux. Use the equivalent interpreter path in the following commands. Organizer corpus/benchmark files are not in this repository.

A minimal **zero-credit** reproduction of the misleading abstention from empty claim mappings:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from kb.query.pipeline import answer_query
from kb.query.observability import LocalSink
from tests.track_b.helpers import FakeLLM, MemoryStore, settings

def responder(name, payload):
    result = FakeLLM.default(name, payload)
    if name == "answer":
        for selection in result["selections"]:
            selection["obligation_id"] = ""
    return result

with TemporaryDirectory() as temporary:
    result = answer_query(
        "synthetic", "Explain the reported capital ratio",
        store=MemoryStore({"report": ["The reported capital ratio was 14 percent."]}),
        generation_id="synthetic-generation", settings=settings(Path(temporary)),
        llm=FakeLLM(responder), sink=LocalSink(),
    )
    print(result["status"], result["answer"], result["coverage"]["limitations"])
```

This reproduces the rejection path with synthetic text. The repaired renderer should now identify a validation failure rather than claim that retrieval found nothing. It is not a model test or an official score.

### Reproduce the public development cases only when credentials and credits are ready

Local source locations on the current machine:

- `../Train/Documents/2012.07440v3.pdf`
- `../Train/Benchmarks/benchmark_100.jsonl`
- `../Train/Evaluation/Evaluation.ipynb`
- `data/collections/single_doc_smoke/active.json` points to the existing generation. Use `Registry(settings).active_dir()`/`Store.open()`, not a hardcoded generation directory.

If the collection exists, **do not reindex it**. On a new machine index only a folder containing the one PDF or a one-document ZIP, using `scripts/index_local.py --src ... --collection single_doc_smoke`. The script accepts a folder or ZIP, not a bare PDF. Confirm costs/auth before doing this.

The repository's checked-in capture path, once an authorized API key is configured:

```sh
.venv312/bin/python -m scripts.run_benchmark \
  --local --env-file .env \
  --benchmark ../Train/Benchmarks/benchmark_100.jsonl \
  --collection single_doc_smoke --ids C31,C18 \
  --out artifacts/handoff-check/capture.jsonl
```

That uses the serving binder and its **configured** settings/deadline; it does not recreate the custom benchmark's 180-second override or automatically add its five-cent admission ledger. Set and verify a genuine per-run credit guard before making live calls. The current shared spend cap alone has the limitations described above. Do not run this command repeatedly until it happens to succeed.

For HTTP validation, start `.venv312/bin/python -m scripts.serve --env-file .env`, and use the same capture command with `--api http://127.0.0.1:8000` instead of `--local`. Preserve exactly `POST /index` and `POST /query`; do not introduce a public health/debug route.

Official judging is separate and billable. With the authorized configuration loaded into the process environment, use `python -m scripts.evaluate <capture.jsonl> --notebook ../Train/Evaluation/Evaluation.ipynb`. This script does not have an `--env-file` argument. `evaluate_file()` reads its API key from an argument/environment, so do not assume merely leaving a key in an unread local file configures this command. Use a safe environment loader and never echo secrets.

Protect these original hashes:

- Notebook: `f75493648896a79fc28499f04bb4909baea9bf717c1b040d0c3fb3974aa5f583`.
- Benchmark JSONL: `bce8a3e48d493e5635fa83cfd5c0c309f02a171fc1951a2f76bd128b23cd1288`.

## 14. Suggested repair order and completion checks

1. Add synthetic regressions for empty obligation IDs, invalid/ellipsis quotes, all-claims-rejected messaging and partial supported answers. Add distinct rejection diagnostics.
2. Repair writer schema/support representation. Keep final semantic verification. Reserve any single bounded repair in advance.
3. Make no-answer/generation-failure classification truthful without weakening public API or source-grounding requirements.
4. Improve analytical evidence novelty/sufficiency and batching; preserve conflicts, tables and missing-scope disclosures. Measure fewer calls and context redundancy.
5. Address factual source wording/numeric formatting and inspect raw judge decompositions without metric gaming.
6. Validate deployment auth, a real HTTP request, production deadline and cost controls; fix shared risks with the teammate as needed.
7. Run the same one-document development smoke once under an explicit small monetary cap. Report raw metrics, failures, accepted claim counts, complete actual writer context, stage latency and total cost. Only then broaden validation if justified and authorized.

A repair is not complete because tests pass or the response is nonempty. Required evidence is supported/cited claims that survive the validator, accurate handling of unsupported subrequests, improved measured quality/latency and no regression in the factual case. The formal goal remains all four official metrics at least **0.95**, with no guarantee from this handoff that the target will be achieved.

**Non-negotiable constraints:** no benchmark-answer hardcoding, no source corpus substitution, no hidden-set access, no runtime gold/web lookup, no alteration of the official evaluator, no citation stripping or hidden writer context to game metrics, no model training/fine-tuning assumption, no silent expensive fallback, and no leaked credentials. Keep collection isolation, document/page provenance, required Langfuse tracing, exact source support, bounded execution and truthful incomplete/error status. Use the actual Smart Knowledge Base statement/compliance file rather than rules from the other hackathon tracks.


## Implementation update: extractive source selection

The answer writer now requests `selections` with one nonempty `obligation_id`, one valid `evidence_id`, and consecutive source sentence/span IDs. The application reconstructs exact support and source wording, with only a narrowly defined display cleanup for italicized thousands commas. It does not accept generated/paraphrased text as a source statement. Literal legacy adapters remain supported but paraphrases are rejected. Source support and final semantic verification remain active. Per-selection rejection reasons are saved privately. Empty accepted-claim output now distinguishes source-validation failure from retrieval absence.

The supplied evaluator notebook and its point decomposition remain unchanged so new scores are comparable. These repairs address implementation causes; a live rerun is needed to establish the resulting quality. The historical diagnostics above remain unmodified evidence of the original failure.


## Latest live repair result: extractive writer

See [the new portable report](docs/diagnostics/qwen-extractive/REPORT.md) and [summary](docs/diagnostics/qwen-extractive/summary.json), evaluated at `da94752` with the original official scorer unchanged. Factual C31 now scores **100% on all four metrics** (21.82s). Analytical C18 now has **18 accepted selections and 18 semantically verified claims**, with no empty-ID/quote rejection recurrence. It remains **partial** (118.22s): answer precision **25.93%**, answer recall **88.89%**, context precision **87.50%**, context recall **42.86%**. Total cost including judging **$0.01217614**. Offline suite: **144 passed, 7 slow tests deselected**.

The historical P0 failures above are retained for provenance, but the latest priority is analytical over-inclusion, reference-relevant fact selection, context coverage and deadline margin. Source-literal output does not ensure high answer precision: too many extra source facts are still included. Read the latest report before assuming that the current analytical output is still the old zero-claim abstention. Do not claim the project meets the 0.95 targets overall.


## Metadata navigation implementation update

Source-derived metadata is now collected during ingestion and can be backfilled into an existing collection with no LLM or embedding calls. See [metadata retrieval](docs/METADATA_RETRIEVAL.md) for the implementation, upgrade command, confidence rules and limitations. This includes section ranges, validated contents/index references, page labels, internal PDF links, captions, table headers, source-local references, units, years, OCR/geometry diagnostics and declared PDF properties. Metadata is routing context, never factual evidence.

An offline comparison using identical saved plans on the same one-document cases reduced factual candidate elements from 56 to 42 and retained its previously cited source. After teammate integration, analytical candidate count remained 86 with or without metadata and all 18 previously cited sources remained available (the earlier comparison used 89). This is candidate retention, not a fresh answer-quality evaluation. No paid API calls were made.

**Still open:** analytical answer over-inclusion and precision, high sequential model latency, writer-context omissions, full-corpus/held-out evaluation and the deployment/accounting gaps described above. Metadata alone has not demonstrated those issues solved. Generic topic matches do not narrow searches, specific section focus retains independent fallback sources, and table/figure dependency expansion is capped to avoid increasing irrelevant context.


## Analytical routing and coverage repair

Broad analytical searches no longer narrow to metadata-only ranges; literal requested topics receive independent source matches. The extractive writer receives a checklist of topic phrases copied from the original question, and the existing final verifier checks topic coverage separately from claim support. Missing/duplicate/invalid coverage checks cannot prove completeness. General background is filtered separately from direct findings and necessary qualifications. Source numeric Markdown artifacts are repaired for display while raw quotation validation remains exact.

These are implementation changes, not proof of a metric improvement. Read [the repair notes](docs/ANALYTICAL_COVERAGE_REPAIR.md) and the subsequent benchmark report for measured limits. The official evaluator is unchanged; a separate zero-call audit flags inconsistent labels without rewriting scores.
