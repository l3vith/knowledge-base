# M5: blocking index orchestration — self-contained assignment

You have no conversation history. Build only your assigned module in the future application checkout. This package is the authoritative handoff; do not infer completed implementation from prose. Read CONTRACTS.md, ARCHITECTURE.md and COMPLIANCE.md in full, then your module in PLAN.md and the relevant PROMPTS.md section. Inputs are configurable source PDFs and a user query. Public benchmark answers/chunks and evaluator belong only to offline M11. Preserve supplied files and secrets.

Hard requirements: Python 3.10+; source-derived qualified identity; original source spans and 1-based physical PDF pages; immutable generation binding; bounded ten-stage query pipeline; exactly POST /index and POST /query; each public trace step has exactly step_name/description/input/output; required separate Langfuse cost/latency; unknown usage/price remains null. No training/fine-tuning, runtime web, hidden access, hardcoded answers or recursive retrieval in the strict profile. Return every writer-visible source fragment. Never treat relevance as factual entailment, navigation summaries as original evidence, or mock tests as live-model proof.

Work against M0 protocols and fakes before concrete dependencies land. Own only module paths listed in PLAN.md; coordinate common-interface changes with the lead. Pin actual dependencies/models at build time; do not copy Windows paths, default prices or throughput guesses. The two-person event and core-work timing are organizer conduct requirements. A future worker must verify eligibility and actual implementation provenance rather than claiming it from this package.

## Your implementation procedure and acceptance

Implement archive validation before extraction. Enforce resource caps, safe relative paths, encrypted-file policy and supported types. Ignore only known benign archive metadata entries with a manifest entry explaining exclusion; do not silently ignore an unsupported user document. Reject duplicate normalized paths and preserve distinct same-basename subpaths.

Run parse → structure/elements → identities/cards → FTS/vectors → validation → manifest/atomic activation. Each required document/page/index component must finish. Use staged, restart-safe writes; record page counts and failures. Optional LLM enrichment is a bounded pre-activation phase only when enabled. Do not mutate active generation after success.

Return `/index` success only after commit. Client/proxy timeout settings must cover measured long ingestion; HTTP keep-alive is not the request processing timeout. Private progress logs show page/category counts and estimated completion without adding public endpoints. Handle aborted/disconnected requests without leaking a ready partial generation.

Acceptance: malicious ZIP rejected; injected mid-build failure preserves old collection; scan-required archive cannot pass without OCR; mixed supported/unsupported input fails clearly; successful response implies all manifest checks pass; a cold second collection leaves the first intact.

## Completion report

Return the owned paths changed, exact interface/schema version, meaningful test commands and actual results, source/generation/config hashes where relevant, live checks performed or explicitly not run, and unresolved risks/dependencies. Include any compatibility adapter assumptions. Run the relevant module checks first and the combined contract/integration suite when dependencies are available. Do not alter official scoring or use holdout results to select changes. A missing required acceptance artifact is unfinished work; state it explicitly rather than substituting an architecture claim.
