"""M2: split parsed pages into paragraph/table elements and flag repeated boilerplate.

Per page: blocks -> clean-up -> merge -> split -> ids (docs/PLAN.md, M2).
"""
import re
from collections import defaultdict
from dataclasses import dataclass

from kb.config import Settings
from kb.models import Element, ParsedDoc
from kb.textutil import norm_for_hash, text_hash

MERGE_BELOW = 120        # text blocks shorter than this merge forward (or become a table caption)
SPLIT_TARGET = 1200      # preferred piece length when splitting long text
SPLIT_ABOVE = 1800       # text blocks longer than this are split
TABLE_SPLIT_ABOVE = 6000
TABLE_GROUP_MAX = 4000
MAX_LEVELS = 4
MAX_TITLE = 80

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_NOISE = re.compile(r"[\s|\-_\d]")
_SENTENCE_END = re.compile(r"(?<=[.;:])\s+")
_TABLE_SEP = re.compile(r"^\|[\s:\-|]+\|?$")


@dataclass
class _Block:
    kind: str            # "text" | "table"
    lines: list[str]     # heading lines first (if any), then body
    section: str
    title: str | None    # nearest heading title when the block started
    n_heads: int = 0
    has_caption: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _clean_title(raw: str) -> str:
    return raw.replace("*", "").replace("_", "").strip()


def _push(stack: list[tuple[int, str]], level: int, title: str) -> None:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))


def _path(stack: list[tuple[int, str]]) -> str:
    return " > ".join(t[:MAX_TITLE] for _, t in stack[:MAX_LEVELS])


def _is_noise(lines: list[str]) -> bool:
    return len(_NOISE.sub("", "".join(lines))) < 3


def _raw_items(md: str) -> list[tuple[str, list[str]]]:
    """Lines -> ("heading"|"text"|"table", lines). Blank lines and text/table transitions end a block."""
    items, cur, cur_kind = [], [], None

    def flush():
        nonlocal cur, cur_kind
        if cur:
            items.append((cur_kind, cur))
        cur, cur_kind = [], None

    for line in md.splitlines():
        s = line.strip()
        if not s:
            flush()
            continue
        if _HEADING.match(s):
            flush()
            items.append(("heading", [s]))
            continue
        kind = "table" if s.startswith("|") else "text"
        if kind != cur_kind:
            flush()
        cur.append(line.rstrip())
        cur_kind = kind
    flush()
    return items


def _blocks(md: str, stack: list[tuple[int, str]], md_base: int) -> list[_Block]:
    """Blocks + clean-up. Mutates `stack` with markdown headings (levels offset by md_base)."""
    blocks, pending = [], []
    for kind, lines in _raw_items(md):
        if kind == "heading":
            m = _HEADING.match(lines[0])
            title = _clean_title(m.group(2))
            if title:
                _push(stack, md_base + len(m.group(1)), title)
            pending.append(lines[0])
            continue
        # Noise is dropped before headings attach, so a heading goes to the next real block.
        if _is_noise(lines):
            continue
        blocks.append(_Block(kind, pending + lines, _path(stack), stack[-1][1] if stack else None, n_heads=len(pending)))
        pending = []
    return blocks  # a trailing heading (pending) is dropped


def _merge(blocks: list[_Block]) -> list[_Block]:
    out: list[_Block] = []
    carry: _Block | None = None
    for i, b in enumerate(blocks):
        if carry is not None:
            if b.kind == "text":
                b = _Block("text", carry.lines + [""] + b.lines, carry.section, carry.title, carry.n_heads)
            else:
                heads = carry.lines[:carry.n_heads]
                caption = " ".join(ln.strip() for ln in carry.lines[carry.n_heads:])
                b.lines = heads + [f"Caption: {caption}"] + b.lines
                b.n_heads += len(heads)
                b.has_caption = True
            carry = None
        if b.kind == "text" and len(b.text) < MERGE_BELOW:
            if i < len(blocks) - 1:
                carry = b
                continue
            if out:
                out[-1].lines += [""] + b.lines
                continue
        out.append(b)
    for b in out:
        # A heading line already prepended to the table serves as its caption; don't repeat it.
        if b.kind == "table" and not b.has_caption and b.n_heads == 0 and b.title:
            b.lines.insert(0, f"Caption: {b.title}")
            b.has_caption = True
    return out


def _split_text(text: str) -> list[str]:
    pieces = []
    while len(text) > SPLIT_ABOVE:
        cuts = [m.start() for m in _SENTENCE_END.finditer(text) if SPLIT_TARGET // 2 <= m.start() <= SPLIT_ABOVE]
        if cuts:
            cut = min(cuts, key=lambda c: abs(c - SPLIT_TARGET))
        else:
            cut = text.rfind(" ", 0, SPLIT_TARGET)
            cut = cut if cut > 0 else SPLIT_TARGET
        pieces.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    pieces.append(text)
    return pieces


def _split_table(b: _Block) -> list[str]:
    text = b.text
    if len(text) <= TABLE_SPLIT_ABOVE:
        return [text]
    lines = b.lines
    first = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("|"))
    last = first
    while last + 1 < len(lines) and lines[last + 1].lstrip().startswith("|"):
        last += 1
    prefix, rows, suffix = lines[:first], lines[first:last + 1], lines[last + 1:]
    head = rows[:2] if len(rows) > 1 and _TABLE_SEP.match(rows[1].strip()) else rows[:1]
    body = rows[len(head):]
    base = prefix + head
    groups, cur = [], []
    for row in body:
        if cur and len("\n".join(base + cur + [row])) > TABLE_GROUP_MAX:
            groups.append(cur)
            cur = []
        cur.append(row)
    groups.append(cur)
    out = ["\n".join(base + g) for g in groups]
    if suffix:
        out[-1] += "\n" + "\n".join(suffix)
    return out


def segment_document(doc: ParsedDoc) -> tuple[list[Element], dict[int, str]]:
    by_page: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for level, title, page in doc.outline:
        by_page[page].append((level, _clean_title(title)))
    has_outline = bool(doc.outline)

    outline_stack: list[tuple[int, str]] = []
    elements: list[Element] = []
    sections: dict[int, str] = {}
    for page in sorted(doc.pages, key=lambda p: p.page_no):
        for level, title in by_page.get(page.page_no, []):
            if title:
                _push(outline_stack, level, title)
        if has_outline:
            # Markdown headings refine this page only, nested under the outline.
            stack = list(outline_stack)
            md_base = stack[-1][0] if stack else 0
        else:
            stack, md_base = outline_stack, 0
        blocks = _merge(_blocks(page.markdown or "", stack, md_base))
        idx = 0
        for b in blocks:
            pieces = _split_table(b) if b.kind == "table" else _split_text(b.text)
            for piece in pieces:
                elements.append(Element(
                    element_id=f"{doc.doc_id}:p{page.page_no:04d}:e{idx:03d}",
                    doc_id=doc.doc_id, page_no=page.page_no, idx=idx, kind=b.kind,
                    section=b.section, text=re.sub(r"\n{3,}", "\n\n", piece).strip(),
                ))
                idx += 1
        sections[page.page_no] = _path(stack)
    return elements, sections


def mark_boilerplate(elements: list[Element], page_count: int, settings: Settings) -> int:
    groups: dict[str, list[Element]] = defaultdict(list)
    for e in elements:
        groups[text_hash(e.text)].append(e)
    count = 0
    for group in groups.values():
        pages = {e.page_no for e in group}
        if (len(norm_for_hash(group[0].text)) <= settings.boilerplate_max_chars
                and len(pages) >= settings.boilerplate_min_pages
                and len(pages) >= settings.boilerplate_page_frac * page_count):
            for e in group:
                if "boilerplate" not in e.flags:
                    e.flags.append("boilerplate")
                count += 1
    return count
