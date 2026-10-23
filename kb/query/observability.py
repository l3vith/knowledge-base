"""Independent Track B spans; never silently claim export success."""
from contextlib import contextmanager
import os
from .errors import QueryError


class LocalSink:
    enabled = False
    status = "local_only"
    trace_id = None

    @contextmanager
    def span(self, name, **kwargs):
        yield self

    def update(self, **kwargs):
        return None

    def flush(self):
        return None


class LangfuseSink:
    enabled = True
    status = "sdk_pending_export"

    def __init__(self, client=None):
        if client is None:
            from langfuse import Langfuse
            client = Langfuse(public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
                              secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
                              base_url=os.environ.get("LANGFUSE_BASE_URL", os.getenv("LANGFUSE_HOST")),
                              sample_rate=1.0)
        self.client = client
        self.trace_id = None

    @contextmanager
    def span(self, name, **kwargs):
        try:
            manager = self.client.start_as_current_observation(name=name, **kwargs)
            span = manager.__enter__()
        except Exception as exc:
            self.status = "failed"
            raise QueryError("OBSERVABILITY_UNAVAILABLE", "Unable to create required trace", 503) from exc
        try:
            self.trace_id = self.client.get_current_trace_id()
            yield span
        except BaseException as exc:
            manager.__exit__(type(exc), exc, exc.__traceback__)
            raise
        else:
            manager.__exit__(None, None, None)

    def flush(self):
        try:
            self.client.flush()
            # SDK flush alone does not establish remote receipt.
            self.status = "sdk_flushed_receipt_unverified"
        except Exception as exc:
            self.status = "failed"
            raise QueryError("OBSERVABILITY_UNAVAILABLE", "Required trace flush failed", 503) from exc


def sink_from_environment(required=True):
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        return LangfuseSink()
    if required:
        raise QueryError("OBSERVABILITY_UNAVAILABLE", "Langfuse credentials are required", 503)
    return LocalSink()
