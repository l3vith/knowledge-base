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
