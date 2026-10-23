"""One tiny LLM call (~$0.0001) to verify auth (key or opencode CLI login), endpoint, qwen3.8-flash, token usage and the spend ledger.

    python scripts/check_llm.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import replace  # noqa: E402

from kb.config import get_settings  # noqa: E402
from kb.llm import OpenCodeLLM, spent_usd  # noqa: E402


def main() -> None:
    s = get_settings()
    source = "OPENCODE_API_KEY" if s.opencode_api_key else "opencode CLI login"
    if not s.opencode_api_key:
        from kb.opencode_auth import cli_headers
        cli_headers()  # fails here, before any spend, if the CLI is not logged in
    if s.budget_usd is None:
        sys.exit("Set KB_BUDGET_USD (e.g. 0.05) before a live call")
    print(f"auth={source}", f"model={s.llm_model} (thinking disabled)", f"budget_cap={s.budget_usd}",
          f"ledger={s.ledger_path()}", sep="\n")
    llm = OpenCodeLLM(replace(s, llm_cache=False))  # a cached reply would prove nothing
    out = llm.complete_json("Respond only with JSON.", 'Return {"ok": true, "word": "capital"}', name="check", max_tokens=400)
    print("response:", json.dumps(out))
    print("usage:", llm.usage)
    print(f"total recorded spend: {spent_usd(s):.6f} USD")


if __name__ == "__main__":
    main()
