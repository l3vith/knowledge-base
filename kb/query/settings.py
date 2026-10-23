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
    verify_chars_per_call: int = 12000
    verify_chars_total: int = 192000
    max_evidence: int = 450
    query_deadline_s: float = 120
    max_llm_calls: int = 24
    # UTF-8 bytes, not tokens (~4 bytes/token): 480 KB is ~120k input tokens, about $0.036 at $0.30/M.
    # Sized from training: gold answers cite a median of 81 chunks, so the writer must see ~60-90 of ours.
    max_input_tokens: int = 480000
    max_output_tokens: int = 32000
    answer_output_tokens: int = 8000
    analytical_writer_mode: str = "extractive"
    ledger_extraction_mode: str = "integrated"
    ledger_output_tokens: int = 8000
    ledger_quote_chars: int = 30000
    analytical_answer_chars: int = 8000
    analytical_answer_claims: int = 24
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
    return QuerySettings(ledger_extraction_mode=os.getenv("KB_LEDGER_EXTRACTION","integrated"),analytical_writer_mode=os.getenv("KB_ANALYTICAL_WRITER","extractive"),metadata_navigation_enabled=os.getenv("KB_METADATA_NAVIGATION","1")!="0",page_selection_mode=os.getenv("KB_PAGE_SELECTION","local"),artifact_dir=Path(os.getenv("KB_RUN_DIR", "artifacts/runs")),
                         strict_observability=os.getenv("KB_REQUIRE_LANGFUSE", "1") != "0",
                         query_deadline_s=float(os.getenv("KB_QUERY_DEADLINE_S", "120")))


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
