# M4: automatic identity and page cards — self-contained assignment

You have no conversation history. Build only your assigned module in the future application checkout. This package is the authoritative handoff; do not infer completed implementation from prose. Read CONTRACTS.md, ARCHITECTURE.md and COMPLIANCE.md in full, then your module in PLAN.md and the relevant PROMPTS.md section. Inputs are configurable source PDFs and a user query. Public benchmark answers/chunks and evaluator belong only to offline M11. Preserve supplied files and secrets.

Hard requirements: Python 3.10+; source-derived qualified identity; original source spans and 1-based physical PDF pages; immutable generation binding; bounded ten-stage query pipeline; exactly POST /index and POST /query; each public trace step has exactly step_name/description/input/output; required separate Langfuse cost/latency; unknown usage/price remains null. No training/fine-tuning, runtime web, hidden access, hardcoded answers or recursive retrieval in the strict profile. Return every writer-visible source fragment. Never treat relevance as factual entailment, navigation summaries as original evidence, or mock tests as live-model proof.

Work against M0 protocols and fakes before concrete dependencies land. Own only module paths listed in PLAN.md; coordinate common-interface changes with the lead. Pin actual dependencies/models at build time; do not copy Windows paths, default prices or throughput guesses. The two-person event and core-work timing are organizer conduct requirements. A future worker must verify eligibility and actual implementation provenance rather than claiming it from this package.

## Your implementation procedure and acceptance

Derive identity from cover/front matter, embedded metadata, trustworthy headings and identifiers. Retain alternative candidates and provenance when sources conflict. Fields are individually source/inferred/unknown. Do not make the most frequent year the reporting period; do not collapse distinct legal entities or different regulatory proposals because the issuer/year match.

Build source-derived page cards without mandatory model calls. Preserve source excerpt anchors and quality flags. Optional enrichment receives source text and must return anchored values or unknown. Cache optional enriched outputs by all relevant hashes; output is navigation-only. An enrichment failure yields a recorded fallback card when required source extraction is valid.

Version matching requires entity, kind, scope, identifiers and comparable periods. Explicit multi-year/multi-entity queries preserve each request. “Latest” never crosses to a different legal entity or unrelated document class. Runtime identity routines cannot import benchmark alias maps. Offline filename alignment belongs exclusively to M11.

Acceptance: ambiguous identity stays uncertain; missing year is not invented; subsidiaries remain distinct where appropriate; renamed PDFs still route from content; false proposal aliases are refused; page cards work without an LLM; generated fields never appear as original evidence.

## Completion report

Return the owned paths changed, exact interface/schema version, meaningful test commands and actual results, source/generation/config hashes where relevant, live checks performed or explicitly not run, and unresolved risks/dependencies. Include any compatibility adapter assumptions. Run the relevant module checks first and the combined contract/integration suite when dependencies are available. Do not alter official scoring or use holdout results to select changes. A missing required acceptance artifact is unfinished work; state it explicitly rather than substituting an architecture claim.
