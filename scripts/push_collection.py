"""Upload an already-built local collection's active generation to MongoDB Atlas (no re-indexing, no LLM calls).

    python scripts/push_collection.py --collection train      (needs MONGODB_URI in .env)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kb.config import get_settings  # noqa: E402
from kb.registry import Registry  # noqa: E402
from kb.remote import get_backend, upload_generation  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True)
    args = ap.parse_args()
    settings = get_settings()
    backend = get_backend(settings)
    if backend is None:
        sys.exit("MONGODB_URI is not set")
    local = Registry(settings)
    local.remote = None  # resolve the LOCAL active generation, not the remote one
    gen_id, gen_dir = local.active_dir(args.collection)
    upload_generation(backend, args.collection, gen_id, gen_dir)
    print(f"pushed {args.collection}/{gen_id} ({sum(f.stat().st_size for f in gen_dir.iterdir()) / 1e6:.0f} MB raw)")


if __name__ == "__main__":
    main()
