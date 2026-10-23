# Requirements and compliance gates

Authority is the supplied Smart Knowledge Base statement, not another track's rules. This is design-level coverage; deployed behavior and procedural conduct require separate evidence. The source extract and hashes are in audit/. Architecture eligibility remains a judging decision.

| Requirement | Design treatment | Release evidence |
|---|---|---|
| Beyond standard RAG; §3–4,6–7 | Qualified identity, source skeleton, finite coverage execution and claim provenance beyond supporting search/rerank | Working mechanism and paired baseline ablations; naming a pipeline is insufficient |
| Automatic metadata and unorganized source dump; §6,11.1 | Content-derived fields with anchors, unknowns, generic hierarchy fallback | Renamed/reordered sources and previously unindexed collection |
| Hidden separate corpus; §11.1,11.4 | No fixed companies/categories/file order/question IDs | Cold second collection and no gold/runtime imports |
| Grounded answer and used document/page chunks; §3,11.3 | Exact source fragments, physical pages, full writer-visible portfolio and claim support | Source-round-trip and citation-dependency checks |
| All four metrics ≥0.95; §4,9–10 | Unchanged evaluator plus diagnostic coverage | Actual per-row/aggregate run; currently unmeasured |
| Cost includes final generation; §3,9 | All attempts, retries, synthesis and verification accounted | Usage/cost/latency reconciliation with pricing provenance |
| Python 3.10+, API client, OpenCode key; §5 | Python 3.11 target, configured provider and live capability check | Target-server lock manifest and real model smoke |
| Vector optional in §5, expected in §6 | Local FAISS page-window index used as supporting infrastructure | Validated dimension/IDs and real retrieval |
| Required Langfuse every query; §5,8,11.4 | Nested observations plus durable attempt ledger; failures visible | Real trace IDs, flush/export and request reconciliation |
| Exactly two public routes; §8,11.3 | POST /index and POST /query only; docs disabled | Enumerate every method/path; no /health route |
| ZIP+collection, success after completion; §11.3 | Safe extraction and required compiler/index validation before atomic activation | End-to-end blocking index and failure injection |
| Isolated multiple collections; §11.3–11.4 | Generation binding, scoped stores/caches, old reader safety | Concurrent second-collection/reindex/restart tests |
| Realistic declared ingest time; §11.3,16 | Cold target-server measurement by page type | Measured report, declared expectation and variance |
| Query input and required trace; §11.3 | collection_name/query and ten ordered steps, each exactly four fields | HTTP contract tests and actual response artifacts |
| Unmodified official evaluator; §11.2,13 | Hash protection, unchanged definition execution | Pre/post hashes and runner audit |
| No hidden access or answer hardcoding; §7,13 | No runtime web/gold lookup or benchmark answer cache | Import/file-access audit and source-only runtime |
| No prebuilt core; §13 | Core work provenance within event window | Commit/work history and team conduct |
| Two people, twelve hours; header,§13 | Explicit Person 1/2 ownership and time plan | Team eligibility and deadline compliance |
| Repository, live server, traces, short write-up; §8,16 | M12 release checklist | Real URLs, reachable routes, export and 2–3-page maximum write-up |

## Conservative boundaries

The statement says “Training or fine-tuning a foundation model from scratch” is out of scope. It does not clearly define adapting an existing retriever. Strict defaults disable all training/fine-tuning to avoid assuming permission. Pretrained inference, automatic metadata, source processing and deterministic calculations proceed. Any adaptation needs an organizer ruling and clean event/evaluation boundaries; research recipes are not authorization.

The brief excludes polished frontend work from the required scope but calls a UI a bonus. It does not categorically forbid a simple interface. Build API and evidence first. The overview in this package is a planning aid, not a competition product UI.

The brief does not explicitly authorize extra human collaborators, AI assistants, subagents, pre-event helper code or prepared planning artifacts. Do not import permission from Decide/CodeGuard or another event. The user's current instruction authorizes work in this workspace, but competition eligibility of how/when it is produced is still an organizer conduct matter. Record actual provenance rather than claiming certification.

An internal 120-second query deadline, CPU profile, model choice and memory budget are team defaults. There is no universal 100-ms CPU limit, single-model restriction, no-LLM rule or 500-MB limit in this KB statement. No fixed ingestion timeout is specified; organizers choose a buffered timeout from the team's declared estimate.

## Forbidden shortcuts and repaired risks

Do not answer from generated cards alone, index gold chunks as source documents, call a missing-year substitution the requested answer, invent source aliases, inflate chunks for count-ratio recall, or hide writer-visible context. Do not label API/provider failure as corpus absence. No open-ended retrieval repair or ReAct loop is enabled. The optional same-source answer repair is bounded and cannot retrieve.

A local no-op tracer is useful in deterministic tests but does not satisfy Langfuse submission requirements. Unknown provider usage or price remains null, with an explanation. Startup success does not prove export success. Mock tests do not establish model accuracy, OCR fidelity, real latency or live endpoint availability.

The event write-up must describe the implementation actually shipped, including limitations and measured results. If a qualitative architectural requirement is disputed, organizer judgment controls; this package cannot guarantee acceptance or a win.
