# M7: page/element retrieval and CPU triage — self-contained assignment

You have no conversation history. Build only your assigned module in the future application checkout. This package is the authoritative handoff; do not infer completed implementation from prose. Read CONTRACTS.md, ARCHITECTURE.md and COMPLIANCE.md in full, then your module in PLAN.md and the relevant PROMPTS.md section. Inputs are configurable source PDFs and a user query. Public benchmark answers/chunks and evaluator belong only to offline M11. Preserve supplied files and secrets.

Hard requirements: Python 3.10+; source-derived qualified identity; original source spans and 1-based physical PDF pages; immutable generation binding; bounded ten-stage query pipeline; exactly POST /index and POST /query; each public trace step has exactly step_name/description/input/output; required separate Langfuse cost/latency; unknown usage/price remains null. No training/fine-tuning, runtime web, hidden access, hardcoded answers or recursive retrieval in the strict profile. Return every writer-visible source fragment. Never treat relevance as factual entailment, navigation summaries as original evidence, or mock tests as live-model proof.

Work against M0 protocols and fakes before concrete dependencies land. Own only module paths listed in PLAN.md; coordinate common-interface changes with the lead. Pin actual dependencies/models at build time; do not copy Windows paths, default prices or throughput guesses. The two-person event and core-work timing are organizer conduct requirements. A future worker must verify eligibility and actual implementation provenance rather than claiming it from this package.

## Your implementation procedure and acceptance

Implement the source lexical, page vector, heading/section and bounded reference candidate generators. Preserve raw per-generator scores and origin; fuse page ranks using fixed RRF. Apply scope before top-k and per-obligation quotas before global cap. Exact identifiers/numeric vocabulary have explicit signals without treating numerical equality as full support.

For broad queries enumerate available source-derived cards within routed documents up to a predeclared survey budget; preserve all omission counts. Read selected-page elements plus scoped element FTS hits and source dependencies. Do not just expand top-k parents and call that coverage innovation. Similar text in two scopes remains separate evidence.

Order verification candidates with actual-token pair windows and the pretrained CPU ranker. Default no auto-keep/drop thresholds. Respect configured pair cap and mark unscored candidates. Keep dependency groups intact and protect at least one plausible candidate for each covered slot where possible. Budgets that preclude this produce a visible partial-coverage state.

Acceptance: correct scope survives near-duplicate distractors; broad multi-section fixture visits evidence outside top similarity pages; long source tail can enter through a token window; null scores do not win sorting; negation survives model input; repeated contexts do not inflate the evidence list; cap behavior is explicit.

## Completion report

Return the owned paths changed, exact interface/schema version, meaningful test commands and actual results, source/generation/config hashes where relevant, live checks performed or explicitly not run, and unresolved risks/dependencies. Include any compatibility adapter assumptions. Run the relevant module checks first and the combined contract/integration suite when dependencies are available. Do not alter official scoring or use holdout results to select changes. A missing required acceptance artifact is unfinished work; state it explicitly rather than substituting an architecture claim.
