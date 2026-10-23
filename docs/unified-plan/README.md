# Unified final plan: Smart Knowledge Base for Agents

Version **UFP 2.0**, 23 October 2026. **Design and audit package. No retrieval system has been built or benchmarked by this deliverable.**

This is the canonical synthesis of `final_plan/` and `knowledge-base-plan/`, checked against the supplied `Hackathon_Problem_Statement_Final.docx`. Both input folders are preserved. Do not build by mixing instructions from all three packages: use this package for implementation and the source folders for provenance.

## Read order

1. [Architecture](ARCHITECTURE.md): the system, its differentiator, ingestion and ten query stages.
2. [Contracts](CONTRACTS.md): interfaces, source records, API, traces, invariants, persistence.
3. [Build plan](PLAN.md): exact module ownership, dependencies, tasks, tests and release gates.
4. [Compliance](COMPLIANCE.md): requirements mapped to implementation evidence, including ambiguous rules.
5. [Evaluation](EVALUATION.md): unchanged official evaluator, clean tuning, coverage and error diagnosis.
6. [Team assignment](TEAM_ASSIGNMENT.md): two-person, twelve-hour execution and longer development path.
7. [Research review](RESEARCH_REVIEW.md): retained industry evidence, refreshed research, excluded mechanisms.
8. [Merge audit](MERGE_AUDIT.md): what was adopted, corrected, deferred or rejected and why.
9. [Prompts](PROMPTS.md) and [reference configuration](reference-config.json): concrete implementation specifications.

[FULL_HANDOFF.md](FULL_HANDOFF.md) combines all specifications and every module brief into one portable document. [overview.html](overview.html) provides a visual navigation page. The Markdown and JSON specifications govern behavior; diagrams are explanatory.

## Handing work to an agent with no context

Give the agent the whole package and its complete file in [agents/](agents/). Each brief defines the task, owned paths, required reads, inputs, outputs, algorithm, integration seams, tests and completion evidence. These are future work assignments; no agents have been launched and no application code is included here. The lead freezes M0 contracts before parallel implementation.

The proposed future application lives in `smart_kb/`, with Python package `kb/`. Module numbering retains `final_plan`'s M0–M12 and I1 ownership, but interfaces and policies are revised here. The former `core/` naming and earlier nine-stage pipeline are superseded.

## Inputs and reproducibility

Current workspace: `/Users/smit/Downloads/Hackathon`.

- Authority: `Hackathon_Problem_Statement_Final.docx`.
- Source corpus: `Train/Documents/`.
- Offline labels: `Train/Benchmarks/benchmark_100.jsonl`.
- Official evaluator: `Train/Evaluation/Evaluation.ipynb`.
- Proposed application: `smart_kb/`, created only when implementation is authorized and event rules permit.

Paths in application code must be configurable. The Windows paths and installed-library claims in `final_plan` are not facts about this Mac or the organizer server. [Input provenance](audit/input-provenance.json) records hashes of both source packages, the statement, benchmark and evaluator. [Document manifest](audit/README.md) records the supplied PDFs. The local package’s statement extract preserves the text used for requirement checking; [repository audit policy](audit/README.md) keeps supplied content external; the original DOCX remains authoritative.

The combined audit establishes 35 PDFs, 6,970 physical pages and 100 labeled questions. Gold evidence spans a median 39 document-pages and a maximum 125 per question; 68 questions involve multiple documents. This motivates broad evidence discovery but does not prove all gold chunks are necessary or that any proposed pipeline reaches the four 0.95 targets. [Audit details](audit/README.md) and [identity review](audit/README.md) describe extraction gaps and unresolved source aliases.

## Decisions that are now fixed

- Preserve source structure and qualified identity; keep generated navigation text separate from evidence.
- Use a bounded document → page → element pipeline with explicit coverage slots and claim-to-source verification.
- Use pretrained local retrieval models, lexical search and a local vector index as supporting tools.
- Build source-derived page cards by default; use selective OCR and optional budgeted enrichment.
- Expose exactly `POST /index` and `POST /query`; include a four-field step trace and separate required Langfuse records.
- Preserve evaluator and labels; tune on development families and inspect the frozen holdout once.
- Disable training, fine-tuning, recursive retrieval, runtime web access and gold-dependent runtime behavior in the strict submission profile.

Architectural eligibility remains the organizers' judgment. This plan cannot certify event-window conduct, a deployed API, measured performance or successful submission. Those require the evidence listed in the release checklist.
