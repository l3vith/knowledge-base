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
    survey_batch_cards: int = 40
    survey_cards_total: int = 400
    verify_pages: int = 200
    lexical_net_pages_per_aspect: int = 5
    element_hits_per_aspect: int = 40
    escape_pages: int = 20
    max_ce_pairs: int = 400
    verify_chars_per_call: int = 12000
    verify_chars_total: int = 192000
    max_evidence: int = 450
    query_deadline_s: float = 120
    max_llm_calls: int = 24
    max_input_tokens: int = 200000
    max_output_tokens: int = 24000
    answer_output_tokens: int = 6000
    artifact_dir: Path = Path("artifacts/runs")
    strict_observability: bool = True
    raw_token_budget_factoid: int = 4000
    raw_token_budget_analytical: int = 16000
    raw_token_budget_exhaustive: int = 48000


def value(settings, name, default=None):
    return getattr(settings, name, getattr(QuerySettings(), name, default))


def budget(settings, intent, key):
    legacy = getattr(settings, "budgets", {}).get(intent, {})
    names = {"survey_cards_total": "survey_cards_total", "verify_pages": "verify_pages",
             "verify_chars": "verify_chars_total", "max_evidence": "max_evidence"}
    return int(legacy.get(key, value(settings, names.get(key, key))))


def from_environment():
    return QuerySettings(artifact_dir=Path(os.getenv("KB_RUN_DIR", "artifacts/runs")),
                         strict_observability=os.getenv("KB_REQUIRE_LANGFUSE", "1") != "0",
                         query_deadline_s=float(os.getenv("KB_QUERY_DEADLINE_S", "120")))


class SharedQuerySettings:
    """Preserve shared budgets, adding query-owned environment controls without editing M0."""
    def __init__(self,shared):
        self._shared=shared
        self._query=from_environment()

    def __getattr__(self,name):
        if name in ("strict_observability","query_deadline_s","artifact_dir"):
            return getattr(self._query,name)
        if hasattr(self._shared,name):
            return getattr(self._shared,name)
        return getattr(self._query,name)
