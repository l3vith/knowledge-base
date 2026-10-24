# Next iteration: evidence requirements, source relationships and checked analysis

Status: architecture and implementation blueprint, not an implemented or benchmarked accuracy gain. This incorporates the user's supplied four-bottleneck audit, corrected against the first-pass C26/A20/A21/C32 artifacts. No source/gold-specific rule or model change is authorized by this document alone.

The highest-confidence engineering direction is to replace sentence eligibility as the answer's authority with a task-specific evidence worksheet. Keep exact source anchors, deterministic arithmetic, local retrieval, automatic metadata, collection isolation and final claim checks. A complete global knowledge graph, retriever training, a new database and unrestricted agent loops are unnecessary for this iteration.

[Architecture diagram](architecture.svg) · [Editable Mermaid](architecture.mmd)

## 1. Evidence from the measured run

Measured code: `9eb518c`. ETF C26 answer precision/recall 11.76%/25%; Bhadora A20 52.63%/30.91%, A21 11.11%/2.04%; FDIC C32 0% on all metrics. Full source provenance and judging caveats are in [the first-pass report](../diagnostics/three-unseen/REPORT.md).

- C26/A20/A21 fact inventories contained 20/28/10 candidates, and all of them fitted the source budget. The 8,000-character selection cap did not remove candidates on these three queries.
- C26 and A20 rejected 15 and 33 draft statements with `finding_outside_selected_inventory`. These are deterministic whitelist rejections. Their seven and twelve final-claim rejections are a separate stage; their validity must be examined individually rather than assumed excessive.
- A21 requested cross-section consistency checks. Its answer quoted audit assurances and did not systematically reconcile figures or compare assertions across the named sections. Its low context recall also indicates evidence retrieval needs repair.
- C32 retrieved 72 candidate elements, checked 16, kept none and left 56 unchecked. Its reference answer says the requested aggregate FDIC statistic is not established, and cites explanatory FAQ passages. A numeric-only support gate cannot produce that answer.
- Context recall above 100% is an artifact of the official count ratio. It cannot establish complete evidence coverage.

## 2. Changes ranked by expected benefit

### First: make the inventory advisory and verify claims by their evidence type

Expected effect: answer recall, and precision if paired with query relevance checks.

Remove `finding_outside_selected_inventory` as a reason to reject an otherwise grounded, query-relevant statement. A regex/number/word-overlap inventory may suggest omissions, rank candidate evidence, and expose coverage, but must not decide which source-supported facts are legally answerable. Keep the requirements for valid source IDs, exact source quotations, correct scopes, units, periods, quantities, negation and measured/projected mode.

Use three explicit claim contracts:

1. Reported finding: directly supported by exact source evidence. No outside factual additions.
2. Derived calculation: source-owned operands, proven scope compatibility, code-computed result, units/formula/rounding and citations to both inputs.
3. Interpretation/proposed control: explicitly labelled reasoning, supported premise IDs and visible assumptions. The source supports the premises; the proposed action must not be attributed to the paper or a regulator without explicit source support.

A rejected analytical phrase should produce a structured reason. If its factual core is still useful, recover the exact original source sentence, preserving qualifications and task relevance. Do not automatically restore a statement marked background or place an unsafe inferred comparison back into the answer. A rewrite is a new claim and must be checked; one bounded same-source repair is the maximum, not a general retry loop.

Precision risk: removing the whitelist alone can admit irrelevant content. Replace it simultaneously with task relevance and redundancy checks, not an unrestricted writer or restoration of every source sentence.

### Second: compile operations and build a query-time evidence worksheet

Expected effect: both answer precision and recall; particularly cross-section comparisons, audits and analytical critiques.

A planner obligation like “look for inconsistencies” is insufficient. Compile the required operations and inputs. Examples of operations are lookup, compare, reconcile, evaluate a stated result, inspect a boundary/assumption and establish that a requested item remains unknown. Preserve the original query and literal requested scopes; generated tasks are hypotheses checked against it.

For an audit query, operations can include comparing repeated financial metrics across named sections, reconciling statement arithmetic, and comparing policy assertions with corresponding notes. Derive candidate metrics and note categories from source headings, row labels, cross-references and query terms. Do not hardcode the Bhadora discrepancies or blindly run a fixed list of seven audit categories for every document.

Each worksheet row must retain:

- Task/requirement ID and operation.
- Exact source IDs, document, physical page, section and original offsets.
- Source role: assertion, numeric result, policy, qualification, counterevidence or explanatory support.
- Entity, metric/row label, period, currency/unit, standalone/consolidated basis and relevant legal/experimental scope; unknown values remain unknown.
- Linked cells/passages, required conditions, source assertions, computed result where applicable, and status.
- Status: supported, corroborated, contradicted, incomparable, unresolved or not established by inspected evidence.

The worksheet is constructed at query time from selected source evidence. It is not a second corpus populated from benchmark answers or invented canonical facts.

### Third: retrieve by section and compare related evidence together

Expected effect: context recall and answer recall, with improved precision from scope checks.

When the question names sections or comparison axes, create independent retrieval queues for each source role/section. Use existing PDF outlines, validated TOC ranges, table captions, cross-references, sparse search and local embeddings/reranker. Add bounded global fallback for missing roles. A source paragraph need not contain the word “inconsistent” to be an input to a consistency test.

For tables, carry the value together with its original row label, column/year header, unit/currency and relevant footnote. Equal numeric strings do not establish the same quantity. A financial comparison must not align different fiscal periods, entity bases or statutory scopes just because its rows share a label.

Before judging a relation, present the matching pair/triplet together. For example, compare an assertion in the directors' report with the corresponding auditor annexure and note. First check comparability; then assess corroboration, contradiction or unresolved ambiguity. “No transaction under a specified statutory category” and a broader accounting related-party disclosure are not automatically contradictory. A question asking for inconsistencies does not establish that a contradiction exists.

For scientific papers, link each result to its experiment/method/data split, measured versus projected status and relevant assumptions. This is the same relationship mechanism, not a separate hand-coded scientific QA system.

### Fourth: distinguish no direct answer from no useful evidence

Expected effect: factual answer recall and meaningful context precision/recall for unsupported-premise questions.

Replace numeric-only stopping with a bounded recovery decision:

1. Run the initial factual verification tranche.
2. If no direct answer is found, inspect source-supported explanatory context, counterevidence and qualifications. Search for the missing task input, not only the original phrasing.
3. Use at most two additional targeted batches within time, call and monetary limits. If already retrieved candidates are promising, consume them first; otherwise allow one targeted retrieval repair. All attempts are charged and traced.
4. A direct answer can finish with minimal context. If the premise remains unsupported, explain what the inspected source does establish, with only semantically verified relevant context. If useful support is still absent, return an honest unresolved/abstaining response.

Source-declared acronym expansions should augment search terms: extract definitions such as “full phrase (ACRONYM)” from the indexed source and preserve the original query. A small general domain lexicon may be evaluated separately, but no benchmark-keyed phrase replacements are allowed. Ambiguous acronyms remain alternatives rather than authoritative entity mappings.

Always expose inspected, remaining and budget-limited candidate counts in public coverage metadata. Do not assert whole-document absence from a partial scan. For C32 specifically, the correct development behavior is a source-backed explanation of the FAQ's inability to establish the requested aggregate statistic, not a forced percentage or an arbitrary top-k context dump.

## 3. Citation changes and evidence appraisal

Keep each distinct supported claim adjacent to its code-rendered citation. Split a statement only where its factual clauses depend on different evidence or scopes; preserve the original source quotations and their connected qualifications. No mandatory LLM decomposition of every sentence and no paraphrasing of quotations.

The provided evaluator has no deterministic citation parser with a special token pattern to satisfy. It delegates answer decomposition/matching to an LLM. Existing filename/page brackets can be present and still be lost by the judge. Treat that as an audit flag; do not change official formulas, fabricate attributions, claim formatting will eliminate it, or rejudge until a score improves.

Separate final verification of factual support from verification of task completion. Source-faithful claims alone do not establish that the answer performed a requested comparison. Check the final answer against resolved worksheet tasks and explicitly disclose material unresolved tasks. A scoped evidence-gap claim is checked against the inspected portfolio; it never bypasses verification.

## 4. Bound compute and avoid model changes as the first remedy

Qwen3.8 Flash remains thinking-disabled as explicitly configured by the user. GLM 5.3 Flash remains an independent low-reasoning judge. Unused room under a maximum dollar ceiling is not a requirement to spend it.

Selective thinking is an optional later ablation, not an accepted immediate fix or an authorized default switch. The supplied “less than $0.005” and “eliminates citation stripping” claims are unmeasured. Only investigate reasoning settings after task structure, scope alignment and hard filtering are repaired, using a fixed small comparison and logged reasoning/output costs.

Prefer one bulk evidence assessment, one relation/operation assessment when necessary, one writer and one final support/coverage check over many independent writers and repeated checks. Grouping is governed by bounded payload size and task inputs; no fixed call-count promise can replace actual measurements. Preserve source qualifications when compacting context. Keep exact writer-visible source context in the returned chunks and trace; never inflate or selectively hide it to change context metrics.

Keep current aggregate/per-query admission guards and accounting for in-flight requests, failed attempts and unknown usage. No transport retry or token escalation for GLM judging. Only a schema/truncation failure may trigger the existing bounded split; a spend denial never does.

## 5. Suggested data contracts

```json
{
  "requirement_id": "T1",
  "operation": "compare",
  "description": "Original-query-linked evidence requirement",
  "source_roles": ["section assertion", "corresponding note"],
  "required_fields": ["entity", "metric", "period", "unit", "basis"],
  "inputs": ["source-span-or-cell-ID", "source-span-or-cell-ID"],
  "scope_status": "unresolved",
  "result": null,
  "status": "unresolved",
  "missing_inputs": ["period"]
}
```

The compiler may propose labels and operations. Code validates that input IDs resolve to actual source, arithmetic uses cited operands, required scope is compatible, and missing fields stay visible. A model cannot populate a numeric result by inventing a value or rewrite an evidence quote.

## 6. Implementation sequence and code ownership

1. **Contracts and soft inventory:** extend `kb/query/types.py` and requirements/planning records with tasks and evidence roles; make the inventory advisory in `facts.py`/`answer.py`. Preserve old serialized fixtures with defaults. Add task-grounded relevance checks before removing the whitelist.
2. **Negative evidence and bounded recovery:** repair `screen.py`/`pipeline.py` stopping, add explanatory/counterevidence support roles, expose unchecked counts, and use source-derived acronym hints in `candidates.py`. Verify legitimate zero-context abstention still works.
3. **Worksheet and pairing:** add a query-owned worksheet module; recover headers/footnotes through existing source navigation; add section-stratified retrieval and scope-aware pair verification. All unknown/mismatched scopes fail closed on comparison.
4. **Checked analysis and final coverage:** generate from worksheet results; reuse code-owned arithmetic, labelled implications and immutable source citations. Remove mandatory restoration of every candidate fact. Add a final required-operation coverage audit and at most one bounded same-source repair.
5. **Measured ablations:** first compare selection-only, then recovery, then relational tasks/synthesis. Keep question/doc scope and judge fixed within a comparison. Never bundle model/thinking changes with architecture changes and attribute the result to one cause.

These are internal changes. Preserve the two public routes, collection isolation, the ten public trace stages and their four-field schema. Additional task/worksheet detail belongs inside stage outputs, saved artifacts and nested Langfuse spans, not new public routes/stages. Organizer evaluator and original corpus remain protected and unchanged. No training or runtime web/gold lookup.

## 7. Acceptance and measurement

Offline regression cases must cover:

- A relevant qualitative statement excluded by the old numeric/phrase heuristic survives with exact source support.
- Zero-hit initial screening followed by relevant explanatory/counterevidence support; exhaustion leaves honest unchecked/budget metadata.
- No arbitrary unverified top-k context is returned merely to avoid zeros.
- Same metric in two sections agrees; a real discrepancy is detected; different periods/units/legal categories yield incomparable rather than a false contradiction.
- Financial arithmetic uses the correct year and row/column/unit provenance; calculated text cannot disagree with computed values.
- A supported interpretation is labelled; an unsupported number, normative authority or causal assertion is rejected.
- A source-faithful answer that omits the requested reconciliation remains incomplete.
- Exact quotes, qualifications, ten-stage traces, Langfuse, collection isolation and admission limits remain intact.

The four recently exposed queries are now development cases, not an untouched holdout. Frozen saved evidence is useful for cheap diagnostics, but an offline replay is not end-to-end accuracy. After implementing the iteration, perform one capped development comparison, preserve first-pass scores, then validate on additional previously untested documents selected before scoring. Report all four official metrics per query/document, query/ingestion time, calls, cost, omissions and judge flags. Context recall above 100% must not be claimed as semantic completeness.

No numeric accuracy improvement or likelihood of reaching 0.95 can be promised from four cases. The strongest evidence for prioritization is the observed information loss and missing operations, not a measured win for this unimplemented design.

## 8. Disposition of the supplied audit

- **Accept:** bounded zero-hit recovery; surfaced unchecked counts; section-stratified retrieval; comparable paired evidence checks; source-grounded analytical verification; source-backed repair of a failed formulation; clear adjacent citations.
- **Modify:** acronym expansion must preserve ambiguity and be sourced/general rather than benchmark-keyed. Inspect budgeted candidate tranches and relevant negative/explanatory evidence; do not scan indefinitely. Draft whitelist and final semantic verifier are distinct failure stages.
- **Reject:** always return fallback passages just to avoid zero metrics; assume the FDIC statistic exists at ranks 17–72; interpret count-based context recall as complete retrieval; broadly relax factual support; assert a special deterministic citation-parser format.
- **Defer:** thinking-enabled planning/synthesis and its claimed price benefit. It changes the user's configured model policy and needs a separate measured experiment, not an unexamined default change.
