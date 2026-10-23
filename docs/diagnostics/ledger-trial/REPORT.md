# Relational ledger experiment: results and decision

**Guarded ledger output improved both official answer metrics on this one saved analytical case:** precision **20.00% → 54.55%**, recall **34.04% → 45.65%**. These are still below the target, and this is not a full-corpus or end-to-end result.

Both trials use the exact same 51 saved writer-context fragments from C18 in the preceding single-document benchmark. Generation sees the original question and source evidence only; reference answers enter only the unchanged official evaluator. Source/context SHA-256: `8a96e660dee0567472f9b24c550540120f944fc06bb7841bc8a73f2c4fb530b8`. Original benchmark/evaluator inputs remain unchanged.

## What applies from the pasted proposal

Typed source-anchored findings, observed experiment/method/metric cells, discourse-role filtering, attached qualifications, bounded output and record-level omission checks are useful here. The experiment implements these behind `KB_ANALYTICAL_WRITER=ledger`.

Some proposed details are unsafe: 117,649 points is a TT grid, not an automatically valid direct baseline; 300 calls and under-five-minute construction cannot be merged across methods; arbitrary Cartesian products invent missing cells; qualifications cost real tokens; deterministic substring checks cannot prove semantic entailment. No benchmark quantities or setup labels are hardcoded into the implementation.

## First trial: why unrestricted synthesis was not promoted

The initial ledger variant scored **50.00% precision / 20.45% recall**, with four accepted claims / 1,272 rendered characters. Ledger extraction, synthesis and final checking took **71.11s** on the saved evidence. It dropped important results and merged distinct under-five-minute and under-eight-minute records. A mandatory monitoring claim also passed the model checker despite being stronger than its source. Therefore this variant was not enabled by default.

Extraction accepted 11 records, with several source/schema rejections and many unanchored setup/method labels reset to unknown. Better structure alone did not make this small model reliably extract or synthesize the right relationships.

## Guarded follow-up

The follow-up reused the already-paid extraction AND synthesis outputs; no new extraction or synthesis call was made. Safe schema aliases retain source-anchored findings without inventing modality; invented values still fail. Synthesized multi-record statements are blocked unless their nonempty experiment/method scopes are demonstrably identical. New mandatory wording and lost projected-mode wording are rejected. Unknown scopes remain separate, and valid short exact-source fallbacks repair omitted/rejected records under the same answer budget.

The guarded answer has **17 accepted claims / 3,588 rendered characters**, official answer precision **54.55%**, recall **45.65%**, context precision **100%**. The official context-recall count ratio is **104.08%** because its unchanged count-based formula can exceed 100%; it is not exhaustive semantic recall. The context is unchanged across variants.

The offline replay explicitly removed the merged timing range and invented mandatory-monitoring wording with zero paid calls. Most claims in the guarded answer use the exact-source fallback rather than free synthesis; the improvement supports finding-level filtering and relationship guards, not a claim that unrestricted paraphrasing is better.

Only semantic verification was timed live in the follow-up: **15.56s**, excluding the reused extraction/synthesis and official judging. Do not compare this with a full query's latency. Final selected-cell coverage is relative to model-extracted records, not gold-cell recall. The extraction can still omit relevant findings; source faithfulness and focus precision have not been independently labelled.

## Cost, tests and rollout

All trial and follow-up costs including judging: **$0.01185127 computed**, **$0.01552551 conservative upper bound**, below a shared **$0.03** ceiling. 12 paid calls; 0 thinking blocks. No automatic inference retries. Only Qwen3.8 Flash was used.

**200 non-slow tests passed; seven slow tests deselected.** They cover source fabrication, method/scope merges, duplicate IDs, quote budgets, background quarantine, modality guards, fallback coverage, numeric checks, factual-path compatibility and reservation of the extra ledger call.

The default remains **extractive**. The ledger branch is available via `KB_ANALYTICAL_WRITER=ledger` for explicit experimentation. A fresh end-to-end run with the extra extraction call, unchanged budgets, other documents and held-out questions remains necessary before making it the default. Production-budget behavior and total latency have not been validated by this frozen-evidence trial. The call budget now reserves space for the extra extraction call; the existing token/cost limits still apply and may visibly omit work or reject a call.

See [implementation notes](../../LEDGER_TRIAL.md) and [machine-readable diagnostic](summary.json). Full local extraction, writer and verifier artifacts remain under `artifacts/ledger_trial/` and `artifacts/ledger_guard_trial/`.
