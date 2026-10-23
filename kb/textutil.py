"""Shared text helpers: one tokenizer for FTS queries, fakes and lexical scoring."""
import hashlib
import re

STOP_TOKENS = {"and", "or", "not", "near"}
_NOISE_LINE = re.compile(r"^[\W\d_]*$")


def tokens(text: str) -> list[str]:
    seen, out = set(), []
    for tok in re.findall(r"\w+", text.lower(), re.UNICODE):
        if (len(tok) == 1 and not tok.isdigit()) or tok in STOP_TOKENS or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def norm_for_hash(text: str) -> str:
    lines = [ln for ln in text.lower().splitlines() if not _NOISE_LINE.match(ln.strip())]
    return " ".join(" ".join(lines).split())


def text_hash(text: str) -> str:
    return hashlib.sha1(norm_for_hash(text).encode("utf-8")).hexdigest()
