# Two-person execution and ownership

Person 1 owns M0 foundation, M1–M5 ingestion/storage/models, I1 integration, and M12 deployment/write-up. Person 2 owns M6–M10 query processing and POST /query, then M11 offline evaluation. Shared contracts must be agreed before integration. Person 2 must not replace Person 1's unfinished storage with a competing production implementation; use protocols, an explicit compatibility adapter and test fakes.

## Twelve-hour schedule

| Time | Person 1 | Person 2 | Gate |
|---|---|---|---|
| 0:00–0:30 | Freeze M0 contracts, environment, provider/tracing checks | Read contracts, build query fixtures and protocol adapters | G0 shared seams |
| 0:30–3:00 | M1–M4 native/OCR extraction, structure, stores, cards | M6–M9 obligations, retrieval, survey, verification, answer | Unit/contract evidence |
| 3:00–5:00 | M5 blocking index and atomic collection activation | M10 executor/API and M11 unchanged-evaluator adapter | G1 synthetic archive flow |
| 5:00–7:00 | Cold corpus ingestion and target-server measurements | Real-model smoke, dev baseline and failure diagnosis | G2 provider/Langfuse |
| 7:00–9:30 | Fix source/identity defects, support paired tests | Development-only ablations and query fixes | Comparable manifests |
| 9:30–10:30 | Freeze deployment/config and run integration | Freeze candidate; inspect holdout once | No holdout tuning |
| 10:30–12:00 | Write-up, API reachability, ingest estimate and submission | Trace export, metrics/failures and checklist | G3 release evidence |

These are proposed allocations, not measured completion times. If time is tight, cut optional enrichment, alternate models and UI. Preserve source fidelity, strict routes, trace/accounting, collection isolation and honest error behavior. A two-person team does not become eligible for extra human members because the module list is long. Organizer rules determine AI assistant/delegation eligibility.

For development without a time constraint, complete the same correctness gates first, then add parser comparisons, retrieval profiles and visual sidecars as separate measured experiments. Avoid building a large stack before identifying the bottleneck.

Use a separate branch per person and integrate through reviewed commits. Keep ownership boundaries visible. Shared-interface changes require updating contracts, fakes and both tracks together. Every completion report includes files, tests, actual live checks and remaining limitations. Mock tests cannot certify real model or export behavior.
