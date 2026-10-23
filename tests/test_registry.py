import json
import os
import time

import pytest

from kb.errors import CollectionNotFound, KBError
from kb.registry import Registry
from kb.store import Store


def _promote_one(reg, name="c1"):
    gen_id, staging = reg.new_staging(name)
    assert staging.name == f"{gen_id}.staging" and staging.is_dir()
    s = Store.create(staging)
    s.close()
    (staging / "manifest.json").write_text("{}")
    return gen_id, reg.promote(name, gen_id, staging)


def test_registry_promote_and_active(settings):
    reg = Registry(settings)
    with pytest.raises(CollectionNotFound):
        reg.active_dir("c1")
    ids = []
    for _ in range(3):
        gen_id, final = _promote_one(reg)
        ids.append(gen_id)
        assert reg.active_dir("c1") == (gen_id, final)
        assert (final / "manifest.json").is_file()
    gens = sorted(p.name for p in (settings.collection_dir("c1") / "generations").iterdir())
    assert gens == sorted(ids[1:])  # active + previous only
    assert json.loads((settings.collection_dir("c1") / "active.json").read_text())["generation_id"] == ids[2]
    assert ids[0].startswith("gen_") and len(ids[0]) == len("gen_20261023120000_abcdef12")


def test_registry_lock_busy(settings):
    reg = Registry(settings)
    with reg.indexing_lock("c1"):
        with pytest.raises(KBError) as exc:
            with reg.indexing_lock("c1"):
                pass
        assert exc.value.code == "COLLECTION_BUSY" and exc.value.http_status == 409 and exc.value.retryable
    with reg.indexing_lock("c1"):  # released
        pass


def test_registry_stale_lock_taken_over(settings):
    reg = Registry(settings)
    lock = settings.collection_dir("c1") / ".lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("{}")
    old = time.time() - 7 * 3600
    os.utime(lock, (old, old))
    with reg.indexing_lock("c1"):
        assert lock.exists()
    assert not lock.exists()


def test_registry_discard(settings):
    reg = Registry(settings)
    _, staging = reg.new_staging("c1")
    Store.create(staging).close()
    reg.discard(staging)
    assert not staging.exists()
    with pytest.raises(CollectionNotFound):
        reg.active_dir("c1")
