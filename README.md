# Smart Knowledge Base

For the current failures, measured benchmark evidence, reproduction steps and next-agent repair checklist, read [major_issues.md](major_issues.md).


Person 1's ingestion track and Person 2's bounded query/evaluation track are integrated. The API exposes exactly POST /index and POST /query. The query path has ten stages, exact source fragments, coverage limitations, structured claim verification, and separate Langfuse observations.

Start with [Track B handoff](docs/TRACK_B_HANDOFF.md) for implementation status and teammate integration notes. [Unified final plan](docs/unified-plan/README.md) reconciles the original architecture and audit; it specifies the target design, including compiler work that is not yet implemented. The original docs remain as legacy references. No 0.95 accuracy result or production readiness is claimed.

## Setup

Python 3.12 is verified locally; the pinned RapidOCR package requires Python below 3.13. Use an isolated environment and install the shared requirements:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the organizer OpenCode key/model and Langfuse credentials locally. Never commit `.env`. OPENCODE_MODEL is also mapped to the shared LLM_MODEL by the launch script. The base URL is configurable; the example follows the supplied evaluator and is not a claim of live model availability. Set both PRICE fields: when `KB_BUDGET_USD` is set and a price is blank, every model call is refused, because the spend cap could not be enforced. See [the credit plan](docs/CREDIT_PLAN.md).

```bash
.venv/bin/python -m scripts.serve --env-file .env --host 127.0.0.1 --port 8000
```

POST /index takes multipart `file` (ZIP) and `collection_name`. It blocks until the current ingestion implementation activates the collection. POST /query takes JSON `{"collection_name":"demo","query":"What does the report disclose about capital?"}`. It returns answer, actual source chunks with physical pages, ten four-field trace steps, coverage, resource usage and generation/config identity. Provider failures are HTTP errors; a semantic search miss is separately reported. No public health or documentation routes are added.

Local indexing through the existing CLI:

```bash
.venv/bin/python -m scripts.index_local --src /path/to/documents --collection demo
```

That CLI reads process environment variables; the server launcher loads `.env`. For offline benchmark capture, use the commands in the handoff. The source dataset remains external to the repository.

Source-derived metadata routing, index/contents mapping, zero-model-cost upgrades and validation limits: [Metadata retrieval](docs/METADATA_RETRIEVAL.md).

## Validation

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_embed.py::test_fast_models_load_and_score -m slow -q
.venv/bin/python -m pytest tests/track_b/test_retrieval.py::test_real_fastembed_adapter_counts_unseen_tail_and_scores_windows -m slow -q
.venv/bin/python -m scripts.check_langfuse --env-file .env
```

The default suite uses synthetic model replies, while PDF/SQLite/collection integration uses real adapters. Explicit slow model checks load pretrained weights and can download them. Langfuse connectivity is a separate explicit live check; it emits no fake inference usage. Full-corpus ingestion, live OpenCode answer quality, official dev/holdout scores and provided-server deployment remain to be measured. See the handoff for remaining ingestion compliance work before submission.


### Current low-cost inference profile

The default is **Qwen3.8 Flash with thinking disabled**. Shared and query transports use OpenCode's Messages endpoint for this model; setting only the model ID on the old Chat Completions request is insufficient. `LLM_MODEL`, `ANSWER_MODEL` and `OPENCODE_MODEL` should all be `qwen3.8-flash`. Current verified catalogue rates are $0.15 input / $0.47 output per million tokens; explicit environment prices override defaults.

Page selection now uses the initial source FTS/vector rankings and per-obligation lexical matches locally. `KB_PAGE_SELECTION=llm` opts back into paid page-card surveying. The ten trace stages remain present. Local navigation does not establish factual support; source evidence and final claims still undergo semantic verification.

BGE-small embeddings, MiniLM cross-encoder reranking, SQLite FTS5, extractive page cards, citation validation and arithmetic already run locally. No additional generative local model is required for these steps. Final-stage token reservations include both answer generation and claim verification, using the same model limits as actual calls.

A live Qwen source-span smoke returned HTTP 200, text blocks only, 484 input / 77 output tokens, $0.00010879 reported-token/catalog cost, and 3.36 seconds. This is transport/evidence-selection validation, not a full analytical benchmark or an accuracy claim. See `docs/QWEN_LOCAL_INFERENCE.md` for the shipped scope and remaining validation.

Latest source-selection benchmark and remaining limitations: [extractive writer report](docs/diagnostics/qwen-extractive/REPORT.md). The official evaluator remains unchanged.

Latest analytical routing/coverage repair and measured limits: [repair benchmark](docs/diagnostics/coverage-repair/REPORT.md).

Experimental relational findings and guarded synthesis: [ledger trial](docs/diagnostics/ledger-trial/REPORT.md). Opt in with `KB_ANALYTICAL_WRITER=ledger`; default remains extractive.

Latest **full-pipeline ledger benchmark**: [report](docs/diagnostics/ledger-full/REPORT.md). Analytical recall regressed; ledger remains off by default.

Ledger source-ID repair: [implementation and zero-cost replay](docs/SOURCE_ID_LEDGER_FIX.md). Integrated mode removes the separate extraction call; fresh accuracy is not yet measured.
