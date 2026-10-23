> Legacy input plan. Use [unified-plan/README.md](unified-plan/README.md) and [TRACK_B_HANDOFF.md](TRACK_B_HANDOFF.md) for reconciled rules and the implementation delta.

# Team assignment — who builds what

Read in this order: **this file → `ARCHITECTURE.md` → your modules in `PLAN.md`** (plus the "Global rules" and "M0 interfaces" sections of PLAN.md).

## The split

| | **Person 1 (Satyaranjan + Claude)** | **Person 2 (teammate)** |
|---|---|---|
| Builds first | **M0 Foundation**: the shared contracts and test fakes. Ready ~20 min after this file is sent; pushed to the shared repo. | Starts immediately on Track B against the M0 interfaces written in PLAN.md (they are frozen). Pull M0 when it lands. |
| Track | **Track A: Ingestion** = M1 Parse & OCR, M2 Segment & boilerplate, M3 Store/registry/CPU models, M4 Cards & identity, M5 Ingest pipeline + `POST /index` | **Track B: Query** = M6 Planning & guard, M7 CPU retrieval & triage, M8 LLM survey & verify, M9 Answer & citation render, M10 Query pipeline + `POST /query` |
| Then | **I1 Integration** (end-to-end test) and **M12** (tuning, write-up, deploy) | **Track C: M11** Evaluation harness, alignment, calibration, reports |

The tracks never import each other's code. Track B sees storage only through `StoreProtocol`, and its tests use `MemoryStore` from `kb/testing.py`. Each track owns its own HTTP route file (`kb/routes/index.py` vs `kb/routes/query.py`). So both of you can work in parallel without waiting on each other.

## Working rules for both
1. Edit only the files your modules own (the table in PLAN.md "Tracks and modules"). Shared M0 files change only via Person 1, after you both agree.
2. Python 3.10+, system install (no venv required). Setup:
   ```bash
   pip install fastapi uvicorn python-multipart httpx "pymupdf==1.28.2" "pymupdf4llm==1.28.2" rapidocr-onnxruntime fastembed langfuse numpy requests pytest
   ```
   Do **not** install `pymupdf4llm==2.0`: it is an empty shim package for pymupdf 2.x.
3. Run tests with `python -m pytest -q`. Tests never call the network or the LLM; they use `FakeLLM`, `HashEmbedder`, `FakeReranker`, `MemoryStore` and `make_pdf`.
4. **Git:** AI agents never commit or push. Humans decide when and how to share code. Until there's a shared repo, exchange code as zip files of your own owned files only. M0 is already included in this package (`kb/`, `tests/`, `requirements.txt`, `pytest.ini`): unzip it into the project root next to `Train/`, then run `python -m pytest -q` (expect 14 passed).
5. **Env vars**, needed only for real runs, never in tests: `OPENCODE_API_KEY`, `OPENCODE_BASE_URL` (default `https://opencode.ai/inference/openai/v1/chat/completions`), `LLM_MODEL` (default `deepseek-v4.1-flash`), `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Never commit keys.
6. Never edit `Train/Train/Evaluation/Evaluation.ipynb`. Never put benchmark questions, answers or training file names into `kb/`.

## LLM budget: $10 total for everything, including the judges' hidden-set run
- **Keys:** put them in `.env` at the repo root (copy `.env.example`). Set `KB_BUDGET_USD`; the code refuses LLM calls once `data/spend.jsonl` reaches it.
- **Budget plan:** ~$1.5 for one real training ingestion (cached afterwards), ~$2.5 for development query/eval runs, **$5 reserved for the hidden test**, $1 buffer.
- **Develop on small question subsets** (5–15 questions), never all 100 repeatedly. The evaluation judge spends from the same key.
- **Tests never spend:** they use `FakeLLM` and never read `.env` (see `tests/conftest.py`).

## Integration points (agree now, so nothing blocks later)
- **`/query` response shape:** ARCHITECTURE.md §5.2. M10 produces it and M11 consumes it.
- **Trace step names (9, fixed order):** `query_planning, routing_guard, candidate_pages, page_survey, element_retrieval, element_triage, element_verification, answer_generation, citation_render`.
- **Calibration hook:** M7 emits `scores` in the `element_triage` trace output when `KB_DEBUG_SCORES=1`.
- **Integration (I1):** happens once both tracks are on `main`. Person 1 runs the real `train` ingestion (~30–40 min) as soon as Track A lands. Person 2 can then run real queries against it.

## Order of work inside each track (all modules except the assembler are independent)
- **Track A:** M1, M2, M3, M4 in any order or in parallel, then M5.
- **Track B:** M6, M7, M8, M9 in any order or in parallel, then M10.
- **Track C (M11):** depends only on M0, so it can start any time Person 2 has capacity.

## Definition of done per module
Its tests in PLAN.md pass, `python -m pytest -q` is green, and any "real smoke/measurement" listed for the module is reported in the merge message (or marked "skipped: no key").
