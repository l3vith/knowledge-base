# M1: page extraction and selective OCR — self-contained assignment

You have no conversation history. Build only your assigned module in the future application checkout. This package is the authoritative handoff; do not infer completed implementation from prose. Read CONTRACTS.md, ARCHITECTURE.md and COMPLIANCE.md in full, then your module in PLAN.md and the relevant PROMPTS.md section. Inputs are configurable source PDFs and a user query. Public benchmark answers/chunks and evaluator belong only to offline M11. Preserve supplied files and secrets.

Hard requirements: Python 3.10+; source-derived qualified identity; original source spans and 1-based physical PDF pages; immutable generation binding; bounded ten-stage query pipeline; exactly POST /index and POST /query; each public trace step has exactly step_name/description/input/output; required separate Langfuse cost/latency; unknown usage/price remains null. No training/fine-tuning, runtime web, hidden access, hardcoded answers or recursive retrieval in the strict profile. Return every writer-visible source fragment. Never treat relevance as factual entailment, navigation summaries as original evidence, or mock tests as live-model proof.

Work against M0 protocols and fakes before concrete dependencies land. Own only module paths listed in PLAN.md; coordinate common-interface changes with the lead. Pin actual dependencies/models at build time; do not copy Windows paths, default prices or throughput guesses. The two-person event and core-work timing are organizer conduct requirements. A future worker must verify eligibility and actual implementation provenance rather than claiming it from this package.

## Your implementation procedure and acceptance

Implement PDF opening from retained original bytes and return page records in physical order. Extract text, blocks, tables and coordinates while preserving raw/native artifacts. Add multi-signal quality classification: native text density, replacement characters, image coverage, layout integrity and blank-page detection. Keep threshold values configurable and record the decision basis per page.

Pilot the chosen adapter against a small stratified source sample and synthetic fixtures. Explicitly set OCR behavior; check installed API/documentation and output shapes. OCR only scan-like/corrupt pages, with bounded workers, timeout and quality flags. A broken OCR executable or missing language model is a startup/preflight failure for scan-required corpora. Do not consider a blank string a successful OCR result on a content-bearing page.

Persist native and OCR alternatives, extraction provenance, selected mode and raw page images where needed. Do not erase original bytes after staging. A content-hash cache key includes parser/OCR versions, DPI/language/options and source hash. A cache hit validates checksums before reuse. Rendered OCR files use a real writable temporary directory and are cleaned safely; do not depend on the Mac's `/tmp` alias behavior.

Acceptance: mixed native/scan/blank PDF preserves page count and order; OCR runs on the intended subset; a rotated scan remains traceable; corrupt PDFs and OCR failures cannot yield a ready collection; source anchors resolve; repeat parsing is deterministic within a fixed environment. Corpus-specific sample checks are diagnostics, not hardcoded runtime rules.

## Completion report

Return the owned paths changed, exact interface/schema version, meaningful test commands and actual results, source/generation/config hashes where relevant, live checks performed or explicitly not run, and unresolved risks/dependencies. Include any compatibility adapter assumptions. Run the relevant module checks first and the combined contract/integration suite when dependencies are available. Do not alter official scoring or use holdout results to select changes. A missing required acceptance artifact is unfinished work; state it explicitly rather than substituting an architecture claim.
