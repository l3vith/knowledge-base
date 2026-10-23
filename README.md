# Smart Knowledge Base

Person 1's ingestion track and Person 2's bounded query/evaluation track are integrated. The API exposes exactly POST /index and POST /query. The query path has ten stages, exact source fragments, coverage limitations, structured claim verification, and separate Langfuse observations.

Start with [Track B handoff](docs/TRACK_B_HANDOFF.md) for implementation status and teammate integration notes. [Unified final plan](docs/unified-plan/README.md) reconciles the original architecture and audit; it specifies the target design, including compiler work that is not yet implemented. The original docs remain as legacy references. No 0.95 accuracy result or production readiness is claimed.

## Setup

Python 3.12 is verified locally; the pinned RapidOCR package requires Python below 3.13. Use an isolated environment and install the shared requirements:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the organizer OpenCode key/model and Langfuse credentials locally. Never commit `.env`. OPENCODE_MODEL is also mapped to the shared LLM_MODEL by the launch script. The base URL is configurable; the example follows the supplied evaluator and is not a claim of live model availability. Keep both PRICE fields blank until organizer/model prices are verified; query accounting records unknown cost as null.

```bash
.venv/bin/python -m scripts.serve --env-file .env --host 127.0.0.1 --port 8000
```

POST /index takes multipart `file` (ZIP) and `collection_name`. It blocks until the current ingestion implementation activates the collection. POST /query takes JSON `{"collection_name":"demo","query":"What does the report disclose about capital?"}`. It returns answer, actual source chunks with physical pages, ten four-field trace steps, coverage, resource usage and generation/config identity. Provider failures are HTTP errors; a semantic search miss is separately reported. No public health or documentation routes are added.

Local indexing through the existing CLI:

```bash
.venv/bin/python -m scripts.index_local --src /path/to/documents --collection demo
```

That CLI reads process environment variables; the server launcher loads `.env`. For offline benchmark capture, use the commands in the handoff. The source dataset remains external to the repository.

## Validation

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_embed.py::test_fast_models_load_and_score -m slow -q
.venv/bin/python -m pytest tests/track_b/test_retrieval.py::test_real_fastembed_adapter_counts_unseen_tail_and_scores_windows -m slow -q
.venv/bin/python -m scripts.check_langfuse --env-file .env
```

The default suite uses synthetic model replies, while PDF/SQLite/collection integration uses real adapters. Explicit slow model checks load pretrained weights and can download them. Langfuse connectivity is a separate explicit live check; it emits no fake inference usage. Full-corpus ingestion, live OpenCode answer quality, official dev/holdout scores and provided-server deployment remain to be measured. See the handoff for remaining ingestion compliance work before submission.
