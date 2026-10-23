# Relational evidence ledger trial

The pasted proposal addresses a real weakness: flat topic coverage and source-copy assembly can miss complementary results while retaining background. The current code already selects sentence spans, so it is not literally limited to whole paragraphs; the more substantial change is preserving relationships and separating grounding from concise synthesis.

## Corrections to the proposal

- 117,649 points is a TT grid in the supplied paper, not an automatically valid direct-method baseline. Example quantities/experiment labels in the pasted proposal are hypotheses, never runtime facts. No specific benchmark quantities or document/question IDs enter the implementation.
- Only observed, source-anchored cells exist. Taking a Cartesian product of all experiments, methods and metrics would invent unsupported combinations. Unknown setup/method labels remain unknown and cannot establish cross-passage joins.
- Qualifications and baseline quotes consume the same real context/output budgets as findings. They are not free. Same-scope dependency groups are selected together when their source anchors establish the relationship.
- Deterministic substring, ID, quantity and coverage checks do not prove semantic entailment. The final model verifier still checks relationships, modality and qualifications against exact source quotes.
- Extracted/selected cell coverage is not gold-cell recall. True source-faithfulness and focus-precision metrics need independent labelled judgments; no >95% claim is inferred from current verification. Official metrics remain unchanged.

## Implementation

`KB_ANALYTICAL_WRITER=ledger` enables the experiment; the default remains `extractive`. Factual queries never enter the ledger branch. New public endpoints or trace stages are not added. The extraction and synthesis calls run within the existing answer-generation stage.

One additional model call builds a compact ledger from existing verified writer evidence. Each finding has exact source span anchors, original obligation/topic IDs, a discourse role, source-exact experiment/method labels where available, a metric grouping key, an epistemic-mode hypothesis, source-exact values and validated dependency links. General background and implementation noise are quarantined. Duplicate IDs, mixed-document anchors, fabricated values and malformed source references fail closed. Unanchored scope labels reset to unknown.

Observed cells include document, setup, method, metric and epistemic mode. Unknown scopes retain record-specific identities to avoid collapsing unrelated findings. Different values/conditions within one cell remain available. Links only join source-anchored identical nonempty method/setup scopes within the same document. Selection charges every quote and records omissions.

The writer receives filtered records and quotes, not raw paragraph context. Concise synthesis is allowed for this experimental branch; the previous source-copy mode stays available. Every sentence identifies its record IDs; code supplies immutable evidence IDs and quotes. New numeric tokens absent from bound quotes are rejected. Omitted record IDs can be repaired by a source-copy fallback within the existing output budget, with no extra generation call. Remaining missing IDs/values are reported explicitly.

The existing semantic verifier checks the final synthesized claims and source relationships. A record rejected there cannot count toward accepted-cell coverage. All original writer-visible source context remains available for trace/citation output; context is not hidden to improve the official score.

## Validation scope

200 non-slow tests pass, with seven slow tests deselected. Tests cover invented quantities, unknown scopes, cross-method links, duplicate IDs, background quarantine, real dependency budgets, source fallbacks, numeric rejection, rejected-cell coverage and the unchanged factual path.

The live trial uses exactly the same saved 51 writer-context fragments from the preceding analytical case. It reruns ledger extraction, synthesis and semantic verification, then applies the unchanged official evaluator. This isolates the answer stage, saves credit and avoids repeated retrieval/verification. It is not a new end-to-end retrieval benchmark, a full-corpus result or held-out validation. Model outputs and the official judge remain stochastic.

The live trial has a $0.03 hard ceiling including judging and uses only Qwen3.8 Flash with thinking disabled. Results and the default-mode decision are recorded in the diagnostic report after completion.

## Measured result and decision

The guarded saved-evidence trial improved precision/recall from 20.00% / 34.04% to 54.55% / 45.65%. The first unrestricted synthesis trial regressed recall and exposed unsafe merges; it was not promoted. Most guarded claims use short exact-source fallbacks when scope is unknown. See [the full measured report](diagnostics/ledger-trial/REPORT.md). Default remains extractive pending end-to-end and broader validation.

## Fresh full-pipeline follow-up supersedes the isolated improvement

The full run scored 56.25% analytical precision / 15.22% recall at 102.51s. Seven formatted value strings failed exact-source validation, dropping key accuracy and timing findings. This is a recall regression against the default. The default remains extractive; do not promote the ledger based on the earlier frozen-evidence result. [Full report](diagnostics/ledger-full/REPORT.md).

## Source-ID contract supersedes the free-text ledger path

The integrated ledger now selects immutable source IDs inside existing verification calls and renders source-owned text from selected IDs. This replaces free-text value extraction and free synthesis in that mode. The seven formatting failures were recovered in offline replay (20/20 retained), with 217 tests passing and no paid calls. These are contract/regression checks, not new accuracy scores. See [the current implementation](SOURCE_ID_LEDGER_FIX.md).
