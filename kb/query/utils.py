from __future__ import annotations
import dataclasses
import hashlib
import json
import math
import re
from typing import Any


def get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def plain(obj):
    if dataclasses.is_dataclass(obj):
        return {k: plain(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [plain(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def terms(text: str) -> list[str]:
    # Keep negation and identifiers; storage must quote tokens for FTS itself.
    return list(dict.fromkeys(re.findall(r"\w+(?:[-.]\w+)*", str(text).lower(), re.UNICODE)))


def estimate_tokens(text: str) -> int:
    # Conservative byte budget, explicitly an estimate, not actual provider usage.
    return max(1, len(text.encode("utf-8")))


def compact(obj) -> str:
    return json.dumps(plain(obj), ensure_ascii=False, separators=(",", ":"))


def quote_valid(text, quote):
    return isinstance(quote, str) and bool(quote.strip()) and quote in text


def id_for(*parts):
    return hashlib.sha256(compact(parts).encode()).hexdigest()


def fragment(element, start, end):
    from .types import SourceFragment
    text = get(element, "text", "")
    parent = get(element, "element_id")
    if start == 0 and end == len(text):
        return element
    return SourceFragment(parent + ":span:" + id_for(start, end, text[start:end]),
                          get(element, "doc_id"), int(get(element, "page_no", get(element, "physical_page", 1))),
                          int(get(element, "idx", 0)), get(element, "kind", "text"),
                          get(element, "section", ""), text[start:end], get(element, "flags", []),
                          parent, start, end)


def source_fragments(element, max_bytes):
    """Lossless contiguous spans; prefer line/sentence boundaries, never unseen tails."""
    text = get(element, "text", "")
    start = 0
    while start < len(text):
        end = min(len(text), start + max_bytes)
        while end > start and len(text[start:end].encode("utf-8")) > max_bytes:
            end -= max(1, (end-start)//10)
        if end == start:
            raise ValueError("fragment budget smaller than one source character")
        if end < len(text):
            boundary = text.rfind("\n", start + (end-start)//2, end)
            if boundary > start:
                end = boundary + 1
        yield fragment(element, start, end)
        start = end


def rrf(*rankings, k=60):
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, key in enumerate(ranking, 1):
            if key not in seen:
                scores[key] = scores.get(key, 0.0) + 1.0/(k+rank)
                seen.add(key)
    return sorted(scores, key=lambda key: (-scores[key], str(key)))
