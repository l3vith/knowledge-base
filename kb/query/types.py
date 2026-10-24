"""Track B owns these query records; source records are structural, not M0 imports."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Aspect:
    aspect_id: str
    text: str
    keywords: list[str]
    entity: str | None = None
    period: str | None = None
    scope: str | None = None


@dataclass
class QueryPlan:
    intent: str
    aspects: list[Aspect]
    doc_ids: list[str]
    doc_reasons: dict[str, str] = field(default_factory=dict)
    answerable: bool = True
    notes: str = ""
    limitations: list[str] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SurveyPick:
    doc_id: str
    page_no: int
    aspect_ids: list[str]
    strength: str = "medium"


@dataclass
class Candidate:
    element: Any
    aspect_ids: list[str]
    sources: list[str]
    ce_score: float | None = None
    metadata_score: float = 0.0


@dataclass
class Evidence:
    element: Any
    aspect_ids: list[str]
    note: str = ""
    selected_by: str = "llm"
    ce_score: float | None = None
    quotes: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    fact_value: str | None = None
    relevance: str = "direct"
    findings: list[dict[str, Any]] = field(default_factory=list)
    requirement_ids: list[str] = field(default_factory=list)  # requested topics the verifier tagged


@dataclass(frozen=True)
class SourceFragment:
    element_id: str
    doc_id: str
    page_no: int
    idx: int
    kind: str
    section: str
    text: str
    flags: list[str] = field(default_factory=list)
    parent_element_id: str | None = None
    char_start: int = 0
    char_end: int | None = None


@dataclass
class Claim:
    claim_id: str
    text: str
    evidence_ids: list[str]
    aspect_ids: list[str]
    quotes: list[dict[str, str]] = field(default_factory=list)
    calculation: dict[str, Any] | None = None
    verification: str = "pending"
    requirement_ids: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)
    section: str = ""  # synthesis answers: heading the statement is rendered under
    kind: str = "finding"  # finding | inference | gap (gap = requested item the evidence does not show)
    fact_ids: list[str] = field(default_factory=list)  # inventoried facts this statement carries with all their figures


@dataclass
class AnswerDraft:
    claims: list[Claim]
    status: str
    limitations: list[str] = field(default_factory=list)
    requested_topics: list[dict[str, Any]] = field(default_factory=list)
    ledger_records: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)  # synthesis fact inventory the final answer must carry
    worksheet: list[dict[str, Any]] = field(default_factory=list)
