from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import json
import time
import uuid
from .errors import BudgetExceeded, QueryError
from .observability import LocalSink
from .settings import value
from .utils import compact, estimate_tokens, plain


class QueryRuntime:
    def __init__(self, settings, llm, sink=None, request_id=None):
        self.settings, self.llm = settings, llm.scoped() if hasattr(llm, "scoped") else llm
        self.sink = sink or LocalSink()
        if value(settings, "strict_observability") and not self.sink.enabled:
            raise QueryError("OBSERVABILITY_UNAVAILABLE", "Required Langfuse tracing is unavailable", 503)
        self.request_id = request_id or "req_" + uuid.uuid4().hex
        self.started = time.monotonic()
        self.deadline = self.started + value(settings, "query_deadline_s")
        self.trace, self.events, self.limitations = [], [], []
        self.calls = self.estimated_input = self.reserved_output = 0
        self.input_tokens = self.output_tokens = self.cost = 0
        self.unknown_usage = self.unknown_cost = False
        self.path = Path(value(settings, "artifact_dir")) / self.request_id
        self.path.mkdir(parents=True, exist_ok=False)
        self.path.chmod(0o700)

    def check(self):
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("Query deadline exhausted")

    def save(self, name, data):
        path = self.path / (name + ".json")
        path.write_text(json.dumps(plain(data), ensure_ascii=False, indent=2)+"\n")
        path.chmod(0o600)
        return name

    @contextmanager
    def stage(self, name, description, inputs=None):
        start = time.monotonic()
        output = {}
        try:
            self.check()
            with self.sink.span(name, input=plain(inputs)) as span:
                yield output
                output["duration_ms"] = round((time.monotonic()-start)*1000, 3)
                span.update(output=plain(output))
        except BaseException as exc:
            output.update(error=type(exc).__name__, complete=False,
                          duration_ms=round((time.monotonic()-start)*1000, 3))
            raise
        finally:
            self.trace.append({"step_name": name, "description": description,
                               "input": plain(inputs or {}), "output": plain(output)})

    def call(self, name, system, payload, max_tokens=4000):
        self.check()
        # This gateway exposes DeepSeek reasoning variants; hidden reasoning consumes
        # completion tokens even when the upstream thinking toggle is ignored.
        if str(getattr(self.llm,"model","")).startswith("deepseek-"):
            max_tokens=max(max_tokens,4096)
        user = compact(payload)
        predicted = estimate_tokens(system) + estimate_tokens(user)
        if self.calls >= value(self.settings, "max_llm_calls"):
            raise BudgetExceeded("Model call budget exhausted")
        # Early stages may not starve the later ones: plan/survey/verify each stop at a cumulative share of the budget.
        # ponytail: fixed shares; make them per-intent settings if dev evaluation shows a better split.
        share = {"plan": 0.25, "survey": 0.5, "verify": 0.85}.get(name, 1.0)
        if self.estimated_input + predicted > share * value(self.settings, "max_input_tokens"):
            raise BudgetExceeded("Conservative input budget exhausted")
        final_reserve = 0 if name in ("answer", "answer_verify") else value(self.settings, "answer_output_tokens") + 2000
        if self.reserved_output + max_tokens + final_reserve > value(self.settings, "max_output_tokens"):
            raise BudgetExceeded("Output reservation budget exhausted")
        self.calls += 1
        self.estimated_input += predicted
        self.reserved_output += max_tokens
        attempt = {"call": self.calls, "name": name, "input_estimate": predicted,
                   "input_estimate_method": "utf8_byte_upper_budget", "output_limit": max_tokens}
        self.save(f"call_{self.calls}_input", {"system": system, "payload": payload})
        start = time.monotonic()
        before = plain(getattr(self.llm, "usage", {}))
        charged = False
        if hasattr(self.llm,"last_usage"):
            self.llm.last_usage=None
        if hasattr(self.llm,"last_response"):
            self.llm.last_response=None
        try:
            with self.sink.span(name, as_type="generation", input=payload,
                                model=getattr(self.llm, "model", None)) as span:
                if hasattr(self.llm, "set_request_deadline"):
                    self.llm.set_request_deadline(self.deadline)
                result = self.llm.complete_json(system, user, name=name, max_tokens=max_tokens)
                if not isinstance(result, dict):
                    raise QueryError("MODEL_SCHEMA", "Expected a JSON object", 503)
                usage = getattr(self.llm, "last_usage", None)
                after = plain(getattr(self.llm, "usage", {}))
                if usage is None and isinstance(after, dict) and isinstance(before, dict) and after:
                    usage = {k: after.get(k)-before.get(k, 0) if isinstance(after.get(k), (int,float)) and isinstance(before.get(k,0),(int,float)) else None
                             for k in ("input_tokens", "output_tokens", "cost_usd")}
                    attempt["transport_attempts"] = "managed_by_shared_client"
                usage = usage or {}
                self._charge(usage)
                charged = True
                if isinstance(usage.get("output_tokens"), int):
                    self.reserved_output += usage["output_tokens"] - max_tokens
                attempt.update(status="ok", usage=usage)
                kwargs = {"output": result}
                known = {key: usage.get(alias) for key,alias in [("input","input_tokens"),("output","output_tokens")] if isinstance(usage.get(alias),int)}
                if known:
                    kwargs["usage_details"] = known
                if usage.get("cost_usd") is not None:
                    kwargs["cost_details"] = {"total": usage["cost_usd"]}
                span.update(**kwargs)
                self.save(f"call_{self.calls}_output", result)
                return result
        except BaseException:
            failed_usage = getattr(self.llm, "last_usage", None)
            attempt.update(status="failed", usage=failed_usage)
            if not charged and failed_usage:
                self._charge(failed_usage)
                if isinstance(failed_usage.get("output_tokens"),int):
                    self.reserved_output+=failed_usage["output_tokens"]-max_tokens
            elif not charged:
                self.unknown_usage = self.unknown_cost = True
            raise
        finally:
            diagnostics=getattr(self.llm,"last_response",None)
            if diagnostics is not None:
                attempt["response_artifact"]=self.save(f"call_{self.calls}_raw_response",diagnostics)
            attempt["latency_ms"] = round((time.monotonic()-start)*1000, 3)
            self.events.append(attempt)
            self.save("attempts", self.events)

    def _charge(self, usage):
        for name in ("input_tokens", "output_tokens"):
            v = usage.get(name)
            if isinstance(v, int) and v >= 0:
                setattr(self, name, getattr(self, name)+v)
            else:
                self.unknown_usage = True
        cost = usage.get("cost_usd")
        if isinstance(cost, (int,float)) and cost >= 0:
            self.cost += cost
        else:
            self.unknown_cost = True

    def usage(self):
        return {"calls": self.calls, "input_tokens": None if self.unknown_usage else self.input_tokens,
                "output_tokens": None if self.unknown_usage else self.output_tokens,
                "cost_usd": None if self.unknown_cost else self.cost,
                "estimated_input_budget_units": self.estimated_input,
                "unknown_reason": "Provider usage and/or verified prices unavailable" if self.unknown_usage or self.unknown_cost else None}
