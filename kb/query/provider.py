"""Optional Track B transport, without replacing Person 1's kb.llm."""
import json
import os
import threading
import time
import httpx
from .errors import QueryError

_PROVIDER_GATE = threading.BoundedSemaphore(2)


class OpenCodeJSONClient:
    def __init__(self, model=None, base_url=None, key=None, timeout=90):
        self.model = model or os.getenv("OPENCODE_MODEL", os.getenv("LLM_MODEL", ""))
        self.base_url = base_url or os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/inference/openai/v1/chat/completions")
        self.key = key or os.getenv("OPENCODE_API_KEY", "")
        self.timeout = timeout
        self.last_usage = None
        self.last_response = None
        self.deadline = None
        if not self.key or not self.model:
            raise QueryError("PROVIDER_UNAVAILABLE", "Configure OPENCODE_API_KEY and OPENCODE_MODEL", 503)

    def scoped(self):
        return OpenCodeJSONClient(self.model, self.base_url, self.key, self.timeout)

    def set_request_deadline(self, deadline):
        self.deadline = deadline

    def complete_json(self, system, user, *, name, max_tokens=4000):
        self.last_usage = None
        self.last_response = None
        payload = {"model": self.model, "messages": [{"role":"system","content":system},{"role":"user","content":user}],
                   "temperature":0, "max_tokens":max_tokens, "response_format":{"type":"json_object"}}
        # One transport attempt per call; retries must go through the request ledger.
        remaining = max(0.0, self.deadline-time.monotonic()) if self.deadline is not None else self.timeout
        acquired = _PROVIDER_GATE.acquire(timeout=min(self.timeout, remaining))
        if not acquired:
            raise QueryError("QUERY_DEADLINE", "Provider queue deadline exhausted", 504)
        try:
            remaining = max(0.0, self.deadline-time.monotonic()) if self.deadline is not None else self.timeout
            if remaining <= 0:
                raise QueryError("QUERY_DEADLINE", "Query deadline exhausted before provider call", 504)
            try:
                with httpx.Client(timeout=min(self.timeout, remaining)) as client:
                    response = client.post(self.base_url, headers={"Authorization":"Bearer "+self.key},json=payload)
                    response.raise_for_status()
                    body = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise QueryError("PROVIDER_UNAVAILABLE", "Model request failed", 503, True) from exc
        finally:
            _PROVIDER_GATE.release()
        if not isinstance(body,dict):
            raise QueryError("MODEL_SCHEMA", "Provider returned a non-object response", 503)
        usage = body.get("usage") or {}
        if not isinstance(usage,dict):
            usage={}
        self.last_usage = {"input_tokens":usage.get("prompt_tokens"),"output_tokens":usage.get("completion_tokens"),"cost_usd":None}
        choice=(body.get("choices") or [{}])[0]
        self.last_response={"content":choice.get("message",{}).get("content"),
                            "finish_reason":choice.get("finish_reason"),"output_limit":max_tokens}
        try:
            content = body["choices"][0]["message"]["content"].strip()
            if content.startswith("```json\n") and content.endswith("\n```"):
                content = content[8:-4]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("not object")
            return result
        except (KeyError,IndexError,TypeError,ValueError) as exc:
            raise QueryError("MODEL_SCHEMA", "Model returned invalid JSON", 503) from exc
