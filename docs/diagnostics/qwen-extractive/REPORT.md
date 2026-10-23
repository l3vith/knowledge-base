# Extractive writer: one-document rerun

Implementation **da947523f3524d92838491ee64551a15e0596392**, Qwen3.8 Flash, thinking disabled, local page selection. Same public factual C31 and analytical C18 questions on the reused 24-page `2012.07440v3.pdf` collection. No indexing, gold lookup, paid retry experiment or evaluator modification. This is a development smoke, not whole-corpus/held-out accuracy.

## Changes under test

The model selects evidence and source sentence IDs with one explicit supported obligation ID. Code reconstructs original statement wording and exact support quotations. It refuses generated paraphrases, unknown IDs, nonconsecutive spans and unsupported mappings. Display-only cleanup normalizes italicized thousands commas while raw source/quotes remain immutable. Literal legacy adapters remain compatible; their free paraphrases are rejected. All-claims-rejected output now says source validation failed rather than claiming retrieval found nothing.

The answer writer is told not to paraphrase or decompose source statements into separate atomic facts. **The supplied official evaluator still performs its original point decomposition.** Disabling that would change the scoring method and make the new metrics incomparable.

## Factual C31

Status **answered**, latency **21.82s**, **one** returned passage. Actual answer:

> It is a Monte Carlo based pricing routine; 60,000 paths were used to generate the prices in our tests. [2012.07440v3.pdf p15]

Official answer precision **1.0**, answer recall **1.0**, context precision **1.0**, context recall **1.0**. All reference points matched; no extra/missing points were returned by the judge. One selected claim passed final semantic verification.

Previous Qwen factual run: 19.13s and answer precision/recall 0.6667. This run improves the measured quality of this example, **not latency**. Do not infer general 100% accuracy from one public question.

## Analytical C18

Status **partial**, latency **118.22s**, **24** returned writer-context passages. The model produced **18** valid source selections; there were **zero selection validation rejections** and **all 18 passed final semantic verification**. The earlier ten-empty-obligation-ID failure and altered quotation failure did not recur. The result contains a substantial answer rather than the generic abstention.

Official answer precision **0.2592593**, answer recall **0.8888889**, context precision **0.8750**, context recall **0.4285714**. The previous run had answer precision/recall 0.0.

These scores do **not** satisfy the required 0.95 targets. Exact source support is different from selective relevance to the reference answer. The answer includes background and implementation details outside the reference's requested facts; the judge labels 40/54 response points extra. It reports 40/45 reference points matched. Its point matching can be inconsistent, so report these values as raw judge outputs, not as an independently audited 88.9% semantic coverage guarantee. Do not change the evaluator or hide writer context to improve them.

The local path retrieved/verified **89** candidates, retained **54** passages and supplied **24** to the writer. **30** verified fragments were omitted by context budget, producing the explicit partial limitation. Planning/routing variation means these are not identical candidates to the preceding run's 114, so attribute performance cautiously. Semantic checking of 18 claims took **21.09s**, which the failed earlier analytical run skipped. Latency remains close to the 120-second production deadline; this diagnostic used the same 180-second allowance as earlier smokes.

Next work is analytical evidence novelty/sufficiency and shorter query-relevant source selections, preserving all essential qualifications and facts. Copying source statements prevents paraphrase errors but does not by itself remove irrelevant or redundant source facts. The P0 generation failures are repaired on this case; analytical precision, context coverage and latency remain open.

## Validation, costs and integrity

Offline: **144 passed, 7 slow tests deselected**; `git diff --check` passed. Tests cover source-ID reconstruction, ignored invented text, empty/unknown obligation IDs, legacy paraphrase rejection, nonconsecutive spans, numeric display cleanup and truthful validation-failure wording.

Live: **27 paid calls**, known reported-token/catalog cost **$0.01217614** including judging; conservative admission ledger **$0.01459659**, below **$0.05**. **0 failed model responses** and **0 thinking blocks**. Benchmark and original evaluator hashes unchanged: **True**.

Portable statistics and stage traces are in [summary.json](summary.json). Full local answer/context/call ledgers are under ignored `artifacts/single_document_qwen_extractive/`. No credentials, raw source PDFs, gold benchmark dataset or complete analytical source-excerpt answer are included in this portable directory. The official context recall is its supplied chunk-count ratio, not a semantic coverage measure.
