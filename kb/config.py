"""Typed settings read from environment variables. Every knob lives here."""
import copy
import os
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Cost-aware defaults: the whole project shares a $10 OpenCode budget (dev + evaluation + hidden-test run).
DEFAULT_BUDGETS = {
    "factoid":    {"survey_pages_per_doc": 300,  "survey_cards_total": 400,  "verify_pages": 12,  "verify_chars": 40000,  "max_evidence": 40},
    "analytical": {"survey_pages_per_doc": 600,  "survey_cards_total": 1000, "verify_pages": 50,  "verify_chars": 120000, "max_evidence": 200},
    "exhaustive": {"survey_pages_per_doc": 1500, "survey_cards_total": 1800, "verify_pages": 120, "verify_chars": 240000, "max_evidence": 400},
}


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from <repo>/.env (or KB_ENV_FILE) without overriding variables already set."""
    path = Path(path or os.environ.get("KB_ENV_FILE") or ROOT / ".env")
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/inference/openai/v1/chat/completions"
    llm_model: str = "qwen3.8-flash"
    answer_model: str = ""
    price_input_per_m: float | None = 0.15
    price_output_per_m: float | None = 0.47
    llm_concurrency: int = 12
    llm_timeout_s: int = 180
    llm_max_retries: int = 3
    mongodb_uri: str = ""                      # env MONGODB_URI: enables Atlas GridFS persistence of generations
    mongodb_db: str = "knowledge_base"         # env MONGODB_DB
    use_reranker: bool = True                  # env KB_RERANKER=0 skips the cross-encoder (~100 MB RAM; Render free)
    llm_mode: str = "live"                     # env KB_LLM_MODE: "live" | "dryrun" (no network, estimated cost)
    llm_cache: bool = True                     # env KB_LLM_CACHE=0 disables the response cache (data/llm_cache.sqlite)
    page_cards_mode: str = "extractive"        # env KB_PAGE_CARDS: "extractive" ($0, default) | "llm" (~$1.75 per 7k pages)
    budget_usd: float | None = None            # env KB_BUDGET_USD: hard cap on total spend recorded in the ledger
    spend_ledger: Path | None = None           # env KB_SPEND_LEDGER; default data_dir / "spend.jsonl"
    data_dir: Path = Path("data")
    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    embed_max_chars: int = 1500
    embed_elements: bool = False
    ce_text_chars: int = 700
    ocr_dpi: int = 200
    min_text_chars: int = 50
    parse_layout: bool = False                 # env KB_PARSE_LAYOUT=1: pymupdf4llm layout AI (~3.8x slower, measured)
    use_cache: bool = True                     # env KB_CACHE=0 disables the content-hash ingestion cache
    cache_dir: Path | None = None              # env KB_CACHE_DIR; default data_dir / "cache"
    page_job_size: int = 50
    parse_workers: int = 0
    max_archive_bytes: int = 8_000_000_000
    page_card_pages_per_call: int = 8
    page_card_chars_per_page: int = 1800
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

    def ledger_path(self) -> Path:
        return Path(self.spend_ledger) if self.spend_ledger else Path(self.data_dir) / "spend.jsonl"

    def cache_path(self) -> Path:
        return Path(self.cache_dir) if self.cache_dir else Path(self.data_dir) / "cache"

    def llm_cache_path(self) -> Path:
        return Path(self.data_dir) / "llm_cache.sqlite"


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
    "KB_BUDGET_USD": ("budget_usd", float),
    "KB_LLM_MODE": ("llm_mode", lambda v: v.strip().lower()),
    "KB_PARSE_WORKERS": ("parse_workers", int),
    "MONGODB_URI": ("mongodb_uri", str),
    "MONGODB_DB": ("mongodb_db", str),
    "KB_RERANKER": ("use_reranker", lambda v: v.strip().lower() not in ("0", "false", "no")),
    "KB_LLM_CACHE": ("llm_cache", lambda v: v.strip().lower() not in ("0", "false", "no")),
    "KB_PAGE_CARDS": ("page_cards_mode", lambda v: v.strip().lower()),
    "KB_PARSE_LAYOUT": ("parse_layout", lambda v: v.strip().lower() in ("1", "true", "yes")),
    "KB_CACHE": ("use_cache", lambda v: v.strip().lower() not in ("0", "false", "no")),
    "KB_CACHE_DIR": ("cache_dir", Path),
    "KB_SPEND_LEDGER": ("spend_ledger", Path),
}


def get_settings(**overrides) -> Settings:
    """Read .env + env on every call; keyword overrides win (tests use them)."""
    load_dotenv()
    values = {}
    for env, (name, parse) in _ENV.items():
        if os.environ.get(env) not in (None, ""):
            values[name] = parse(os.environ[env])
    values["price_input_per_m"] = _opt_float(os.environ.get("PRICE_INPUT_PER_M"), 0.15)
    values["price_output_per_m"] = _opt_float(os.environ.get("PRICE_OUTPUT_PER_M"), 0.47)
    values["ce_tau_low"] = _opt_float(os.environ.get("CE_TAU_LOW"), None)
    values["ce_tau_high"] = _opt_float(os.environ.get("CE_TAU_HIGH"), None)
    known = {f.name for f in fields(Settings)}
    unknown = set(overrides) - known
    if unknown:
        raise TypeError(f"unknown settings: {sorted(unknown)}")
    values.update(overrides)
    if "data_dir" in values:
        values["data_dir"] = Path(values["data_dir"])
    settings = replace(Settings(), **values)
    from kb.model_api import REQUIRED_MODEL
    for name in ("llm_model", "answer_model"):
        if getattr(settings, name) not in ("", REQUIRED_MODEL):
            raise ValueError(f"{name}={getattr(settings, name)!r} refused: set LLM_MODEL/ANSWER_MODEL to {REQUIRED_MODEL}")
    return settings
