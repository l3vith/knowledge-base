# Team integration and GLM-judged development run

The team update was pulled from `origin/main` at `4c5522f`, with all pre-pull changes and untracked source files preserved in a stash. New implementation work continues on the team's synthesis writer. The stash remains available; it was not applied wholesale over newer code.

## Fresh live results

Measured query implementation: **`8fb1910`**. Existing index reused for one 24-page document, `2012.07440v3.pdf`. Qwen3.8 Flash answers with thinking disabled; **GLM 5.3 Flash** judges the saved answers using low reasoning effort, as explicitly requested. GLM 5.3 Flash requires reasoning; this report does not claim its thinking was disabled. Exact organizer evaluator/decomposition/formulas are unchanged. Transport limits were capped at 4,000 output tokens, with 2,000 for chunk judgments; no GLM retries or escalation.

- **C31 factual:** 15.06 seconds within the query response (15.61 seconds including driver overhead), one passage, 125 characters; correct **60,000 paths**, page-15 citation. Official GLM answer precision **0%**, recall **100%**, context precision/recall **100% / 100%**. GLM marked its single benchmark point matched and all three answer points extra. This is flagged as contradictory matching, not interpreted as a wholly incorrect answer. Qwen's earlier judgment of the identical saved answer was 100% / 66.67%; it is retained historically, not substituted for GLM's requested score.
- **C18 analytical:** 75.97 seconds within the query response (76.50 seconds including driver overhead), 64 returned fragments, 17,349 characters; status **partial**. Official GLM answer precision **34.78%**, recall **82.76%**, context precision **100%**, context recall **130.61%**. The raw count-based context-recall formula can exceed 100%; it is not bounded semantic coverage. GLM decomposition dropped citation details, separately flagged by the audit.

This is a public development example, not held-out accuracy or evidence of meeting 0.95 targets. Earlier ledger/Qwen results used different writer/deadline/judge settings, so they are not controlled comparisons.

## What remained wrong in the measured query

The writer inventoried 89 facts and produced 123 draft statements. Many claim checks could not complete under the shared five-cent admission cap. Only 23 statements received an accepted model verdict; source restoration supplied 73 original-source facts. The 100 unaccepted draft statements include uncompleted/budget-refused checks and must **not** be described as 100 hallucinations. Budget refusals were treated as splittable writer/check errors, generating extra local attempts. The result remained verbose and included secondary content. Final generation has grace beyond the 30-second early-stage setting, so total latency exceeded 30 seconds.

## Additional fixes after that live run — offline only

1. A shared **8,000-character source budget** selects distinct findings across requested topics, protecting limitations before extra result detail. Only selected findings are mandatory for restoration. No blanket budget increase.
2. Sampling/train-test details remain when relevant to validation; a controls request no longer preserves every grid-construction recipe. Findings outside the chosen inventory are rejected except for a tightly limited explicit short-answer section. Unsupported supervisory authority cannot be introduced as a reported finding.
3. Private `_group` retry metadata, which duplicated full claim/source data in verifier requests, is stripped before sending to the model. Local splitting still retains it.
4. Only schema/truncation errors may split once; spend-cap, transport and other errors no longer trigger splitting as if their output were malformed.
5. GLM judging is independently configured with `OPENCODE_JUDGE_MODEL=glm-5.3-flash` and `JUDGE_REASONING_EFFORT=low`. Ingestion and answers remain pinned to Qwen. GLM pricing defaults reflect the live OpenCode catalogue, and this judge has no automatic retries/token escalation.

Offline on the same 64 saved writer fragments, the refined selector retains **60 of 84 candidates** within **7,973 source characters**, with candidate hits retained for all nine requested topics. These topic hits are lexical selection hypotheses, not verified answer coverage. The actual regenerated answer length, latency and accuracy for these last changes have **not** been measured. No additional paid calls were made after the GLM judging.

## Spend and integrity

Known reported-token/catalog cost across queries and both judge phases: **$0.032465984**. An interrupted Qwen C18 judge request has unknown billed usage, so **$0.0058334** is conservatively reserved rather than silently counted as free. Aggregate conservative upper bound **$0.04538086**, under **$0.05**, includes that reserve. These calculations are not a billing receipt. Eight GLM judge requests completed; neither answer was regenerated for the model switch.

Both answers retain all ten required trace steps. Protected organizer benchmark/evaluator hashes stayed unchanged. Full local request/response/cost provenance is ignored under `artifacts/post_merge_integrity/`; [portable summary](summary.json) excludes raw reference answers and full source chunks. [Implementation details](IMPLEMENTATION.md), [initial offline replay](offline-replay.json), [post-run bounded selection](bounded-replay.json).

## Final offline verification

**263 tests passed; seven slow model tests deselected.** This final suite includes the post-run bounded selector, shared-topic coverage, source-scope preservation, verified gaps, generated calculation output, removal of duplicated private verifier data, no split on spend refusal, independent GLM selection and no GLM token escalation. The suite also retains the team routing/table and qualitative-mechanism regressions. No paid accuracy score is assigned to the final post-run changes.
