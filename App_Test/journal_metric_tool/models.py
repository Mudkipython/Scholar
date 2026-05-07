from dataclasses import dataclass
from typing import Optional


@dataclass
class ScholarPaper:
    title: str
    year: Optional[int] = None
    citations: Optional[int] = None
    scholar_url: Optional[str] = None
    authors: Optional[str] = None
    venue_hint: Optional[str] = None


@dataclass
class AuthorCandidate:
    id: str
    display_name: str
    institution: str = ""
    works_count: int = 0
    cited_by_count: int = 0
    topics: str = ""


@dataclass
class WorkMatch:
    title: str
    year: Optional[int]
    doi: str
    openalex_id: str
    journal: str
    source_id: str
    issn_l: str
    source_type: str
    cited_by_count: Optional[int]
    match_confidence: float
    notes: str = ""


@dataclass
class SourceMetric:
    metric_value: Optional[float]
    metric_source: str
    h_index: Optional[int] = None
    i10_index: Optional[int] = None
    notes: str = ""
