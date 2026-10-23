"""The only door to the LLM: retries, JSON parsing, usage/cost accounting, Langfuse generations.

Credit savers: a disk response cache (identical prompt -> no second payment) and a dry-run mode
(KB_LLM_MODE=dryrun) that answers with cheap heuristics in the prompts' formats and records ESTIMATED tokens/cost.
"""
import hashlib
import json
import random
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

import requests

from kb.config import Settings
from kb.textutil import tokens
from kb.tracing import clip, lf_generation


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    cache_hits: int = 0


class ResponseCache:
    """sqlite map sha256(model, json_mode, max_tokens, system, user) -> raw content. Temperature is 0, so reuse is safe."""

    _locks: dict[str, threading.Lock] = {}

    def __init__(self, settings: Settings):
        self.path = settings.llm_cache_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = ResponseCache._locks.setdefault(str(self.path), threading.Lock())
        with self._lock, sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS responses(key TEXT PRIMARY KEY, name TEXT, content TEXT, ts REAL)")

    @staticmethod
    def key(model: str, json_mode: bool, max_tokens: int, system: str, user: str) -> str:
        return hashlib.sha256(json.dumps([model, json_mode, max_tokens, system, user]).encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        with self._lock, sqlite3.connect(self.path) as c:
            row = c.execute("SELECT content FROM responses WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, name: str, content: str) -> None:
        with self._lock, sqlite3.connect(self.path) as c:
            c.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?,?)", (key, name, content, time.time()))


def parse_json_content(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object in model output")
        out = json.loads(text[start:end + 1])
    if not isinstance(out, dict):
        raise ValueError("model JSON is not an object")
    return out


class LLM:
    """Base class. Subclasses implement _complete(system, user, name, model, max_tokens, json_mode) -> (text, in_tok, out_tok)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.usage = Usage()
        self._lock = threading.Lock()

    def _account(self, in_tok: int, out_tok: int) -> None:
        s = self.settings
        with self._lock:
            self.usage.calls += 1
            self.usage.input_tokens += in_tok
            self.usage.output_tokens += out_tok
            if self.usage.cost_usd is not None:
                if s.price_input_per_m is None or s.price_output_per_m is None:
                    self.usage.cost_usd = None
                else:
                    self.usage.cost_usd += in_tok * s.price_input_per_m / 1e6 + out_tok * s.price_output_per_m / 1e6

    def complete_json(self, system: str, user: str, *, name: str, model: str | None = None, max_tokens: int = 8000) -> dict:
        return self._complete(system, user, name, model or self.settings.llm_model, max_tokens, True)

    def complete_text(self, system: str, user: str, *, name: str, model: str | None = None, max_tokens: int = 16000) -> str:
        return self._complete(system, user, name, model or self.settings.llm_model, max_tokens, False)

    def scoped(self) -> "LLM":
        raise NotImplementedError

    def _complete(self, system, user, name, model, max_tokens, json_mode):
        raise NotImplementedError


_semaphores: dict[int, threading.BoundedSemaphore] = {}
_sem_lock = threading.Lock()
_ledger_lock = threading.Lock()
_ledger_totals: dict[str, float] = {}


def spent_usd(settings: Settings) -> float:
    """Total recorded spend in the ledger file (read once per process, then tracked in memory)."""
    # ponytail: per-process running total; concurrent processes each see the file total at their start
    path = settings.ledger_path()
    key = str(path.resolve())
    with _ledger_lock:
        if key not in _ledger_totals:
            total = 0.0
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        total += float(json.loads(line).get("cost_usd") or 0)
                    except ValueError:
                        continue
            _ledger_totals[key] = total
        return _ledger_totals[key]


def _record_spend(settings: Settings, name: str, model: str, in_tok: int, out_tok: int, cost: float | None) -> None:
    path = settings.ledger_path()
    spent_usd(settings)  # make sure the running total is initialised from the file
    with _ledger_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "name": name, "model": model, "input_tokens": in_tok,
                                "output_tokens": out_tok, "cost_usd": cost}) + "\n")
        _ledger_totals[str(path.resolve())] += cost or 0.0


def _semaphore(n: int) -> threading.BoundedSemaphore:
    with _sem_lock:
        if n not in _semaphores:
            _semaphores[n] = threading.BoundedSemaphore(n)
        return _semaphores[n]


class OpenCodeLLM(LLM):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.cache = ResponseCache(settings) if settings.llm_cache else None

    def scoped(self) -> "OpenCodeLLM":
        return OpenCodeLLM(self.settings)

    def _complete(self, system, user, name, model, max_tokens, json_mode):
        s = self.settings
        key = ResponseCache.key(model, json_mode, max_tokens, system, user) if self.cache else None
        if self.cache:
            hit = self.cache.get(key)
            if hit is not None:
                try:
                    out = parse_json_content(hit) if json_mode else hit
                    with self._lock:
                        self.usage.cache_hits += 1
                    return out
                except ValueError:
                    pass  # corrupt entry: fall through to a live call
        if s.budget_usd is not None and spent_usd(s) >= s.budget_usd:
            raise LLMError(f"{name}: spend cap KB_BUDGET_USD={s.budget_usd} reached ({spent_usd(s):.4f} USD recorded)")
        payload = {"model": model, "temperature": 0, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {s.opencode_api_key}", "Content-Type": "application/json"}
        last_error: Exception | None = None
        for attempt in range(1, s.llm_max_retries + 1):
            with lf_generation(name, model, {"system": clip(system, 2000), "user": clip(user, 4000)}) as gen:
                retry_after = None
                try:
                    with _semaphore(s.llm_concurrency):
                        resp = requests.post(s.opencode_base_url, headers=headers, json=payload, timeout=s.llm_timeout_s)
                    if resp.status_code == 429 or resp.status_code >= 500:
                        retry_after = resp.headers.get("Retry-After")
                        raise LLMError(f"HTTP {resp.status_code}")
                    resp.raise_for_status()
                    data = resp.json()
                    usage = data.get("usage") or {}
                    in_tok, out_tok = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
                    self._account(in_tok, out_tok)
                    content = data["choices"][0]["message"].get("content")
                    cost = self._cost(in_tok, out_tok)
                    _record_spend(s, name, model, in_tok, out_tok, cost["total"] if cost else None)
                    gen.update(output=clip(content or "", 4000), usage_details={"input": in_tok, "output": out_tok},
                               **({"cost_details": cost} if cost else {}))
                    if not content:
                        raise LLMError(f"empty content, finish_reason={data['choices'][0].get('finish_reason')}")
                    out = parse_json_content(content) if json_mode else content
                    if self.cache:
                        self.cache.put(key, name, content)
                    return out
                except (requests.RequestException, LLMError, ValueError, KeyError, IndexError) as e:
                    last_error = e
                    gen.update(level="ERROR", status_message=str(e)[:300])
            if attempt < s.llm_max_retries:
                delay = float(retry_after) if retry_after and str(retry_after).isdigit() else min(30, 2 ** attempt) + random.random()
                time.sleep(delay)
        raise LLMError(f"{name}: failed after {s.llm_max_retries} attempts: {last_error}")

    def _cost(self, in_tok: int, out_tok: int) -> dict | None:
        s = self.settings
        if s.price_input_per_m is None or s.price_output_per_m is None:
            return None
        ci, co = in_tok * s.price_input_per_m / 1e6, out_tok * s.price_output_per_m / 1e6
        return {"input": ci, "output": co, "total": ci + co}


class FakeLLM(LLM):
    """Test double. responder(name, system, user) -> dict | str, may raise LLMError. Counts 100 in / 10 out tokens per call."""

    def __init__(self, responder: Callable[[str, str, str], dict | str], settings: Settings | None = None,
                 _calls: list | None = None):
        super().__init__(settings or Settings())
        self.responder = responder
        self.calls: list[tuple[str, str, str]] = _calls if _calls is not None else []

    def scoped(self) -> "FakeLLM":
        return FakeLLM(self.responder, self.settings, self.calls)

    def _complete(self, system, user, name, model, max_tokens, json_mode):
        with self._lock:
            self.calls.append((name, system, user))
        self._account(100, 10)
        out = self.responder(name, system, user)
        if json_mode and isinstance(out, str):
            return parse_json_content(out)
        return out


def parallel_map(fn: Callable, items: list, max_workers: int) -> list:
    """Order-preserving map over threads; an exception is returned in its slot, never raised."""
    if not items:
        return []

    def safe(item):
        try:
            return fn(item)
        except Exception as e:  # noqa: BLE001 - caller inspects the slot
            return e

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(items)))) as pool:
        return list(pool.map(safe, items))


_DRY_OUTPUT_TOKENS = {"doc_card": 350, "page_card": 700, "plan": 450, "survey": 300, "verify": 450, "answer": 1800}


def _between(text: str, start: str, end: str | None) -> str:
    i = text.rfind(start) if end is None else text.find(start)
    if i < 0:
        return ""
    rest = text[i + len(start):]
    j = rest.find(end) if end else -1
    return (rest[:j] if j >= 0 else rest).strip()


def _dry_responder(name: str, system: str, user: str):
    """Heuristic stand-in for each prompt. Card calls fail on purpose so ingestion uses its deterministic fallbacks."""
    if name in ("doc_card", "page_card"):
        raise LLMError("dryrun: cards use deterministic fallbacks")
    if name == "plan":
        query = _between(user, "Question: ", None)
        return {"intent": "analytical", "answerable": True, "notes": "dryrun",
                "aspects": [{"id": "a1", "text": query, "keywords": tokens(query)[:8]}], "documents": []}
    if name == "survey":
        return {"pages": []}
    query = set(tokens(_between(user, "Question: ", "\n\n")))
    blocks = re.findall(r"\[E(\d+)\][^\n]*\n(.*?)(?=\n\[E\d+\]|\Z)", user, re.S)
    if name == "verify":
        need = max(2, len(query) // 5)
        return {"keep": [{"id": f"E{n}", "aspects": ["a1"], "note": "dryrun lexical overlap"}
                         for n, text in blocks if len(query & set(tokens(text))) >= need]}
    if name == "answer":
        lines = [f"- {' '.join(text.split())[:160]} [E{n}]" for n, text in blocks[:8]]
        return "Dry-run answer built from the top evidence.\n" + "\n".join(lines) + "\nSTATUS: answered"
    return {}


class DryRunLLM(LLM):
    """KB_LLM_MODE=dryrun: no network, no spend; usage holds ESTIMATED tokens (chars/4 in, nominal out) and cost."""

    def scoped(self) -> "DryRunLLM":
        return DryRunLLM(self.settings)

    def _complete(self, system, user, name, model, max_tokens, json_mode):
        self._account((len(system) + len(user)) // 4, min(max_tokens, _DRY_OUTPUT_TOKENS.get(name, 300)))
        out = _dry_responder(name, system, user)
        return out


def get_llm(settings: Settings) -> LLM:
    return DryRunLLM(settings) if settings.llm_mode == "dryrun" else OpenCodeLLM(settings)
