import numpy as np
import pymupdf
import pytest
from fastapi.testclient import TestClient

import kb.llm as llm_mod
from kb.config import get_settings
from kb.errors import CollectionNotFound, KBError
from kb.llm import FakeLLM, LLMError, OpenCodeLLM, parallel_map
from kb.testing import FakeReranker, HashEmbedder, make_pdf, memory_store_from_texts
from kb.textutil import text_hash, tokens
from kb.tracing import StepTrace, clip, lf_span, lf_trace_id


class _Resp:
    def __init__(self, content, status=200, usage=None):
        self.status_code = status
        self.headers = {}
        self._data = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                      "usage": usage or {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}}

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _patch_post(monkeypatch, contents):
    calls = []

    def post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return _Resp(contents[min(len(calls) - 1, len(contents) - 1)])

    monkeypatch.setattr(llm_mod.requests, "post", post)
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    return calls


def test_fake_llm_records_calls_and_usage():
    llm = FakeLLM(lambda n, s, u: {"ok": True})
    assert llm.complete_json("sys", "user", name="plan") == {"ok": True}
    assert llm.calls == [("plan", "sys", "user")]
    assert llm.usage.calls == 1 and llm.usage.input_tokens == 100


def test_scoped_has_fresh_usage_and_shared_calls():
    llm = FakeLLM(lambda n, s, u: "t")
    llm.complete_text("s", "u", name="answer")
    child = llm.scoped()
    assert child.usage.calls == 0
    child.complete_text("s", "u", name="answer")
    assert child.usage.calls == 1 and len(llm.calls) == 2


def test_opencode_strips_fences_and_costs(monkeypatch, settings):
    calls = _patch_post(monkeypatch, ['```json\n{"a": 1}\n```'])
    llm = OpenCodeLLM(settings)
    assert llm.complete_json("s", "u", name="plan") == {"a": 1}
    assert calls[0]["response_format"] == {"type": "json_object"} and calls[0]["temperature"] == 0
    assert abs(llm.usage.cost_usd - 1.50) < 1e-9


def test_unknown_price_gives_null_cost(monkeypatch, tmp_path):
    _patch_post(monkeypatch, ["hello"])
    monkeypatch.setenv("PRICE_INPUT_PER_M", "")
    llm = OpenCodeLLM(get_settings(data_dir=tmp_path))
    assert llm.complete_text("s", "u", name="answer") == "hello"
    assert llm.usage.cost_usd is None


def test_empty_content_retries_then_raises(monkeypatch, settings):
    calls = _patch_post(monkeypatch, [None])
    with pytest.raises(LLMError):
        OpenCodeLLM(settings).complete_json("s", "u", name="plan")
    assert len(calls) == settings.llm_max_retries == 3


def test_spend_cap_blocks_calls_and_ledger_records(monkeypatch, tmp_path):
    calls = _patch_post(monkeypatch, ['{"a": 1}'])
    s = get_settings(data_dir=tmp_path, budget_usd=2.0, llm_cache=False)
    llm = OpenCodeLLM(s)
    llm.complete_json("s", "u", name="plan")          # costs 1.50 (1M in + 1M out)
    ledger = (tmp_path / "spend.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 1 and '"cost_usd": 1.5' in ledger[0]
    llm.complete_json("s", "u", name="plan")          # 1.50 < 2.0 -> allowed, total 3.0
    with pytest.raises(LLMError, match="spend cap"):
        llm.complete_json("s", "u", name="plan")      # 3.0 >= 2.0 -> blocked before any HTTP call
    assert len(calls) == 2


def test_response_cache_never_pays_twice(monkeypatch, tmp_path):
    calls = _patch_post(monkeypatch, ['{"a": 1}'])
    s = get_settings(data_dir=tmp_path)
    assert OpenCodeLLM(s).complete_json("s", "u", name="plan") == {"a": 1}
    llm = OpenCodeLLM(s)                       # new instance, same disk cache
    assert llm.complete_json("s", "u", name="plan") == {"a": 1}
    assert len(calls) == 1 and llm.usage.cache_hits == 1 and llm.usage.calls == 0
    llm.complete_json("s", "different prompt", name="plan")
    assert len(calls) == 2


def test_dryrun_llm_formats_and_estimates(tmp_path):
    from kb.llm import DryRunLLM, get_llm

    s = get_settings(data_dir=tmp_path, llm_mode="dryrun")
    llm = get_llm(s)
    assert isinstance(llm, DryRunLLM)
    plan = llm.complete_json("sys", "Rules...\nCatalogue:\n{}\n\nQuestion: What is the capital ratio of Alpha Bank?", name="plan")
    assert plan["aspects"][0]["keywords"][:2] == ["what", "is"] and plan["documents"] == []
    user = ("Question: capital ratio Alpha Bank\n\nAspects:\na1: x\n\nElements:\n"
            "[E1] f.pdf p.3 (text)\nAlpha Bank capital ratio was 14.2%.\n[E2] f.pdf p.4 (text)\nWeather report.")
    assert llm.complete_json("s", user, name="verify") == {"keep": [{"id": "E1", "aspects": ["a1"], "note": "dryrun lexical overlap"}]}
    with pytest.raises(LLMError):
        llm.complete_json("s", "x", name="doc_card")
    assert llm.usage.calls == 3 and llm.usage.input_tokens > 0 and llm.usage.cost_usd > 0


def test_load_dotenv_does_not_override(monkeypatch, tmp_path):
    from kb.config import load_dotenv

    env = tmp_path / ".env"
    env.write_text('# comment\nKB_TEST_A="from_file"\nKB_TEST_B=from_file\n', encoding="utf-8")
    monkeypatch.setenv("KB_TEST_B", "already_set")
    monkeypatch.delenv("KB_TEST_A", raising=False)
    load_dotenv(env)
    import os
    assert os.environ["KB_TEST_A"] == "from_file" and os.environ["KB_TEST_B"] == "already_set"
    monkeypatch.delenv("KB_TEST_A")


def test_parallel_map_order_and_errors():
    out = parallel_map(lambda x: 1 / x, [1, 0, 2], max_workers=3)
    assert out[0] == 1 and isinstance(out[1], ZeroDivisionError) and out[2] == 0.5


def test_step_trace_exact_keys_and_clip():
    t = StepTrace()
    t.add("query_planning", "d", {"q": "x" * 600}, {"ids": list(range(60))})
    step = t.to_list()[0]
    assert list(step) == ["step_name", "description", "input", "output"]
    assert len(step["input"]["q"]) == 503 and step["output"]["ids"][-1] == "... (+10 more)"
    assert clip("abc") == "abc"


def test_langfuse_noop_without_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    with lf_span("x") as s:
        s.update(output=1)
    assert lf_trace_id() is None


def test_tokens_and_hash():
    assert tokens('"NEAR" AND 10-K* asc 326-20: ₹') == ["10", "asc", "326", "20"]
    assert text_hash("Hello   World\n12") == text_hash("hello world")


def test_settings_env_and_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_CONCURRENCY", "3")
    monkeypatch.setenv("CE_TAU_LOW", "0.25")
    s = get_settings(data_dir=tmp_path)
    assert s.llm_concurrency == 3 and s.ce_tau_low == 0.25 and s.ce_tau_high is None
    assert s.collection_dir("c1") == tmp_path / "collections" / "c1"
    assert s.effective_answer_model() == s.llm_model
    with pytest.raises(TypeError):
        get_settings(nope=1)


def test_memory_store_search_and_dense():
    store = memory_store_from_texts({"d1": ["Net interest income rose.", "Gross NPA ratio was 3.1%.\n\nOther text here."]})
    assert store.search_pages(["NPA ratio"], ["d1"], 1)[0][:2] == ("d1", 2)
    assert store.dense_pages(HashEmbedder().embed(["gross npa ratio"]), None, 1)[0][:2] == ("d1", 2)
    assert [e.element_id for e in store.elements_for_pages("d1", [2])] == ["d1:p0002:e000", "d1:p0002:e001"]
    assert store.search_elements(["AND OR"], None, 5) == []
    assert store.nonblank_pages("d1") == [1, 2]


def test_fake_reranker_and_embedder_shapes():
    assert FakeReranker().score("capital ratio", ["capital ratio rose", "weather"]) == [1.0, 0.0]
    v = HashEmbedder().embed(["capital buffer ratio", ""])
    assert v.shape == (2, 256) and abs(np.linalg.norm(v[0]) - 1) < 1e-6


def test_make_pdf_image_only_page(tmp_path):
    p = make_pdf(tmp_path / "x.pdf", ["visible text here", "scanned words"], image_only_pages={1},
                 toc=[[1, "Intro", 1]])
    doc = pymupdf.open(p)
    assert "visible" in doc[0].get_text() and doc[1].get_text().strip() == "" and doc[1].get_images()
    assert doc.get_toc() == [[1, "Intro", 1]]


def test_api_exact_routes_and_error_shape():
    from kb.api import app

    client = TestClient(app)
    assert client.get("/health").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert {(r.path, method) for r in app.routes for method in r.methods} == {("/index", "POST"), ("/query", "POST")}
    body = CollectionNotFound("x").to_body("req_1")
    assert body["error"]["code"] == "COLLECTION_NOT_FOUND" and isinstance(KBError("A", "b", 400), Exception)


def test_budget_without_prices_blocks_calls(monkeypatch, tmp_path):
    calls = _patch_post(monkeypatch, ['{"a": 1}'])
    s = get_settings(data_dir=tmp_path, budget_usd=1.0, price_input_per_m=None, llm_cache=False)
    with pytest.raises(LLMError, match="cap cannot be enforced"):
        OpenCodeLLM(s).complete_json("s", "u", name="plan")
    assert calls == []


def test_dryrun_answers_query_track_json_payloads(tmp_path):
    import json

    from kb.llm import get_llm

    llm = get_llm(get_settings(data_dir=tmp_path, llm_mode="dryrun"))
    q, aspects = "Alpha Bank capital ratio", "a1: capital ratio | entity=None period=None scope=None"
    survey = llm.complete_json("s", json.dumps({"query": q, "aspects": aspects, "cards": [
        {"page_no": 3, "summary": "Alpha Bank capital ratio was 14.2%", "topics": []},
        {"page_no": 4, "summary": "Weather", "topics": []}]}), name="survey")
    assert survey == {"pages": [{"page_no": 3, "aspects": ["a1"], "strength": "medium"}]}
    text = "Alpha Bank capital ratio was 14.2% in FY2025."
    keep = llm.complete_json("s", json.dumps({"query": q, "aspects": aspects, "elements": [{"id": "E1", "text": text}]}),
                             name="verify")["keep"]
    assert keep[0]["id"] == "E1" and keep[0]["quotes"][0] in text
    ans = llm.complete_json("s", json.dumps({"query": q, "obligations": [{"id": "a1"}],
                                             "evidence": [{"id": "E1", "content": text}]}), name="answer")
    assert ans["status"] == "answered" and ans["claims"][0]["quotes"][0]["quote"] in text
    check = llm.complete_json("s", json.dumps({"claims": [{"claim_id": "c1"}]}), name="answer_verify")
    assert check["verdicts"][0]["verdict"] == "supported"
