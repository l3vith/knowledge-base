"""One tiny LLM call (~$0.0001) to verify the key, endpoint, model, real token usage and the spend ledger.

    python scripts/check_llm.py
"""
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kb.config import get_settings  # noqa: E402
from kb.llm import OpenCodeLLM, spent_usd  # noqa: E402


def main() -> None:
    s = get_settings()
    if not s.opencode_api_key:
        sys.exit("OPENCODE_API_KEY is not set (put it in .env at the repo root)")
    print(f"endpoint={s.opencode_base_url}\nmodel={s.llm_model}\nbudget_cap={s.budget_usd}\nledger={s.ledger_path()}")
    models_url = s.opencode_base_url.rsplit("/chat/completions", 1)[0] + "/models"
    try:
        r = requests.get(models_url, headers={"Authorization": f"Bearer {s.opencode_api_key}"}, timeout=30)
        ids = [m.get("id") for m in r.json().get("data", [])] if r.ok else []
        print(f"models endpoint: HTTP {r.status_code}; {len(ids)} models: {ids[:40]}")
    except Exception as e:  # listing is informational only
        print(f"models endpoint not available: {e}")
    llm = OpenCodeLLM(s)
    out = llm.complete_json("Respond only with JSON.", 'Return {"ok": true, "word": "capital"}', name="check", max_tokens=400)
    print("response:", json.dumps(out))
    print("usage:", llm.usage)
    print(f"output tokens {llm.usage.output_tokens} for a ~10-token answer -> "
          f"{'reasoning tokens are being billed' if llm.usage.output_tokens > 60 else 'no large reasoning overhead'}")
    print(f"total recorded spend: {spent_usd(s):.6f} USD")


if __name__ == "__main__":
    main()
