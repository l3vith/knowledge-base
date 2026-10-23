"""Windows defaults to a locale encoding (cp1252), macOS/Linux to UTF-8: every text read/write must say encoding="utf-8"."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text_io_without_encoding(path: Path) -> list[str]:
    bad = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        if name in ("read_text", "write_text"):
            bad.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno} {name}()")
        elif name == "open" and (isinstance(f, ast.Name) or (node.args and isinstance(node.args[0], ast.Constant))):
            # builtin open(path, mode) or Path.open(mode); binary modes need no encoding
            modes = [a.value for a in node.args + [k.value for k in node.keywords if k.arg == "mode"]
                     if isinstance(a, ast.Constant) and isinstance(a.value, str) and set(a.value) <= set("rwabxt+")]
            if not any("b" in m for m in modes):
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno} open()")
    return bad


def test_all_text_io_is_utf8():
    files = [p for d in ("kb", "scripts", "evaluation", "tests") for p in (ROOT / d).rglob("*.py")]
    bad = [b for p in files for b in _text_io_without_encoding(p)]
    assert not bad, "add encoding=\"utf-8\":\n" + "\n".join(bad)
