"""OpenCode credentials from the logged-in CLI (`opencode auth export`), held in process memory only.

Used when OPENCODE_API_KEY is empty. The token and org ID are never logged, cached on disk or returned in errors.
Headers match the CLI's own requests: `authorization: Bearer <access>` plus `x-org-id`.
"""
import json
import shutil
import subprocess
import threading
import time

_lock = threading.Lock()
_cached: dict | None = None


class CLIAuthError(RuntimeError):
    pass


def _load() -> dict:
    exe = shutil.which("opencode")
    if not exe:
        raise CLIAuthError("OPENCODE_API_KEY is empty and the opencode CLI is not on PATH; run `opencode auth login`")
    try:
        out = subprocess.run([exe, "auth", "export"], capture_output=True, text=True, encoding="utf-8", timeout=60, check=True).stdout
        entries = json.loads(out)
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        raise CLIAuthError(f"could not read the opencode CLI login ({type(exc).__name__}); run `opencode auth login`") from None
    for entry in entries if isinstance(entries, list) else []:
        value = entry.get("value") or {}
        if entry.get("integrationID") == "opencode" and entry.get("active"):
            token = value.get("access") if value.get("type") == "oauth" else value.get("key")
            if not isinstance(token, str) or not token:
                break
            expires = value.get("expires")
            expires = expires / 1000 if isinstance(expires, (int, float)) and expires > 1e11 else expires
            org = (value.get("metadata") or {}).get("orgID")
            return {"token": token, "org": org if isinstance(org, str) else None,
                    "expires": expires if isinstance(expires, (int, float)) else None}
    raise CLIAuthError("no active OpenCode login in the opencode CLI; run `opencode auth login`")


def cli_headers() -> dict:
    """Authorization headers from the CLI login; re-read when the access token is within 5 minutes of expiry."""
    # ponytail: no refresh call of our own; the CLI refreshes its token when it runs, and we re-export near expiry.
    global _cached
    with _lock:
        if _cached is None or (_cached["expires"] and _cached["expires"] - time.time() < 300):
            _cached = _load()
            if _cached["expires"] and _cached["expires"] - time.time() < 300:
                raise CLIAuthError("the opencode CLI login has expired; run any opencode command or `opencode auth login`")
        headers = {"Authorization": f"Bearer {_cached['token']}"}
        if _cached["org"]:
            headers["x-org-id"] = _cached["org"]
        return headers
