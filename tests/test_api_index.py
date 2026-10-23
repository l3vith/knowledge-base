import io
import re
import zipfile
from dataclasses import replace

from fastapi.testclient import TestClient

import kb.routes.index as route
from kb.api import app
from kb.llm import FakeLLM
from kb.testing import HashEmbedder, make_pdf


def card_responder(name, system, user):
    if name == "doc_card":
        return {"title": "Alpha Bank Annual Report", "doc_type": "annual_report", "issuer": "Alpha Bank",
                "period_label": "FY2025", "period_year": 2025, "summary": "Annual report."}
    return {"pages": [{"page_no": int(n), "summary": f"card for page {n}"} for n in re.findall(r"=== page (\d+)", user)]}


def _client(monkeypatch, settings):
    s = replace(settings, parse_workers=1)
    monkeypatch.setattr(route, "get_settings", lambda: s)
    monkeypatch.setattr(route, "get_llm", lambda _s: FakeLLM(card_responder))
    monkeypatch.setattr(route, "get_embedder", lambda _s: HashEmbedder())
    return TestClient(app)


def test_api_index_ok(tmp_path, settings, monkeypatch):
    pdf = make_pdf(tmp_path / "a.pdf", ["Alpha bank capital ratio was 14.2 percent in FY2025."]).read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.pdf", pdf)
    r = _client(monkeypatch, settings).post("/index", files={"file": ("d.zip", buf.getvalue(), "application/zip")},
                                            data={"collection_name": "c1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ready" and body["documents"] == 1 and body["generation_id"].startswith("gen_")


def test_api_index_errors(tmp_path, settings, monkeypatch):
    client = _client(monkeypatch, settings)
    r = client.post("/index", files={"file": ("d.zip", b"nope", "application/zip")}, data={"collection_name": "c1"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "INVALID_ARCHIVE" and body["request_id"].startswith("req_")
    r = client.post("/index", files={"file": ("d.zip", b"nope", "application/zip")}, data={"collection_name": "bad name"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_COLLECTION_NAME"
    r = client.post("/index", data={"collection_name": "c1"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"
