"""Collection generations on disk: staging, atomic promotion via active.json, per-collection indexing lock."""
import json
import os
import secrets
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from kb.config import Settings
from kb.errors import CollectionNotFound, KBError

LOCK_STALE_S = 6 * 3600
STAGING_SUFFIX = ".staging"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Registry:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _root(self, name: str) -> Path:
        return self.settings.collection_dir(name)

    def _read_active(self, name: str) -> str | None:
        try:
            return json.loads((self._root(name) / "active.json").read_text(encoding="utf-8"))["generation_id"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def active_dir(self, name: str) -> tuple[str, Path]:
        gen_id = self._read_active(name)
        gen_dir = self._root(name) / "generations" / gen_id if gen_id else None
        if gen_dir is None or not gen_dir.is_dir():
            raise CollectionNotFound(name)
        return gen_id, gen_dir

    @contextmanager
    def indexing_lock(self, name: str):
        root = self._root(name)
        root.mkdir(parents=True, exist_ok=True)
        lock = root / ".lock"
        for attempt in range(2):
            try:
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    stale = time.time() - lock.stat().st_mtime > LOCK_STALE_S
                except FileNotFoundError:
                    stale = True  # released between our open and stat
                if attempt == 0 and stale:
                    lock.unlink(missing_ok=True)
                    continue
                raise KBError("COLLECTION_BUSY", f"Collection '{name}' is already being indexed.", 409,
                              retryable=True, details={"collection_name": name})
        try:
            os.write(fd, json.dumps({"pid": os.getpid(), "since": _utc_now().isoformat()}).encode())
            os.close(fd)
            yield
        finally:
            lock.unlink(missing_ok=True)

    def new_staging(self, name: str) -> tuple[str, Path]:
        gen_id = f"gen_{_utc_now():%Y%m%d%H%M%S}_{secrets.token_hex(4)}"
        staging = self._root(name) / "generations" / f"{gen_id}{STAGING_SUFFIX}"
        staging.mkdir(parents=True)
        return gen_id, staging

    def promote(self, name: str, generation_id: str, staging: Path) -> Path:
        """Caller must have closed every Store on `staging` (Windows cannot rename a dir with open files)."""
        root = self._root(name)
        final = root / "generations" / generation_id
        previous = self._read_active(name)
        Path(staging).rename(final)
        tmp = root / f"active.json.{secrets.token_hex(4)}.tmp"
        tmp.write_text(json.dumps({"generation_id": generation_id, "promoted_at": _utc_now().isoformat()}), encoding="utf-8")
        for attempt in range(5):  # Windows: os.replace fails while a reader briefly has active.json open
            try:
                os.replace(tmp, root / "active.json")
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1)
        self._cleanup(root, keep={generation_id, previous})
        return final

    @staticmethod
    def _cleanup(root: Path, keep: set) -> None:
        # ponytail: no in-process refcount; a generation still open by a query is deleted best-effort
        # (Windows leaves the locked sqlite files, retried at the next promote; Store loads vectors eagerly).
        for d in (root / "generations").iterdir():
            if d.is_dir() and not d.name.endswith(STAGING_SUFFIX) and d.name not in keep:
                shutil.rmtree(d, ignore_errors=True)

    def discard(self, staging: Path) -> None:
        shutil.rmtree(staging, ignore_errors=True)
