"""Private query defaults plus a non-mutating adapter for Person 1 Settings."""
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class QuerySettings:
    query_max_chars: int = 32000
    router_max_docs: int = 12
    router_max_cards: int = 120
    max_obligations: int = 64
    page_selection_mode: str = "local"
    local_pages_per_doc: int = 5
    short_doc_pages: int = 30  # analytical: every page of a document this short is eligible for local ranking
    endmatter_hits: int = 8  # conclusion/limitation elements searched for and verified first
    metadata_navigation_enabled: bool = True
    metadata_dependency_elements: int = 4
    metadata_ranges_per_aspect: int = 2
    metadata_pages_per_range: int = 2
    metadata_fallback_pages: int = 3
    metadata_element_fallback_hits: int = 8
    survey_batch_cards: int = 40
    survey_cards_total: int = 400
    verify_pages: int = 200
    lexical_net_pages_per_aspect: int = 5
    element_hits_per_aspect: int = 40
    escape_pages: int = 20
    max_ce_pairs: int = 400
    verify_batch_elements: int = 8
    factoid_initial_elements: int = 8
    factoid_reserve_elements: int = 8
    factoid_recovery_batches: int = 2  # extra targeted tranches; never an unbounded scan
    task_role_hits: int = 4
    dynamic_evidence_selection: bool = True
    dynamic_max_verification_batches: int = 8
    dynamic_preview_chars: int = 220
    verify_chars_per_call: int = 12000
    verify_chars_total: int = 192000
    max_evidence: int = 450
    query_deadline_s: float = 30  # judges' guidance: an answer within 30 s is good
    max_llm_calls: int = 32
    # UTF-8 bytes, not tokens (~4 bytes/token): 480 KB is ~120k input tokens, about $0.036 at $0.30/M.
    # Writer context stays small (raw_token_budget_*) for a ~30 s answer; all verified evidence is still returned as chunks.
    max_input_tokens: int = 480000
    max_output_tokens: int = 32000
    # Answer stage pools (writers + claim checks), separate from the early stages. Bounds, not targets: actual
    # writer and check limits are computed from the evidence. Worst case ~$0.04 output at Qwen prices.
    max_answer_calls: int = 24
    answer_input_tokens: int = 600000
    answer_pool_output_tokens: int = 80000
    verify_output_tokens: int = 48000  # separate pool; ~$0.02 worst case at Qwen output prices
    answer_output_tokens: int = 8000
    # extractive: copied sentences; ledger: source-ID findings rendered from source text; synthesis: cited analyst
    # write-up with labelled finding/inference/gap statements. A narrow single-value factoid is always extractive.
    analytical_writer_mode: str = "extractive"
    ledger_extraction_mode: str = "integrated"
    ledger_output_tokens: int = 8000
    ledger_quote_chars: int = 30000
    # Ceilings only: the answer takes what its evidence needs up to these (ledger/extractive source text).
    analytical_answer_chars: int = 24000
    analytical_answer_claims: int = 80
    # Synthesis: code picks the facts, each writer phrases at most this many; writer count and every output limit are
    # computed from the facts. Claim checks run in parallel batches of claims_per_check.
    facts_per_writer: int = 12
    analytical_fact_chars: int = 8000  # shared source budget; topic coverage beats restoring every candidate
    max_answer_writers: int = 10
    claims_per_check: int = 12
    artifact_dir: Path = Path("artifacts/runs")
    strict_observability: bool = True
    raw_token_budget_factoid: int = 12000
    raw_token_budget_analytical: int = 64000
    raw_token_budget_exhaustive: int = 96000


def value(settings, name, default=None):
    return getattr(settings, name, getattr(QuerySettings(), name, default))


def budget(settings, intent, key):
    legacy = getattr(settings, "budgets", {}).get(intent, {})
    names = {"survey_cards_total": "survey_cards_total", "verify_pages": "verify_pages",
             "verify_chars": "verify_chars_total", "max_evidence": "max_evidence"}
    return int(legacy.get(key, value(settings, names.get(key, key))))


def from_environment():
    return QuerySettings(ledger_extraction_mode=os.getenv("KB_LEDGER_EXTRACTION","integrated"),analytical_writer_mode=os.getenv("KB_ANALYTICAL_WRITER","synthesis"),metadata_navigation_enabled=os.getenv("KB_METADATA_NAVIGATION","1")!="0",page_selection_mode=os.getenv("KB_PAGE_SELECTION","local"),artifact_dir=Path(os.getenv("KB_RUN_DIR", "artifacts/runs")),
                         strict_observability=os.getenv("KB_REQUIRE_LANGFUSE", "1") != "0",
                         query_deadline_s=float(os.getenv("KB_QUERY_DEADLINE_S", "30")))


class SharedQuerySettings:
    """Preserve shared budgets, adding query-owned environment controls without editing M0."""
    def __init__(self,shared):
        self._shared=shared
        self._query=from_environment()

    def __getattr__(self,name):
        if name in ("strict_observability","query_deadline_s","artifact_dir","page_selection_mode","metadata_navigation_enabled","analytical_writer_mode","ledger_extraction_mode"):
            return getattr(self._query,name)
        if hasattr(self._shared,name):
            return getattr(self._shared,name)
        return getattr(self._query,name)
