from typing import Dict, List

import pandas as pd

from .models import AuthorCandidate, ScholarPaper, WorkMatch
from .openalex import OpenAlexClient, works_to_matches
from .scholar import fetch_scholar_papers


RESULT_COLUMNS = [
    "title",
    "year",
    "journal",
    "doi",
    "citations",
    "metric_value",
    "metric_source",
    "h_index",
    "i10_index",
    "jcr_quartile",
    "cas_zone",
    "cas_subject",
    "jcr_category",
    "local_metric_source",
    "match_confidence",
    "source_type",
    "issn_l",
    "openalex_id",
    "notes",
]


def build_results_from_scholar_profile(
    profile_url: str,
    max_papers: int = 20,
    mailto: str = "",
) -> List[Dict[str, object]]:
    papers = fetch_scholar_papers(profile_url, limit=max_papers)
    client = OpenAlexClient(mailto=mailto)
    rows = []
    for paper in papers[:max_papers]:
        match = client.find_best_work_match(paper)
        rows.append(_row_from_match(match, client, fallback_paper=paper))
    return rows


def search_author_candidates(
    name: str,
    institution_keyword: str = "",
    per_page: int = 10,
    mailto: str = "",
) -> List[AuthorCandidate]:
    return OpenAlexClient(mailto=mailto).search_authors(
        name=name,
        institution_keyword=institution_keyword,
        per_page=per_page,
    )


def build_results_from_openalex_author(
    author_id: str,
    max_papers: int = 50,
    mailto: str = "",
) -> List[Dict[str, object]]:
    client = OpenAlexClient(mailto=mailto)
    works = client.works_for_author(author_id, max_works=max_papers)
    rows = []
    for match in works_to_matches(works):
        rows.append(_row_from_match(match, client))
    return rows


def results_to_dataframe(rows: List[Dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


def _row_from_match(
    match: WorkMatch,
    client: OpenAlexClient,
    fallback_paper: ScholarPaper = None,
) -> Dict[str, object]:
    metric = client.metric_for_source(match.source_id, match.issn_l)
    notes = " ".join(part for part in [match.notes, metric.notes] if part).strip()
    citations = match.cited_by_count
    if citations is None and fallback_paper:
        citations = fallback_paper.citations
    return {
        "title": match.title or (fallback_paper.title if fallback_paper else ""),
        "year": match.year or (fallback_paper.year if fallback_paper else None),
        "journal": match.journal,
        "doi": match.doi,
        "citations": citations,
        "metric_value": metric.metric_value,
        "metric_source": metric.metric_source,
        "h_index": metric.h_index,
        "i10_index": metric.i10_index,
        "jcr_quartile": "",
        "cas_zone": "",
        "cas_subject": "",
        "jcr_category": "",
        "local_metric_source": "",
        "match_confidence": match.match_confidence,
        "source_type": match.source_type,
        "issn_l": match.issn_l,
        "openalex_id": match.openalex_id,
        "notes": notes,
    }
