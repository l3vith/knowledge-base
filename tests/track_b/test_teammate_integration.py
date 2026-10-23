"""Real PDF/SQLite/vector integration with Person 1; LLM responses remain synthetic."""
from dataclasses import replace
import re
import zipfile
from fastapi.testclient import TestClient
from kb.config import get_settings
from kb.ingest.pipeline import index_collection
from kb.llm import FakeLLM as FoundationFakeLLM
from kb.registry import Registry
from kb.store import Store
from kb.testing import HashEmbedder,make_pdf
from kb.query.observability import LocalSink
from kb.query.demo_app import create_query_app
from kb.routes.query import BoundServices
from .helpers import FakeLLM,settings


def ingestion_response(name,system,user):
    if name=="doc_card":
        return {"title":"Synthetic Annual Report","doc_type":"annual_report","issuer":"Synthetic Bank", "entities":["Synthetic Bank"],
                "period_label":"FY2025","period_year":2025,"publication_date":None,"jurisdiction":"","topics":["capital"],"summary":"Synthetic fixture."}
    numbers=[int(n) for n in re.findall(r"=== page (\d+)",user)]
    return {"pages":[{"page_no":n,"summary":"Source page about capital ratios and buffers", "topics":["capital"],"entities":[],"figures":[]} for n in numbers]}


def archive(tmp_path,name,text):
    pdf=make_pdf(tmp_path/(name+".pdf"),[text])
    path=tmp_path/(name+".zip")
    with zipfile.ZipFile(path,"w") as z:
        z.write(pdf,pdf.name)
    return path


def test_actual_index_to_query_two_collections_and_reindex_snapshot(tmp_path):
    shared=get_settings(data_dir=tmp_path/"data",parse_workers=1,price_input_per_m=None,price_output_per_m=None)
    emb=HashEmbedder()
    first=index_collection(archive(tmp_path,"one","Capital ratio was 14 percent for Cobalt Bank during FY2025 under the published capital framework."),"one",settings=shared,llm=FoundationFakeLLM(ingestion_response),embedder=emb,use_ocr=False)
    second=index_collection(archive(tmp_path,"two","Capital ratio was 22 percent for Amber Bank during FY2025 under the published capital framework."),"two",settings=shared,llm=FoundationFakeLLM(ingestion_response),embedder=emb,use_ocr=False)
    registry=Registry(shared)
    old_gen,old_path=registry.active_dir("one")
    old_store=Store.open(old_path)
    def binder(name):
        generation,directory=registry.active_dir(name)
        return BoundServices(Store.open(directory),generation,settings(tmp_path),FakeLLM(),embedder=emb,sink=LocalSink(),close_store=True)
    client=TestClient(create_query_app(binder))
    one=client.post("/query",json={"collection_name":"one","query":"capital ratio"})
    two=client.post("/query",json={"collection_name":"two","query":"capital ratio"})
    assert one.status_code==two.status_code==200
    a,b=one.json(),two.json()
    assert "14 percent" in a["answer"] and "22 percent" not in a["answer"]
    assert "22 percent" in b["answer"] and "14 percent" not in b["answer"]
    assert a["generation_id"]==first["generation_id"] and b["generation_id"]==second["generation_id"]
    assert a["chunks"][0]["document"]=="one.pdf" and a["chunks"][0]["page"]==1
    updated=index_collection(archive(tmp_path,"new","Capital ratio was 31 percent for Cobalt Bank during FY2026 under the updated capital framework."),"one",settings=shared,llm=FoundationFakeLLM(ingestion_response),embedder=emb,use_ocr=False)
    assert updated["generation_id"]!=old_gen
    assert any("14 percent" in e.text for c in old_store.docs() for e in old_store.elements_for_pages(c.doc_id,[1],include_boilerplate=True))
    old_store.close()
    current=client.post("/query",json={"collection_name":"one","query":"capital ratio"}).json()
    assert "31 percent" in current["answer"] and "14 percent" not in current["answer"]
