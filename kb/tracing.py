"""Response trace (exactly four keys per step) and a Langfuse facade that never breaks a request."""
import logging
import os
from contextlib import contextmanager
from typing import Any

log = logging.getLogger("kb.tracing")
TRACE_KEYS = ("step_name", "description", "input", "output")


def clip(value: Any, max_str: int = 500, max_list: int = 50) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_str else value[:max_str] + "..."
    if isinstance(value, dict):
        return {k: clip(v, max_str, max_list) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [clip(v, max_str, max_list) for v in value[:max_list]]
        if len(value) > max_list:
            items.append(f"... (+{len(value) - max_list} more)")
        return items
    return value


class StepTrace:
    def __init__(self):
        self._steps: list[dict] = []

    def add(self, step_name: str, description: str, input: Any, output: Any) -> None:
        self._steps.append({"step_name": step_name, "description": description,
                            "input": clip(input), "output": clip(output)})

    def to_list(self) -> list[dict]:
        return [dict(s) for s in self._steps]


class _Noop:
    def update(self, **kwargs) -> None:
        pass


_client = None
_client_checked = False


def _lf():
    """Langfuse client if keys are configured, else None. Created once per process."""
    global _client, _client_checked
    if not _client_checked:
        _client_checked = True
        if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
            try:
                from langfuse import Langfuse
                _client = Langfuse()
            except Exception as e:  # observability must never break serving
                log.warning("langfuse disabled: %s", e)
    return _client


@contextmanager
def _observation(as_type: str, name: str, **kwargs):
    client = _lf()
    if client is None:
        yield _Noop()
        return
    try:
        cm = client.start_as_current_observation(name=name, as_type=as_type, **kwargs)
        obs = cm.__enter__()
    except Exception as e:
        log.warning("langfuse observation failed: %s", e)
        yield _Noop()
        return
    safe = _Safe(obs)
    try:
        yield safe
    finally:
        try:
            cm.__exit__(None, None, None)
        except Exception as e:
            log.warning("langfuse close failed: %s", e)


class _Safe:
    def __init__(self, obs):
        self._obs = obs

    def update(self, **kwargs) -> None:
        try:
            self._obs.update(**kwargs)
        except Exception as e:
            log.warning("langfuse update failed: %s", e)


@contextmanager
def lf_span(name: str, input: Any = None, metadata: dict | None = None):
    with _observation("span", name, input=input, metadata=metadata) as obs:
        yield obs


@contextmanager
def lf_generation(name: str, model: str, input: Any):
    with _observation("generation", name, model=model, input=input) as obs:
        yield obs


def lf_trace_id() -> str | None:
    client = _lf()
    if client is None:
        return None
    try:
        return client.get_current_trace_id()
    except Exception:
        return None


def lf_flush() -> None:
    client = _lf()
    if client is not None:
        try:
            client.flush()
        except Exception as e:
            log.warning("langfuse flush failed: %s", e)
