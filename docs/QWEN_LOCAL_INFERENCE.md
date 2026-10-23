# Qwen Flash and local token savings

## Shipped behavior

Default model: `qwen3.8-flash`, with `thinking: {type: disabled}` on OpenCode's Anthropic-compatible Messages endpoint. Native Messages text blocks, stop reason and usage are normalized for the existing query pipeline. Cache reads/writes are included in input-token accounting; shared cost reporting applies the configured input/output rates. The live check had no cache tokens. No expensive model fallback exists. Query-level transport stays at one attempt per call; one schema split recovery remains bounded by the query ledger.

All active local model pins and pricing fields were updated without storing CLI credentials. The checked-in defaults/example and deployment model pin match. The official evaluator notebook and metric definitions remain unchanged; the evaluation wrapper supplies the compatible transport.

The previous finishing-budget bug is repaired: intermediate calls reserve effective answer and final-check limits, and drafting itself retains a final-check reserve. The DeepSeek-specific minimum no longer forces Qwen to reserve 4,096 tokens for small JSON calls.

## Local components

- **Semantic retrieval:** existing `BAAI/bge-small-en-v1.5` embeddings, CPU inference through FastEmbed/ONNX. No API tokens.
- **Passage ranking:** existing `Xenova/ms-marco-MiniLM-L-6-v2` cross-encoder, CPU inference. Scores establish relevance, not truth or entailment.
- **Lexical retrieval:** SQLite FTS5/BM25 with safe query construction; no model needed.
- **Page navigation:** initial lexical/vector page ranks plus per-obligation lexical matches. Local mode is now the default, removing a generative page-survey call. Exhaustive requests preserve the available pool subject to the existing finite raw-page budget. All omissions and local selection appear in the trace. `KB_PAGE_SELECTION=llm` restores the paid option for comparison.
- **Page cards:** teammate's existing extractive mode uses source text, TF-IDF topics and structural cues. No new API page-card call.
- **Source IDs, exact quote matching, citation/page validation, duplicate matching and arithmetic:** deterministic Python. Do not replace these with a small generative model.

No new local model downloads or fine-tuning were introduced. The cached CPU models fit the current implementation and deployment path. A local NLI model could be evaluated later as an additional entailment filter, but has not been calibrated for this corpus and should not replace semantic claim verification on the basis of relevance scores alone.

## Validation and limits

A real source verification call through the shared Qwen transport returned HTTP 200, `end_turn`, text blocks only, 484 input and 77 output tokens, 3.36 seconds, and $0.00010879 computed at the verified catalogue rates. This validates authentication via the existing CLI session, the Messages wire format, disabled thinking on this response, JSON decoding and source-span output. The half-cent one-call admission ceiling was not reached. Credentials stayed in process memory; only allowlisted model/pricing fields were persisted to the ignored local environment file.

The full analytical query and official accuracy metrics have **not** been rerun on this profile. Local page selection changes navigation and needs paired retrieval/answer-quality measurement before claiming accuracy parity. Evidence support, entity/period checks and final verification remain active. There is no runtime access to benchmark answers.

Offline validation: **136 passed, 7 slow tests deselected**; `git diff --check` passed. Regressions cover both wire formats, disabled thinking, native usage/cache parsing, local page navigation with all ten stages, and finishing-budget reserves.
