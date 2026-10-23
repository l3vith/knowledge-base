import re
import zipfile
from dataclasses import replace

import pytest

from kb.ingest.pipeline import index_collection
from kb.llm import FakeLLM
from kb.registry import Registry
from kb.remote import MemoryBackend
from kb.store import Store
from kb.testing import HashEmbedder, make_pdf


def _responder(name, system, user):
    if name == "doc_card":
        return {"title": "Alpha Bank Annual Report", "doc_type": "annual_report", "issuer": "Alpha Bank",
                "period_label": "FY2025", "period_year": 2025, "summary": "Annual report."}
    return {"pages": [{"page_no": int(n), "summary": f"card {n}"} for n in re.findall(r"=== page (\d+)", user)]}


def _zip(tmp_path):
    pdf = make_pdf(tmp_path / "src" / "a.pdf", ["Alpha bank capital ratio was 14.2 percent in FY2025.",
                                                "Liquidity coverage ratio stayed above the minimum."])
    z = tmp_path / "in.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.write(pdf, "a.pdf")
    return z


def test_generation_survives_ephemeral_disk(tmp_path, settings):
    remote = MemoryBackend()
    s1 = replace(settings, parse_workers=1, data_dir=tmp_path / "host1")
    out = index_collection(_zip(tmp_path), "c1", settings=s1, llm=FakeLLM(_responder), embedder=HashEmbedder(),
                           use_ocr=False, registry=Registry(s1, remote=remote))
    assert remote.pointers["c1"]["generation_id"] == out["generation_id"]
    assert all(k.startswith(f"c1/{out['generation_id']}/") and k.endswith(".gz") for k in remote.files)

    # A brand-new container with an empty disk: the generation is downloaded on first use.
    s2 = replace(settings, data_dir=tmp_path / "host2")
    gen_id, gen_dir = Registry(s2, remote=remote).active_dir("c1")
    assert gen_id == out["generation_id"] and (gen_dir / "kb.sqlite").is_file()
    store = Store.open(gen_dir)
    try:
        assert store.search_pages(["liquidity"], None, 1)[0][1] == 2
    finally:
        store.close()


def test_reindex_replaces_remote_generation(tmp_path, settings):
    remote = MemoryBackend()
    s1 = replace(settings, parse_workers=1)
    reg = Registry(s1, remote=remote)
    first = index_collection(_zip(tmp_path), "c1", settings=s1, llm=FakeLLM(_responder), embedder=HashEmbedder(),
                             use_ocr=False, registry=reg)
    second = index_collection(_zip(tmp_path), "c1", settings=s1, llm=FakeLLM(_responder), embedder=HashEmbedder(),
                              use_ocr=False, registry=reg)
    assert remote.pointers["c1"]["generation_id"] == second["generation_id"] != first["generation_id"]
    assert not any(k.startswith(f"c1/{first['generation_id']}/") for k in remote.files)  # old one freed


def test_failed_upload_activates_nothing(tmp_path, settings):
    class Broken(MemoryBackend):
        def put_file(self, key, data):
            raise ConnectionError("atlas down")

    s1 = replace(settings, parse_workers=1)
    with pytest.raises(ConnectionError):
        index_collection(_zip(tmp_path), "c1", settings=s1, llm=FakeLLM(_responder), embedder=HashEmbedder(),
                         use_ocr=False, registry=Registry(s1, remote=Broken()))
    assert not (s1.collection_dir("c1") / "active.json").exists()
