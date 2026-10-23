"""Collection generations on disk: staging, atomic promotion via active.json, per-collection indexing lock."""
import json
import os
import secrets
import shutil
import threading
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


_POINTER_TTL_S = 30.0
_pointer_cache: dict[str, tuple[float, dict]] = {}
_sync_locks: dict[str, threading.Lock] = {}
_sync_guard = threading.Lock()


class Registry:
    def __init__(self, settings: Settings, remote=None):
        from kb.remote import get_backend

        self.settings = settings
        self.remote = remote if remote is not None else get_backend(settings)

    def _root(self, name: str) -> Path:
        return self.settings.collection_dir(name)

    def _remote_pointer(self, name: str) -> dict | None:
        now = time.monotonic()
        key = f"{id(self.remote)}:{name}"
        cached = _pointer_cache.get(key)
        if cached and now - cached[0] < _POINTER_TTL_S:
            return cached[1]
        pointer = self.remote.get_pointer(name)
        if pointer:
            _pointer_cache[key] = (now, pointer)
        return pointer

    def _sync_from_remote(self, name: str) -> None:
        """Make the remote active generation available locally (cold start on an ephemeral-disk host)."""
        from kb.remote import download_generation

        pointer = self._remote_pointer(name)
        if not pointer:
            return
        gen_id = pointer["generation_id"]
        final = self._root(name) / "generations" / gen_id
        with _sync_guard:
            lock = _sync_locks.setdefault(name, threading.Lock())
        with lock:
            if not final.is_dir():
                final.parent.mkdir(parents=True, exist_ok=True)
                shutil.rmtree(str(final) + ".download", ignore_errors=True)
                download_generation(self.remote, name, pointer, final)
            if self._read_active(name) != gen_id:
                self._write_active(self._root(name), gen_id)

    def _read_active(self, name: str) -> str | None:
        try:
            return json.loads((self._root(name) / "active.json").read_text(encoding="utf-8"))["generation_id"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def active_dir(self, name: str) -> tuple[str, Path]:
        if self.remote is not None:
            self._sync_from_remote(name)
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
        if self.remote is not None:  # upload first: a failed upload must not activate anything anywhere
            from kb.remote import upload_generation
            upload_generation(self.remote, name, generation_id, Path(staging))
            _pointer_cache.pop(f"{id(self.remote)}:{name}", None)
        final = root / "generations" / generation_id
        previous = self._read_active(name)
        Path(staging).rename(final)
        self._write_active(root, generation_id)
        self._cleanup(root, keep={generation_id, previous})
        return final

    @staticmethod
    def _write_active(root: Path, generation_id: str) -> None:
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

    @staticmethod
    def _cleanup(root: Path, keep: set) -> None:
        # ponytail: no in-process refcount; a generation still open by a query is deleted best-effort
        # (Windows leaves the locked sqlite files, retried at the next promote; Store loads vectors eagerly).
        for d in (root / "generations").iterdir():
            if d.is_dir() and not d.name.endswith(STAGING_SUFFIX) and d.name not in keep:
                shutil.rmtree(d, ignore_errors=True)

    def discard(self, staging: Path) -> None:
        shutil.rmtree(staging, ignore_errors=True)
