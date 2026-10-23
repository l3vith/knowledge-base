# M8: finite survey, verification and coverage ledger — self-contained assignment

You have no conversation history. Build only your assigned module in the future application checkout. This package is the authoritative handoff; do not infer completed implementation from prose. Read CONTRACTS.md, ARCHITECTURE.md and COMPLIANCE.md in full, then your module in PLAN.md and the relevant PROMPTS.md section. Inputs are configurable source PDFs and a user query. Public benchmark answers/chunks and evaluator belong only to offline M11. Preserve supplied files and secrets.

Hard requirements: Python 3.10+; source-derived qualified identity; original source spans and 1-based physical PDF pages; immutable generation binding; bounded ten-stage query pipeline; exactly POST /index and POST /query; each public trace step has exactly step_name/description/input/output; required separate Langfuse cost/latency; unknown usage/price remains null. No training/fine-tuning, runtime web, hidden access, hardcoded answers or recursive retrieval in the strict profile. Return every writer-visible source fragment. Never treat relevance as factual entailment, navigation summaries as original evidence, or mock tests as live-model proof.

Work against M0 protocols and fakes before concrete dependencies land. Own only module paths listed in PLAN.md; coordinate common-interface changes with the lead. Pin actual dependencies/models at build time; do not copy Windows paths, default prices or throughput guesses. The two-person event and core-work timing are organizer conduct requirements. A future worker must verify eligibility and actual implementation provenance rather than claiming it from this package.

## Your implementation procedure and acceptance

Implement page-card survey batches with IDs/obligation relevance and source-inspection escalation for ambiguity. The budget is fixed before execution; do not add iterative retrieval. A rejected lossy card cannot veto independently strong source matches. Record eligible/surveyed/raw-read/omitted counts and distinguish those kinds of visibility.

Verification batches contain full bounded source fragments and required table/header dependencies, not clipped unseen tails. Output selection may be empty. Validate IDs, support quote offsets, source scope and schema. Record factual atoms with entity/period/units/basis; conflicting values remain qualified alternatives. Evidence relevance alone cannot mark an entire broad obligation complete.

Implement CoverageLedger updates as append-only decisions with deterministic summaries. Scope overflow, failed model batches and missing source are distinct limitations. Do not label all dropped evidence negative in an offline training dataset. No training is enabled by default.

Acceptance: header-dependent numeric fixture is supported only with its header; zero-relevant batch selects none; a fabricated quote is rejected; unseen table tail cannot be verified; summary omission remains discoverable via raw source branch; a provider failure is not labeled corpus absence.

## Completion report

Return the owned paths changed, exact interface/schema version, meaningful test commands and actual results, source/generation/config hashes where relevant, live checks performed or explicitly not run, and unresolved risks/dependencies. Include any compatibility adapter assumptions. Run the relevant module checks first and the combined contract/integration suite when dependencies are available. Do not alter official scoring or use holdout results to select changes. A missing required acceptance artifact is unfinished work; state it explicitly rather than substituting an architecture claim.
