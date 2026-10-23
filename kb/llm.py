"""The only door to the LLM: retries, JSON parsing, usage/cost accounting, Langfuse generations."""
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

import requests

from kb.config import Settings
from kb.tracing import clip, lf_generation


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0


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


def _semaphore(n: int) -> threading.BoundedSemaphore:
    with _sem_lock:
        if n not in _semaphores:
            _semaphores[n] = threading.BoundedSemaphore(n)
        return _semaphores[n]


class OpenCodeLLM(LLM):
    def scoped(self) -> "OpenCodeLLM":
        return OpenCodeLLM(self.settings)

    def _complete(self, system, user, name, model, max_tokens, json_mode):
        s = self.settings
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
                    gen.update(output=clip(content or "", 4000), usage_details={"input": in_tok, "output": out_tok},
                               **({"cost_details": cost} if cost else {}))
                    if not content:
                        raise LLMError(f"empty content, finish_reason={data['choices'][0].get('finish_reason')}")
                    return parse_json_content(content) if json_mode else content
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


def get_llm(settings: Settings) -> LLM:
    return OpenCodeLLM(settings)
