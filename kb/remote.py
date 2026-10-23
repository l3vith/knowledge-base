"""Optional MongoDB Atlas persistence for collection generations (free-tier hosts have ephemeral disks).

A finished generation's files are gzipped into GridFS under "<collection>/<generation_id>/<file>.gz"; a small
pointer document per collection names the active generation and its files. The pointer is switched only after
every file is uploaded, so a failed upload never activates a partial generation. Enabled when MONGODB_URI is set.
"""
import gzip
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

log = logging.getLogger("kb.remote")


class RemoteBackend(Protocol):
    def put_file(self, key: str, data: bytes) -> None: ...
    def get_file(self, key: str) -> bytes | None: ...
    def delete_prefix(self, prefix: str) -> None: ...
    def get_pointer(self, name: str) -> dict | None: ...
    def set_pointer(self, name: str, doc: dict) -> None: ...


class GridFSBackend:
    def __init__(self, uri: str, db_name: str):
        import gridfs
        from pymongo import MongoClient

        self._db = MongoClient(uri, serverSelectionTimeoutMS=15000)[db_name]
        self._fs = gridfs.GridFSBucket(self._db, bucket_name="kb_files")
        self._pointers = self._db["collections"]

    def put_file(self, key: str, data: bytes) -> None:
        self.delete_prefix(key)  # GridFS allows duplicate names; keep exactly one
        self._fs.upload_from_stream(key, data)

    def get_file(self, key: str) -> bytes | None:
        import gridfs
        try:
            return self._fs.open_download_stream_by_name(key).read()
        except gridfs.errors.NoFile:
            return None

    def delete_prefix(self, prefix: str) -> None:
        import re
        for f in self._db["kb_files.files"].find({"filename": {"$regex": "^" + re.escape(prefix)}}, {"_id": 1}):
            self._fs.delete(f["_id"])

    def get_pointer(self, name: str) -> dict | None:
        return self._pointers.find_one({"_id": name})

    def set_pointer(self, name: str, doc: dict) -> None:
        self._pointers.replace_one({"_id": name}, {"_id": name, **doc}, upsert=True)


class MemoryBackend:
    """In-process stand-in used by tests."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.pointers: dict[str, dict] = {}

    def put_file(self, key, data):
        self.files[key] = data

    def get_file(self, key):
        return self.files.get(key)

    def delete_prefix(self, prefix):
        for k in [k for k in self.files if k.startswith(prefix)]:
            del self.files[k]

    def get_pointer(self, name):
        return self.pointers.get(name)

    def set_pointer(self, name, doc):
        self.pointers[name] = {"_id": name, **doc}


_backend_lock = threading.Lock()
_backends: dict[tuple[str, str], RemoteBackend] = {}


def get_backend(settings) -> RemoteBackend | None:
    if not settings.mongodb_uri:
        return None
    key = (settings.mongodb_uri, settings.mongodb_db)
    with _backend_lock:
        if key not in _backends:
            _backends[key] = GridFSBackend(*key)
        return _backends[key]


def upload_generation(backend: RemoteBackend, name: str, gen_id: str, gen_dir: Path) -> None:
    files = sorted(p.name for p in Path(gen_dir).iterdir() if p.is_file() and not p.name.endswith(("-wal", "-shm")))
    for fname in files:
        backend.put_file(f"{name}/{gen_id}/{fname}.gz", gzip.compress((Path(gen_dir) / fname).read_bytes(), 6))
    previous = (backend.get_pointer(name) or {}).get("generation_id")
    backend.set_pointer(name, {"generation_id": gen_id, "files": files,
                               "promoted_at": datetime.now(timezone.utc).isoformat()})
    if previous and previous != gen_id:  # Atlas free storage is small: keep only the active generation remotely
        backend.delete_prefix(f"{name}/{previous}/")
    log.info("uploaded %s/%s (%d files) to remote storage", name, gen_id, len(files))


def download_generation(backend: RemoteBackend, name: str, pointer: dict, dest: Path) -> Path:
    """Download into dest + '.download', then rename to dest (atomic on success)."""
    tmp = Path(str(dest) + ".download")
    tmp.mkdir(parents=True, exist_ok=True)
    for fname in pointer["files"]:
        data = backend.get_file(f"{name}/{pointer['generation_id']}/{fname}.gz")
        if data is None:
            raise FileNotFoundError(f"remote file missing: {name}/{pointer['generation_id']}/{fname}")
        (tmp / fname).write_bytes(gzip.decompress(data))
    tmp.rename(dest)
    return dest
