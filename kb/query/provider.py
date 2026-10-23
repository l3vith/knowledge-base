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
        from kb.model_api import request_spec, response_parts
        endpoint,wire_headers,payload=request_spec(self.base_url,self.model,system,user,max_tokens)
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
                    response = client.post(endpoint, headers={"Authorization":"Bearer "+self.key,**wire_headers},json=payload)
                    response.raise_for_status()
                    body = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise QueryError("PROVIDER_UNAVAILABLE", "Model request failed", 503, True) from exc
        finally:
            _PROVIDER_GATE.release()
        if not isinstance(body,dict):
            raise QueryError("MODEL_SCHEMA", "Provider returned a non-object response", 503)
        try:
            content,finish_reason,inputs,outputs=response_parts(body)
        except (KeyError,IndexError,TypeError,ValueError) as exc:
            raise QueryError("MODEL_SCHEMA","Invalid provider response envelope",503) from exc
        self.last_usage={"input_tokens":inputs,"output_tokens":outputs,"cost_usd":None}
        self.last_response={"content":content,"finish_reason":finish_reason,"output_limit":max_tokens}
        try:
            if not isinstance(content,str):
                raise ValueError("missing answer content")
            content=content.strip()
            if content.startswith("```json\n") and content.endswith("\n```"):
                content = content[8:-4]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("not object")
            return result
        except (KeyError,IndexError,TypeError,ValueError) as exc:
            raise QueryError("MODEL_SCHEMA", "Model returned invalid JSON", 503) from exc


class SharedQueryClient:
    """Keep shared cache/spend accounting, with one deadline-bound attempt per query call."""
    def __init__(self, llm):
        self.llm=llm
        self.model=llm.settings.effective_answer_model()

    def scoped(self):
        from dataclasses import replace
        clone=self.llm.scoped()
        clone.settings=replace(clone.settings,llm_max_retries=1)
        return SharedQueryClient(clone)

    @property
    def usage(self):
        from dataclasses import asdict
        return asdict(self.llm.usage)

    @property
    def last_usage(self):
        return getattr(self.llm,"last_usage",None)

    @last_usage.setter
    def last_usage(self,v):
        self.llm.last_usage=v

    @property
    def last_response(self):
        return getattr(self.llm,"last_response",None)

    @last_response.setter
    def last_response(self,v):
        self.llm.last_response=v

    def set_request_deadline(self,deadline):
        self.llm.deadline=deadline

    def complete_json(self,system,user,*,name,max_tokens):
        try:
            return self.llm.complete_json(system,user,name=name,model=self.model,max_tokens=max_tokens)
        except Exception as exc:
            from kb.llm import LLMError
            if isinstance(exc,LLMError) and self.last_response is not None:
                raise QueryError("MODEL_SCHEMA","Model returned invalid or truncated JSON",503) from exc
            raise
