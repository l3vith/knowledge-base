# Merge audit and decisions

This package reconciles the three files in final_plan/ with the audited knowledge-base-plan/ package. It is a synthesis, not an endorsement of either source in full. Input hashes preserve provenance. Every decision below has a canonical implementation destination in ARCHITECTURE.md, CONTRACTS.md, PLAN.md, EVALUATION.md or COMPLIANCE.md.

The source final_plan contains useful reported throughput and timing figures but no raw measurement artifact establishing their applicability here. Those figures are retained only as provenance, not promoted to verified local/server performance. Source audit JSON files copied here are labeled by their original audit/tool. The original problem statement, PDFs, labels and evaluator are unchanged.

## Decision ledger

### A01. Adopt: M0-first seams and M6–M11 Person 2 ownership

Source: `final_plan/PLAN.md module table`. PLAN.md and TEAM_ASSIGNMENT.md preserve independent work against protocols.

### A02. Adopt: Fixed query execution with bounded work

Source: `final_plan/ARCHITECTURE.md §4`. No retrieval back-edge; ten ordered stages include answer support verification.

### A03. Adopt: Natural source elements and page-level navigation

Source: `final_plan/PLAN.md M2–M4`. Canonical source paragraphs/tables remain distinct from tokenized search windows.

### A04. Adopt: Explicit source obligations and provenance

Source: `knowledge-base-plan/01_MASTER_PLAN.md`. Coverage slots, source spans, table dependencies and qualified claim support remain core.

### A05. Adopt: Atomic collection generations and scoped search

Source: `both source plans`. Query binds one generation; filter before top-k; reader-safe retention.

### R01. Revise: Nine versus ten query stages

Source: `final_plan/PLAN.md M10`. Add answer_verification before citation_render; all contracts/prompts follow ten names.

### R02. Revise: Full ingest-time page-card LLM work

Source: `final_plan/PLAN.md M4–M5`. Source-derived cards by default, selective budgeted enrichment; no mandatory ~1743 page-batch calls.

### R03. Revise: 240-token canonical chunks

Source: `knowledge-base-plan/reference-config.yaml`. Natural source elements plus tokenizer-limited search windows; never reshape evidence to evaluator counts.

### R04. Revise: Character limits claimed to enforce token limits

Source: `final_plan/PLAN.md M0,M3,M7`. Count actual model tokens including query/prefix; no silent text-tail clipping.

### R05. Revise: Global normalized-text deduplication

Source: `final_plan/PLAN.md M8,M10`. Deduplicate by source identity/anchor within qualified scope; preserve cross-year contradictions.

### R06. Revise: 40-bit document hashes

Source: `final_plan/PLAN.md global rule 10`. Full SHA-256 identities in new compiler specification; legacy integration gap must be recorded.

### R07. Revise: Year histogram metadata fallback

Source: `final_plan/PLAN.md M4`. Unknown period stays null; cited source or explicit inference required.

### R08. Revise: Issuer normalization removes Group/Holdings

Source: `final_plan/PLAN.md M4`. Preserve legal-entity distinctions, document kind, scope and identifiers.

### R09. Revise: Only newest sibling retained

Source: `final_plan/PLAN.md M6`. Retain every explicit entity/period; latest only within comparable verified versions.

### R10. Revise: Hard eight-document/eight-aspect truncation

Source: `final_plan/PLAN.md M6`. Document limits are soft for explicit scope; separate aspect groups from up to 64 obligation slots.

### R11. Revise: Catalog answerable=false exits before search

Source: `final_plan/PLAN.md M10`. Uncertain/empty route schedules fixed escape; summaries cannot prove absence.

### R12. Revise: Stop-word removal includes not

Source: `final_plan/PLAN.md M0`. Preserve negation in semantic inputs; quote FTS safely instead of deleting meaning.

### R13. Revise: Short repeated lines deleted as boilerplate

Source: `final_plan/PLAN.md M2`. Flags and scoring only; preserve unit/header/definition recovery and raw text.

### R14. Revise: Cross-encoder high score auto-verifies

Source: `final_plan/PLAN.md M7`. Relevance ordering only by default; no score-based factual entailment.

### R15. Revise: Long element clipped then whole unit kept

Source: `final_plan/PLAN.md M8`. Verify visible bounded fragments and source dependencies; never certify unseen tails.

### R16. Revise: Unknown evidence ID removed leaving assertion

Source: `final_plan/PLAN.md M9`. Reject or qualify whole unsupported claim, then deterministic rendering.

### R17. Revise: Provider error becomes no-information answer

Source: `final_plan/PLAN.md M9`. Infrastructure errors are typed failures; partial requires verified support and disclosed limits.

### R18. Revise: Uncited writer evidence hidden from response

Source: `both source plans ambiguous`. Return every writer-visible source fragment, with role and claim links; offline adapter passes exact returned list.

### R19. Revise: Trace clips scores and evidence arbitrarily

Source: `final_plan/PLAN.md M0`. Compact public summaries reference durable complete evidence/attempt artifacts.

### R20. Revise: Langfuse exceptions silently swallowed

Source: `final_plan/PLAN.md M0`. Visible tracing/export state; actual reconciliation required for release.

### R21. Revise: Guessed provider price and unknown tokens as zero

Source: `final_plan/PLAN.md Settings,LLM`. Unknown cost/usage is null with reason; verified dated price record required.

### R22. Revise: Nested pools and loose global concurrency

Source: `final_plan/PLAN.md M5`. Single shared scheduler, initial provider concurrency two, measured CPU/OCR jobs.

### R23. Revise: Stale lock removal by age and automatic old-generation cleanup

Source: `final_plan/PLAN.md M3`. Owner-checked locks and reader-safe explicit retention cleanup.

### R24. Revise: Delete staging/src after build

Source: `final_plan/PLAN.md M5`. Retain original PDFs/content-addressed source bytes and provenance.

### R25. Revise: Windows paths and system-install instructions

Source: `final_plan/PLAN.md global rules`. Portable checkout paths, isolated environment, real server capability validation.

### R26. Revise: Holdout performance selects rollback

Source: `final_plan/PLAN.md M12`. Freeze first, inspect once; future tuning invalidates untouched holdout status.

### R27. Revise: 60% overlap implies document alias

Source: `final_plan/PLAN.md M11`. Verified identity precedes overlap; ambiguous references stay unresolved, not hard negatives.

### R28. Revise: 603 chunks become a hard semantic-recall ceiling

Source: `final_plan/ARCHITECTURE.md source audit`. Count references honestly; unique absent facts and alternate support remain unquantified.

### R29. Revise: All page cards imply all relevant facts found

Source: `final_plan/ARCHITECTURE.md`. Separate available, surveyed-card and raw-inspected coverage; summaries remain lossy.

### R30. Revise: Fixed ingest time/price/throughput copied as measured here

Source: `final_plan/PLAN.md budgeting`. Treat source-report timings as unverified on this machine; measure cold/warm on target server.

### R31. Revise: Prose response plus STATUS line bypasses claim checks

Source: `final_plan/PLAN.md M9`. Structured claims with exact source quotes; renderer uses accepted claims only.

### R32. Revise: Listwise attribution for arXiv 2510.11358

Source: `final_plan/ARCHITECTURE.md research table`. Actual topic is LLM-specific evidence utility; correction in R36.

### X01. Reject: GET /health and optional missing-router startup

Source: `final_plan/PLAN.md M0`. Exactly two routes; docs disabled; missing required route is a startup error.

### X02. Reject: Gold-based runtime aliases, answer caching and hidden access

Source: `all runtime work`. Offline labels stay outside index/query code; no hidden set scraping/reconstruction.

### X03. Reject: Other-track CPU/no-LLM/size constraints

Source: `earlier conversation possibilities`. Only the KB statement controls this submission.

### D01. Defer: Training/fine-tuning and learned fusion

Source: `knowledge-base-plan experiments`. Disabled strict profile pending organizer eligibility and clean evidence; not needed for core.

### D02. Defer: Recursive reader/corrective retrieval

Source: `knowledge-base-plan/reference-config.yaml repair passes`. No retrieval repair in core; fixed DAG and bounded same-source answer checking.

### D03. Defer: Visual sidecar, element vectors, heavier models and full claim compilation

Source: `both research plans`. One-at-a-time bottleneck-driven experiments after core correctness and baseline.

### D04. Defer: Procedural eligibility, live deployment and actual 0.95 results

Source: `requirements versus implementation`. Require real organizer conduct/API/export/evaluation evidence; no design certification.

## Canonical reconciliation

There is one strict profile, ten query stages, one source/citation policy and one evaluation boundary. Reference config, prompts and handoff briefs use those same decisions. An optional research mechanism cannot silently override the core. The source plans remain readable but are superseded for new work.

Implementation is a separate artifact. In particular, if Person 1 has already implemented the original M0/M1–M5 contracts, Person 2 should integrate through the explicit legacy adapter and document compiler gaps rather than pretending the new full metadata/ID/storage schema is already present. A shared route fix may be needed to remove /health. Record that integration delta in the repository handoff.
