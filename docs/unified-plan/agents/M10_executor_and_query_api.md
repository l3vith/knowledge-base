# M10: executor and query API — self-contained assignment

You have no conversation history. Build only your assigned module in the future application checkout. This package is the authoritative handoff; do not infer completed implementation from prose. Read CONTRACTS.md, ARCHITECTURE.md and COMPLIANCE.md in full, then your module in PLAN.md and the relevant PROMPTS.md section. Inputs are configurable source PDFs and a user query. Public benchmark answers/chunks and evaluator belong only to offline M11. Preserve supplied files and secrets.

Hard requirements: Python 3.10+; source-derived qualified identity; original source spans and 1-based physical PDF pages; immutable generation binding; bounded ten-stage query pipeline; exactly POST /index and POST /query; each public trace step has exactly step_name/description/input/output; required separate Langfuse cost/latency; unknown usage/price remains null. No training/fine-tuning, runtime web, hidden access, hardcoded answers or recursive retrieval in the strict profile. Return every writer-visible source fragment. Never treat relevance as factual entailment, navigation summaries as original evidence, or mock tests as live-model proof.

Work against M0 protocols and fakes before concrete dependencies land. Own only module paths listed in PLAN.md; coordinate common-interface changes with the lead. Pin actual dependencies/models at build time; do not copy Windows paths, default prices or throughput guesses. The two-person event and core-work timing are organizer conduct requirements. A future worker must verify eligibility and actual implementation provenance rather than claiming it from this package.

## Your implementation procedure and acceptance

Assemble the ten fixed stages with explicit QueryContext, bound generation, budget ledger, trace and dependency injection. Each stage executes once, with bounded internal batches. Include skips in order. Pass deadlines through CPU/model work and never schedule a model call after exhaustion. A failed stage preserves the completed execution/usage record.

Build the public response and typed errors from CONTRACTS.md. A useful verified partial result can be delivered with limitations; a raw infrastructure failure is not a no-answer. Resolve collection once per request, use immutable source mappings, and ensure no cache key omits generation/config/model identity. Do not cache answers by public question ID or load gold labels.

Acceptance: route/schema tests, ten-step order, missing collection, concurrent requests do not mix state, a reindex cannot alter an in-flight query, deadline/429/retry costs are retained, Langfuse IDs reconcile with the response and privacy checks pass.

## Completion report

Return the owned paths changed, exact interface/schema version, meaningful test commands and actual results, source/generation/config hashes where relevant, live checks performed or explicitly not run, and unresolved risks/dependencies. Include any compatibility adapter assumptions. Run the relevant module checks first and the combined contract/integration suite when dependencies are available. Do not alter official scoring or use holdout results to select changes. A missing required acceptance artifact is unfinished work; state it explicitly rather than substituting an architecture claim.
