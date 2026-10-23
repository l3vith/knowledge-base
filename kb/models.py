"""Shared data types and protocols. The only types that cross module boundaries."""
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

INTENTS = ("factoid", "analytical", "exhaustive")
BLANK_PAGE_SUMMARY = "(blank or image-only page)"


@dataclass
class PageText:
    page_no: int
    markdown: str
    is_ocr: bool
    toc_titles: list[str]
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDoc:
    doc_id: str
    file_name: str
    page_count: int
    pages: list[PageText]
    outline: list[tuple[int, str, int]]
    pdf_metadata: dict
    ocr_unavailable_pages: int = 0


@dataclass
class Element:
    element_id: str
    doc_id: str
    page_no: int
    idx: int
    kind: str  # "text" | "table"
    section: str
    text: str
    flags: list[str] = field(default_factory=list)  # may contain "boilerplate"


@dataclass
class DocCard:
    doc_id: str
    file_name: str
    title: str
    doc_type: str
    issuer: str
    entities: list[str]
    period_label: str
    period_year: int | None
    publication_date: str | None
    jurisdiction: str
    topics: list[str]
    summary: str
    page_count: int
    identifiers: list[str] = field(default_factory=list)
    sibling_group: str | None = None
    navigation: dict = field(default_factory=dict)


@dataclass
class PageCard:
    doc_id: str
    page_no: int
    section: str
    summary: str
    topics: list[str]
    entities: list[str]
    figures: list[str]


@dataclass
class Aspect:
    aspect_id: str
    text: str
    keywords: list[str]


@dataclass
class QueryPlan:
    intent: str
    aspects: list[Aspect]
    doc_ids: list[str]
    doc_reasons: dict[str, str]
    answerable: bool
    notes: str


@dataclass
class SurveyPick:
    doc_id: str
    page_no: int
    aspect_ids: list[str]
    strength: str  # "high" | "lexical" | "medium"


@dataclass
class Candidate:
    element: Element
    aspect_ids: list[str]
    sources: list[str]  # subset of survey_high, survey_lexical, survey_medium, hybrid, escape
    ce_score: float | None = None


@dataclass
class Evidence:
    element: Element
    aspect_ids: list[str]
    note: str
    selected_by: str  # "llm" | "auto_keep"
    ce_score: float | None = None


class StoreProtocol(Protocol):
    def docs(self) -> list[DocCard]: ...
    def doc(self, doc_id: str) -> DocCard: ...
    def page_cards(self, doc_id: str, page_nos: list[int] | None = None) -> list[PageCard]: ...
    def nonblank_pages(self, doc_id: str) -> list[int]: ...
    def elements_for_pages(self, doc_id: str, page_nos: list[int], include_boilerplate: bool = False) -> list[Element]: ...
    def elements_by_ids(self, element_ids: list[str]) -> list[Element]: ...
    def search_pages(self, terms: list[str], doc_ids: list[str] | None, limit: int) -> list[tuple[str, int, float]]: ...
    def dense_pages(self, query_vecs: np.ndarray, doc_ids: list[str] | None, limit: int) -> list[tuple[str, int, float]]: ...
    def search_elements(self, terms: list[str], doc_ids: list[str] | None, limit: int) -> list[tuple[str, float]]: ...
    def dense_elements(self, query_vecs: np.ndarray, doc_ids: list[str] | None, limit: int) -> list[tuple[str, float]]: ...


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...
