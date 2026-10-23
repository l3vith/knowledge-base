from kb.query.candidates import candidate_pages, element_retrieval
from kb.query.screen import local_survey_pages
from kb.query.triage import element_triage
from kb.query.types import Aspect, QueryPlan
from kb.store import fts_query
from .helpers import MemoryStore, settings

PAGES=[f"Speed result {i}: calibration took {i} seconds." for i in range(1,24)]+["In conclusion, the surrogate cannot extrapolate."]


def plan():
    return QueryPlan("analytical",[Aspect("a1","calibration speed",["speed","calibration"])],["a"])


def test_decisive_limitation_on_the_last_page_reaches_verification(tmp_path):
    store=MemoryStore({"a":PAGES});s=settings(tmp_path)
    pool,lexical,report=candidate_pages(store,plan(),"calibration speed and limitations",None,s)
    picks,_=local_survey_pages(plan(),pool,lexical,report,s)
    assert {p.page_no for p in picks}==set(range(1,25))  # short document: every page eligible
    candidates,_=element_retrieval(store,plan(),"calibration speed and limitations",[],[],None,s)
    last=[c for c in candidates if c.element.page_no==24]
    assert last and "structure" in last[0].sources  # found by the conclusion search even with no page survey
    _,middle,_=element_triage(candidates,plan(),None,settings(tmp_path,verify_chars_total=200))
    assert middle[0].element.page_no==24  # verified first, before the budget runs out


def test_letter_digit_terms_also_match_their_split_markdown_form():
    assert fts_query(["i7","speed"])=='"i7" OR "speed" OR "i 7"'
