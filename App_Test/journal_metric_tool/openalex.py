import time
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

import requests

from .models import AuthorCandidate, ScholarPaper, SourceMetric, WorkMatch


OPENALEX_API = "https://api.openalex.org"


class OpenAlexClient:
    def __init__(self, mailto: str = "", timeout: int = 30, polite_delay: float = 0.1):
        self.timeout = timeout
        self.polite_delay = polite_delay
        self.session = requests.Session()
        self.source_cache: Dict[str, SourceMetric] = {}
        self.params = {"mailto": mailto} if mailto else {}

    def _get(self, path_or_url: str, params: Optional[dict] = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else f"{OPENALEX_API}{path_or_url}"
        merged = dict(self.params)
        if params:
            merged.update(params)
        response = self.session.get(url, params=merged, timeout=self.timeout)
        response.raise_for_status()
        if self.polite_delay:
            time.sleep(self.polite_delay)
        return response.json()

    def search_authors(self, name: str, institution_keyword: str = "", per_page: int = 10) -> List[AuthorCandidate]:
        data = self._get("/authors", {"search": name, "per-page": per_page})
        candidates = [_author_from_json(item) for item in data.get("results", [])]
        keyword = institution_keyword.strip().lower()
        if keyword:
            candidates.sort(key=lambda c: keyword in c.institution.lower(), reverse=True)
        return candidates

    def works_for_author(self, author_id: str, max_works: int = 50) -> List[dict]:
        clean_id = author_id.rstrip("/").split("/")[-1]
        data = self._get(
            "/works",
            {
                "filter": f"authorships.author.id:{clean_id}",
                "sort": "publication_date:desc",
                "per-page": max(1, min(max_works, 200)),
            },
        )
        return data.get("results", [])

    def find_best_work_match(self, paper: ScholarPaper) -> WorkMatch:
        data = self._get("/works", {"search": paper.title, "per-page": 5})
        candidates = data.get("results", [])
        if not candidates:
            return WorkMatch(
                title=paper.title,
                year=paper.year,
                doi="",
                openalex_id="",
                journal="",
                source_id="",
                issn_l="",
                source_type="",
                cited_by_count=paper.citations,
                match_confidence=0.0,
                notes="No OpenAlex work match found.",
            )

        best = max(candidates, key=lambda item: _work_score(paper, item))
        match = work_to_match(best, requested_title=paper.title, requested_year=paper.year)
        if paper.citations is not None:
            match.cited_by_count = paper.citations
        return match

    def metric_for_source(self, source_id: str = "", issn_l: str = "") -> SourceMetric:
        cache_key = source_id or issn_l
        if not cache_key:
            return SourceMetric(
                metric_value=None,
                metric_source="OpenAlex",
                notes="No journal source or ISSN-L found for this work.",
            )
        if cache_key in self.source_cache:
            return self.source_cache[cache_key]

        if source_id:
            clean_id = source_id.rstrip("/").split("/")[-1]
            path = f"/sources/{clean_id}"
        else:
            path = f"/sources/issn:{quote(issn_l)}"

        try:
            source = self._get(path)
            stats = source.get("summary_stats") or {}
            metric = SourceMetric(
                metric_value=stats.get("2yr_mean_citedness"),
                metric_source="OpenAlex 2-year mean citedness (not official JIF)",
                h_index=stats.get("h_index"),
                i10_index=stats.get("i10_index"),
                notes="" if stats.get("2yr_mean_citedness") is not None else "OpenAlex source has no 2-year metric.",
            )
        except requests.HTTPError:
            metric = SourceMetric(
                metric_value=None,
                metric_source="OpenAlex",
                notes="OpenAlex source lookup failed.",
            )
        self.source_cache[cache_key] = metric
        return metric


def works_to_matches(works: Iterable[dict]) -> List[WorkMatch]:
    return [work_to_match(work, requested_title=work.get("title") or "", requested_year=work.get("publication_year")) for work in works]


def work_to_match(work: dict, requested_title: str = "", requested_year: Optional[int] = None) -> WorkMatch:
    source = _source_from_work(work)
    score = _work_score(
        ScholarPaper(title=requested_title or work.get("title") or "", year=requested_year),
        work,
    )
    notes = []
    if not source.get("display_name"):
        notes.append("No journal/source found in OpenAlex.")
    if source.get("type") and source.get("type") != "journal":
        notes.append(f"Source type is {source.get('type')}, not journal.")
    if requested_year and work.get("publication_year") and abs(int(work["publication_year"]) - int(requested_year)) > 1:
        notes.append("OpenAlex year differs from Scholar year.")

    return WorkMatch(
        title=work.get("title") or requested_title,
        year=work.get("publication_year") or requested_year,
        doi=(work.get("doi") or "").replace("https://doi.org/", ""),
        openalex_id=work.get("id") or "",
        journal=source.get("display_name") or "",
        source_id=source.get("id") or "",
        issn_l=source.get("issn_l") or "",
        source_type=source.get("type") or "",
        cited_by_count=work.get("cited_by_count"),
        match_confidence=round(score, 3),
        notes=" ".join(notes),
    )


def _author_from_json(item: dict) -> AuthorCandidate:
    institution = (item.get("last_known_institution") or {}).get("display_name") or ""
    topics = ", ".join(
        topic.get("display_name", "")
        for topic in (item.get("topics") or [])[:3]
        if topic.get("display_name")
    )
    return AuthorCandidate(
        id=item.get("id") or "",
        display_name=item.get("display_name") or "",
        institution=institution,
        works_count=item.get("works_count") or 0,
        cited_by_count=item.get("cited_by_count") or 0,
        topics=topics,
    )


def _source_from_work(work: dict) -> dict:
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    if source:
        return source
    for location in work.get("locations") or []:
        if location.get("source"):
            return location["source"]
    return {}


def _work_score(paper: ScholarPaper, work: dict) -> float:
    candidate_title = work.get("title") or ""
    title_score = _title_similarity(paper.title, candidate_title)
    year = work.get("publication_year")
    if paper.year and year:
        diff = abs(int(paper.year) - int(year))
        year_score = max(0.0, 1.0 - min(diff, 5) * 0.2)
    else:
        year_score = 0.6
    return title_score * 0.85 + year_score * 0.15


def _title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _normalize_title(left), _normalize_title(right)).ratio()


def _normalize_title(title: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in title).split())
