# M11: offline evaluation and source alignment — self-contained assignment

You have no conversation history. Build only your assigned module in the future application checkout. This package is the authoritative handoff; do not infer completed implementation from prose. Read CONTRACTS.md, ARCHITECTURE.md and COMPLIANCE.md in full, then your module in PLAN.md and the relevant PROMPTS.md section. Inputs are configurable source PDFs and a user query. Public benchmark answers/chunks and evaluator belong only to offline M11. Preserve supplied files and secrets.

Hard requirements: Python 3.10+; source-derived qualified identity; original source spans and 1-based physical PDF pages; immutable generation binding; bounded ten-stage query pipeline; exactly POST /index and POST /query; each public trace step has exactly step_name/description/input/output; required separate Langfuse cost/latency; unknown usage/price remains null. No training/fine-tuning, runtime web, hidden access, hardcoded answers or recursive retrieval in the strict profile. Return every writer-visible source fragment. Never treat relevance as factual entailment, navigation summaries as original evidence, or mock tests as live-model proof.

Work against M0 protocols and fakes before concrete dependencies land. Own only module paths listed in PLAN.md; coordinate common-interface changes with the lead. Pin actual dependencies/models at build time; do not copy Windows paths, default prices or throughput guesses. The two-person event and core-work timing are organizer conduct requirements. A future worker must verify eligibility and actual implementation provenance rather than claiming it from this package.

## Your implementation procedure and acceptance

Read EVALUATION.md first. Keep the notebook untouched and hash-verified. A runner invokes its unchanged definition cells in an isolated namespace, sets credentials/config externally and skips sample demonstration execution. Snapshot the actual evaluated dataset and model/config manifest. Preserve all query failures and denominators in the result bundle.

Create a frozen query-family split with seed 20261023, aiming at 70 development/30 holdout without breaking families. Inspect dev/inner-validation only for tuning. Document shared source documents and the fact that a fully document-disjoint split is impractical on this benchmark's connected source graph. Exact counts may move with family integrity; record manifest IDs before tuning.

Offline alignment uses verified identity/identifier first, then page/span support with conservative confidence. Missing/ambiguous references remain unresolved. A text overlap threshold alone cannot alias distinct proposals. Gold-unlisted retrieved evidence is not automatically irrelevant. Keep benchmark content entirely outside runtime stores.

Implement official metric export plus independent document/page/span/obligation/claim support diagnostics. Evaluate baseline controls and source/identity/coverage/verification ablations at comparable budgets. No training, threshold calibration or prompt changes based on the final holdout.

Acceptance: notebook hash unchanged, exact API chunks passed to scorer, all failures retained, missing-source references counted honestly, split family boundaries held, no holdout-derived tuning artifact, baseline and candidate manifests comparable.

## Completion report

Return the owned paths changed, exact interface/schema version, meaningful test commands and actual results, source/generation/config hashes where relevant, live checks performed or explicitly not run, and unresolved risks/dependencies. Include any compatibility adapter assumptions. Run the relevant module checks first and the combined contract/integration suite when dependencies are available. Do not alter official scoring or use holdout results to select changes. A missing required acceptance artifact is unfinished work; state it explicitly rather than substituting an architecture claim.
