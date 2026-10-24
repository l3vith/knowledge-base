# Evidence integrity after the team update

The user's in-progress workspace was preserved with `git stash push -u` before fast-forwarding `track-b` from `1d4ee63` to the team's `origin/main` at `4c5522f`. The stash includes the pre-pull work and remains available; it was not blindly applied over the team's synthesis writer. New fixes build on that writer, routing repairs, table-row source spans and relaxed mechanism verification.

Initial measured repair commit: `8fb1910`. Additional source-budget/request-size repairs described in [the report](REPORT.md) were applied after that live run and are offline-only.

## Changes

- **Qualitative coverage:** an empty number set no longer makes any written sentence carry a qualitative finding. Local matching requires substantive words and preserves negation and projected/measured wording. This is conservative candidate matching, not a semantic entailment score; the final model still checks support.
- **Scope:** source inventory identities include document, parent element, section and absolute source offset. Equal sentences in different documents/experiments remain distinct. Approximate statement deduplication is restricted to the same cited source spans and polarity; equal figures alone cannot establish equivalence.
- **Requested validation:** train/test and sampling details remain available when validation, controls, monitoring or experimental setup is requested. Small rank/dimension results and short qualitative effects also qualify. No benchmark fact/value is embedded in serving logic.
- **Evidence gaps:** uncited gap statements are sent to final verification against the entire inspected writer portfolio. They no longer bypass checking. A gap must concern inspected evidence; it cannot assert absence from the whole paper. All returned gaps have a model verdict, not a guarantee of exhaustive document inspection.
- **Calculations:** code calculates and rounds the result from selected operands and renders the expression. Generated result text cannot contradict the arithmetic. Operand source quotations are attached to the claim even if omitted from the writer's citation list. Existing exact source, unit and semantic checks still apply.
- **Restoration:** restored facts use unused claim IDs after filtered claims. A fact explicitly rejected as background by the final checker is not automatically restored. Other source-restored facts are marked `verification=source`, not reported as independently model-verified paraphrases.
- **Judge audit:** filename and page references decomposed into separate points still trigger citation diagnostics; Anthropic `max_tokens` truncation is recognized. Official formulas and protected organizer inputs remain unchanged.

## Validation

The initial repair passed 258 non-slow tests. Later selection, judge-isolation and budget-error regressions are included in the final suite reported in REPORT.md; slow model tests remain deselected. Tests include unrelated text falsely carrying a qualitative fact, same figures in separate scopes, small ranks/dimensions, validation-dependent trimming, code-owned arithmetic/rounding, a contradicted gap, source-restoration ID collisions, background resurrection and split-citation audit flags. The team's routing/table and retrieval regression tests also pass.

The same 52 saved C18 writer fragments produce 78 fact candidates after these repairs, compared with 64 at `4c5522f`. The old qualitative matcher marked an unrelated sentence as covering a mechanism statement; the new matcher rejects it. This offline inventory replay used zero model calls and does not establish an accuracy or precision gain. More retained evidence can lengthen the answer and increase cost; the live run must measure that tradeoff.

## Boundaries

The team serving configuration selects `synthesis` through the environment adapter; a bare `QuerySettings()` still defaults to `extractive`. This repair does not silently change those mode defaults. Source-ID `ledger` remains another optional mode. The current synthesis writer can paraphrase cited findings; it is not the original strict source-copy architecture. Original source quotations remain exact, and source-copy repairs remain available.

Figure-dependent patterns still require actual image evidence; captions alone cannot support a heat-map interpretation. No new vision model, training, external regulatory corpus or runtime web search is added. General unsourced advice remains disallowed. The 30-second query setting reserves early-stage time but grants final generation grace, so total query wall time can exceed 30 seconds. Passing offline tests does not establish the hackathon's 0.95 targets.

Full ignored local artifacts: `artifacts/post_merge_integrity/`. The fresh results and post-run changes are recorded separately in REPORT.md; neither offline replay is an accuracy benchmark.
