"""Typed settings read from environment variables. Every knob lives here."""
import copy
import os
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

DEFAULT_BUDGETS = {
    "factoid":    {"survey_pages_per_doc": 300,  "survey_cards_total": 600,  "verify_pages": 15,  "verify_chars": 60000,  "max_evidence": 40},
    "analytical": {"survey_pages_per_doc": 1000, "survey_cards_total": 2000, "verify_pages": 80,  "verify_chars": 240000, "max_evidence": 250},
    "exhaustive": {"survey_pages_per_doc": 2000, "survey_cards_total": 3000, "verify_pages": 200, "verify_chars": 480000, "max_evidence": 450},
}


@dataclass(frozen=True)
class Settings:
    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/inference/openai/v1/chat/completions"
    llm_model: str = "deepseek-v4.1-flash"
    answer_model: str = ""
    price_input_per_m: float | None = 0.30
    price_output_per_m: float | None = 1.20
    llm_concurrency: int = 8
    llm_timeout_s: int = 180
    llm_max_retries: int = 3
    data_dir: Path = Path("data")
    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    embed_max_chars: int = 1500
    embed_elements: bool = False
    ce_text_chars: int = 700
    ocr_dpi: int = 200
    min_text_chars: int = 50
    page_job_size: int = 50
    parse_workers: int = 0
    max_archive_bytes: int = 8_000_000_000
    page_card_pages_per_call: int = 4
    page_card_chars_per_page: int = 3500
    doc_card_chars: int = 9000
    boilerplate_min_pages: int = 3
    boilerplate_page_frac: float = 0.3
    boilerplate_max_chars: int = 300
    router_max_docs: int = 8
    router_max_cards: int = 120
    survey_batch_cards: int = 60
    lexical_net_pages_per_aspect: int = 5
    element_hits_per_aspect: int = 40
    escape_pages: int = 10
    max_ce_pairs: int = 800
    ce_tau_low: float | None = None
    ce_tau_high: float | None = None
    verify_chars_per_call: int = 24000
    query_max_chars: int = 32000
    budgets: dict = field(default_factory=lambda: copy.deepcopy(DEFAULT_BUDGETS))

    def collection_dir(self, name: str) -> Path:
        return Path(self.data_dir) / "collections" / name

    def effective_answer_model(self) -> str:
        return self.answer_model or self.llm_model


def _opt_float(raw: str | None, default: float | None) -> float | None:
    if raw is None:
        return default
    raw = raw.strip()
    return float(raw) if raw else None


# env var name -> (field, parser)
_ENV = {
    "OPENCODE_API_KEY": ("opencode_api_key", str),
    "OPENCODE_BASE_URL": ("opencode_base_url", str),
    "LLM_MODEL": ("llm_model", str),
    "ANSWER_MODEL": ("answer_model", str),
    "LLM_CONCURRENCY": ("llm_concurrency", int),
    "KB_DATA_DIR": ("data_dir", Path),
    "KB_EMBED_ELEMENTS": ("embed_elements", lambda v: v.strip().lower() in ("1", "true", "yes")),
}


def get_settings(**overrides) -> Settings:
    """Read env on every call; keyword overrides win (tests use them)."""
    values = {}
    for env, (name, parse) in _ENV.items():
        if os.environ.get(env) not in (None, ""):
            values[name] = parse(os.environ[env])
    values["price_input_per_m"] = _opt_float(os.environ.get("PRICE_INPUT_PER_M"), 0.30)
    values["price_output_per_m"] = _opt_float(os.environ.get("PRICE_OUTPUT_PER_M"), 1.20)
    values["ce_tau_low"] = _opt_float(os.environ.get("CE_TAU_LOW"), None)
    values["ce_tau_high"] = _opt_float(os.environ.get("CE_TAU_HIGH"), None)
    known = {f.name for f in fields(Settings)}
    unknown = set(overrides) - known
    if unknown:
        raise TypeError(f"unknown settings: {sorted(unknown)}")
    values.update(overrides)
    if "data_dir" in values:
        values["data_dir"] = Path(values["data_dir"])
    return replace(Settings(), **values)
