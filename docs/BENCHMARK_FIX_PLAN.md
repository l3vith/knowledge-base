# Single-document benchmark fixes

Scope: repair the measured factual latency/over-retrieval and analytical verification failures. Preserve the ten public trace stages, original source evidence, collection identity, required citations, Langfuse, and the unchanged official evaluator. Do not train a model or copy benchmark facts into serving code.

## Evidence

The factual request spent 65.0/82.75 seconds in one full-document page survey, retrieved 57 elements, verified all 57 in three calls, and returned two passages for the same scalar. Local search/reranking took about 1.1 seconds. The analytical request sent 25–37 elements per batch and requested verbatim support quotes within 2,000 output tokens; all five batches returned invalid JSON. Truncation is a hypothesis until finish reasons/raw diagnostics are captured. The count-based evaluator also interpreted citations as extra points. Original scores must remain untouched.

## Work order and acceptance

1. **Compact verification and bounded recovery.** Assign deterministic source sentence/span IDs. Return IDs/aspects and short optional validated fact keys, reconstruct exact quotes locally, and keep source text immutable. Limit both batch item count and source size. Validate all IDs. Retain complete source elements for tables and their context. On a malformed/truncated response, permit one budgeted split of that batch; stop repeated schema failures and preserve already verified evidence. Test many short elements, mathematical text/escaping, unknown spans, output truncation, partial success, and no-source failure.
2. **Factual path and evidence novelty.** Only a narrow single-document, single-obligation fact request qualifies; comparisons, exhaustive requests, uncertain routing and missing periods use the general path. Skip the LLM page survey, preserve scoped lexical/dense discovery and local ranking, verify a small first batch, and allow a bounded reserve from the same already retrieved candidates. Deduplicate confirmed identical scalar support within the same qualified scope, preserve conflicting values and all table/context dependencies, and return every source fragment actually supplied to the writer. Test correct evidence below the first candidate batch and explicit fast-path exclusions.
3. **Diagnostics and numerical integrity.** Persist private raw response content, finish reason, usage and elapsed time even for invalid JSON. Do not charge stale usage or silently retry failed calls. Bound support-output size and record omitted/bounded work. Replace the warning-prone local BLAS dot-product path with validated finite, scoped deterministic accumulation; compare against a reference under strict floating-point error settings.
4. **Validation without waste.** Run focused regressions and the existing combined suite offline. Reuse the already indexed 24-page collection. Run the same two development questions once on DeepSeek V4.1 Flash with a separate hard $0.05 cap including any judging; no bulk indexing, model substitution or automatic repeated experiments. Report failures, raw official metrics, per-stage latency, source context and total cost. Do not select changes from hidden/holdout results.

## Evaluator policy

Irrelevant returned writer context is penalized by context precision. Additional relevant chunks are not automatically penalized, and the supplied recall count ratio can exceed one. Reduce redundant evidence before generation and retain required document/page citations. Never hide writer context, strip citations only for scoring, alter the notebook, or describe citation-point artifacts as measured factual error. Document the judge behavior separately.

## Completion evidence

Each item requires code, meaningful tests and a result artifact. Performance targets are hypotheses: eliminate the survey call on eligible factual queries, verify fewer source candidates, return one sufficient passage for duplicate scalar support, and complete the analytical path with valid compact verification. No speed or quality target is achieved until a live rerun measures it. Preserve demo credits and stop at the spending cap.


## Implementation status (24 October)

Implemented the compact source-span protocol (source text is sent once), eight-element batches, one split recovery, fail-fast repeated failures, and retention of successful evidence. Eligible single-document fact requests skip the card survey and verify up to eight initial and eight reserve candidates. Verified duplicate numeric values are merged only within the same qualified document/obligation, retaining conflicting values, different units and dependencies. All writer context and required citations remain visible.

Private diagnostics now retain raw answer content, finish reason, requested output limit, elapsed time and known billed usage on JSON failure. Known failed-call usage is charged once and releases unused token reservations. Source fragment offsets remain absolute through nested slicing. Scoped dense search uses finite-checked float64 accumulation instead of the locally warning-prone BLAS operation.

Integrated teammate main through `db0f7d6`, including their ingestion cache, deployment, shared response cache and spend ledger. The query adapter retains these shared features but limits each transport call to one attempt; schema recovery remains in the query ledger. Dry-run verification understands the same compact spans.

### Provider issue discovered during validation

The first compact live responses had **null answer content and `finish_reason=length`**, exhausting 1,536 and 896 completion tokens. This confirms output exhaustion, rather than an ordinary escaping error. Disabling thinking with the upstream toggle alone was ineffective through this gateway; sending the upstream `reasoning_effort=none` setting was rejected. The installed OpenCode model catalogue advertises `low`, `high`, `max`. Production now uses **low** for DeepSeek and reserves at least 4,096 output tokens per query call, including reasoning; reservations are released against actual usage.

The [DeepSeek API reference](https://api-docs.deepseek.com/api/create-chat-completion) documents thinking/reasoning controls, but gateway capability metadata takes precedence for accepted values. No alternate or expensive model was used.

A final **live source-verification probe succeeded** using the compact protocol and `low`: 3.28 seconds, 442 input / 367 output tokens, `finish_reason=stop`, exact source-span ID and source-backed value. This verifies transport and compact evidence selection, **not** the full revised two-question benchmark or analytical answer quality.

The full post-fix benchmark remains unverified. Failed transport checks, an interrupted request and the successful probe share the same cumulative **$0.05 ceiling**; unknown/rejected requests retain conservative reservations. Known reported-token/catalog cost was **$0.009370812**, with a conservative cumulative admission ledger of **$0.0484573**. Unknown actual charge is not represented as zero. Further paid testing stopped at this ceiling. Original benchmark and evaluator files remain unchanged.

Next validation: reuse the indexed collection, run the original factual and analytical requests through the final `low` transport, then compare latency, returned context, answer support and untouched official metrics. The earlier 82.75-second result is a baseline, not evidence of the final system's speed. Do not claim a quality or speed improvement until this run completes.

Offline validation: **130 passed, 7 slow tests deselected**. New regressions cover bounded/reserve retrieval, compact span IDs, one split recovery, partial evidence, factual survey skipping, conflicting values/units/dependencies, nested source identity, strict finite scoped vector search, raw failure diagnostics, billed usage, shared single-attempt calls and compact dry-run support. `git diff --check` passed.
