from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import contextvars
from pathlib import Path
import json
import threading
import time
import uuid
from .errors import BudgetExceeded, QueryError
from .observability import LocalSink
from .settings import value
from .utils import compact, estimate_tokens, plain

FINAL = {"answer", "answer_verify", "answer_generation", "answer_verification", "citation_render"}
FINAL_GRACE_S = 45  # per-call HTTP allowance for the answer and claim check when the query deadline is close

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
        self.calls = self.estimated_input = self.reserved_output = self.reserved_verify = 0
        self.pending_ledger = False
        self.input_tokens = self.output_tokens = self.cost = 0
        self.unknown_usage = self.unknown_cost = False
        self._lock = threading.RLock()
        self.path = Path(value(settings, "artifact_dir")) / self.request_id
        self.path.mkdir(parents=True, exist_ok=False)
        self.path.chmod(0o700)

    def check(self, name=None):
        # Early stages stop at a share of the deadline so the answer always gets time; answer stages are never cut,
        # because a deadline hit there would throw away all the evidence already paid for.
        if name in FINAL:
            return
        share = {"survey": 0.35, "verify": 0.55}.get(name, 1.0)
        if time.monotonic() >= self.started + share * (self.deadline - self.started):
            raise BudgetExceeded("Query deadline exhausted")

    def save(self, name, data):
        path = self.path / (name + ".json")
        path.write_text(json.dumps(plain(data), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        path.chmod(0o600)
        return name

    @contextmanager
    def stage(self, name, description, inputs=None):
        start = time.monotonic()
        output = {}
        try:
            self.check(name)
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
        result = self.call_many(name, system, [payload], max_tokens)[0]
        if isinstance(result, BaseException):
            raise result
        return result

    def call_many(self, name, system, payloads, max_tokens=4000):
        """Reserve budget for each payload in order, then run the reserved calls concurrently.

        max_tokens is one limit or one per payload. Returns one result or exception per payload;
        payloads past the first budget refusal get BudgetExceeded."""
        limits = max_tokens if isinstance(max_tokens, list) else [max_tokens] * len(payloads)
        jobs, results = [], []
        for payload, limit in zip(payloads, limits):
            try:
                jobs.append(self._reserve(name, system, payload, limit))
            except BudgetExceeded as exc:
                results = [exc] * (len(payloads) - len(jobs))
                break
        if len(jobs) == 1:
            ran = [self._run_safe(jobs[0], self.llm)]
        else:
            # Own client per thread keeps usage deltas separate; copied contexts keep Langfuse spans nested.
            ctxs = [contextvars.copy_context() for _ in jobs]
            # 12 workers: a 12-batch verification runs in one wave (two waves of 6 took ~14 s).
            with ThreadPoolExecutor(max_workers=min(12, len(jobs) or 1)) as pool:
                ran = list(pool.map(lambda pair: pair[0].run(self._run_safe, pair[1], self._clone()), zip(ctxs, jobs)))
        return ran + results

    def _clone(self):
        return self.llm.scoped() if hasattr(self.llm, "scoped") else self.llm

    def _effective_limit(self, n):
        # Reasoning models spend hidden tokens before the JSON; the floor is DeepSeek-only (Qwen runs without thinking).
        return max(n, 4096) if str(getattr(self.llm, "model", "")).startswith("deepseek-") else n

    def _reserve(self, name, system, payload, max_tokens):
        self.check(name)
        max_tokens = self._effective_limit(max_tokens)
        user = compact(payload)
        predicted = estimate_tokens(system) + estimate_tokens(user)
        with self._lock:
            # Earlier stages leave six calls (up to three parallel writers and three claim-check batches),
            # plus one for the optional separate ledger extraction.
            reserved_calls=0 if name in FINAL else 6 + int(self.pending_ledger and name!="ledger_extract")
            if self.calls >= value(self.settings, "max_llm_calls") - reserved_calls:
                raise BudgetExceeded("Model call budget exhausted")
            # Early stages may not starve the later ones: plan/survey/verify each stop at a cumulative share of the budget.
            # ponytail: fixed shares; make them per-intent settings if dev evaluation shows a better split.
            share = {"plan": 0.1, "survey": 0.3, "verify": 0.72}.get(name, 1.0)
            if self.estimated_input + predicted > share * value(self.settings, "max_input_tokens"):
                raise BudgetExceeded("Conservative input budget exhausted")
            # Verification has its own output pool: in-flight batches reserve their full limit, and sharing the
            # answer's pool (minus its reserve) capped a concurrent round at ~14 batches and dropped the rest.
            if name == "verify":
                if self.reserved_verify + max_tokens > value(self.settings, "verify_output_tokens"):
                    raise BudgetExceeded("Verification output budget exhausted")
            else:
                final_check = self._effective_limit(2000)
                final_reserve = (0 if name == "answer_verify" else final_check if name == "answer"
                                 else self._effective_limit(value(self.settings, "answer_output_tokens")) + final_check)
                if self.reserved_output + max_tokens + final_reserve > value(self.settings, "max_output_tokens"):
                    raise BudgetExceeded("Output reservation budget exhausted")
            self.calls += 1
            self.estimated_input += predicted
            self._pool(name, max_tokens)
            number = self.calls
        self.save(f"call_{number}_input", {"system": system, "payload": payload})
        return {"number": number, "name": name, "system": system, "user": user, "payload": payload,
                "max_tokens": max_tokens, "predicted": predicted}

    def _run_safe(self, job, llm):
        try:
            return self._run(job, llm)
        except Exception as exc:
            return exc

    def _run(self, job, llm):
        name, max_tokens = job["name"], job["max_tokens"]
        attempt = {"call": job["number"], "name": name, "input_estimate": job["predicted"],
                   "input_estimate_method": "utf8_byte_upper_budget", "output_limit": max_tokens}
        start = time.monotonic()
        before = plain(getattr(llm, "usage", {}))
        charged = False
        if hasattr(llm,"last_usage"):
            llm.last_usage=None
        if hasattr(llm,"last_response"):
            llm.last_response=None
        try:
            with self.sink.span(name, as_type="generation", input=job["payload"],
                                model=getattr(llm, "model", None)) as span:
                if hasattr(llm, "set_request_deadline"):
                    # The answer and claim check are never cut by the query deadline: losing them discards paid evidence.
                    llm.set_request_deadline(max(self.deadline, time.monotonic() + FINAL_GRACE_S) if name in FINAL else self.deadline)
                result = llm.complete_json(job["system"], job["user"], name=name, max_tokens=max_tokens)
                if not isinstance(result, dict):
                    raise QueryError("MODEL_SCHEMA", "Expected a JSON object", 503)
                usage = getattr(llm, "last_usage", None)
                after = plain(getattr(llm, "usage", {}))
                if usage is None and isinstance(after, dict) and isinstance(before, dict) and after:
                    usage = {k: after.get(k)-before.get(k, 0) if isinstance(after.get(k), (int,float)) and isinstance(before.get(k,0),(int,float)) else None
                             for k in ("input_tokens", "output_tokens", "cost_usd")}
                    attempt["transport_attempts"] = "managed_by_shared_client"
                usage = usage or {}
                with self._lock:
                    self._charge(usage)
                    charged = True
                    if isinstance(usage.get("output_tokens"), int):
                        self._pool(name, usage["output_tokens"] - max_tokens)
                attempt.update(status="ok", usage=usage)
                kwargs = {"output": result}
                known = {key: usage.get(alias) for key,alias in [("input","input_tokens"),("output","output_tokens")] if isinstance(usage.get(alias),int)}
                if known:
                    kwargs["usage_details"] = known
                if usage.get("cost_usd") is not None:
                    kwargs["cost_details"] = {"total": usage["cost_usd"]}
                span.update(**kwargs)
                self.save(f"call_{job['number']}_output", result)
                return result
        except BaseException:
            failed_usage = getattr(llm, "last_usage", None)
            attempt.update(status="failed", usage=failed_usage)
            with self._lock:
                if not charged and failed_usage:
                    self._charge(failed_usage)
                    if isinstance(failed_usage.get("output_tokens"),int):
                        self._pool(name, failed_usage["output_tokens"]-max_tokens)
                elif not charged:
                    self.unknown_usage = self.unknown_cost = True
            raise
        finally:
            diagnostics=getattr(llm,"last_response",None)
            if diagnostics is not None:
                attempt["response_artifact"]=self.save(f"call_{job['number']}_raw_response",diagnostics)
            attempt["latency_ms"] = round((time.monotonic()-start)*1000, 3)
            with self._lock:
                self.events.append(attempt)
                self.events.sort(key=lambda e: e["call"])
                self.save("attempts", self.events)

    def _pool(self, name, delta):
        if name == "verify":
            self.reserved_verify += delta
        else:
            self.reserved_output += delta

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
