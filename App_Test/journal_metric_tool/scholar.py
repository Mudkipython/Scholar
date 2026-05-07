import re
from typing import List, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import ScholarPaper


GOOGLE_SCHOLAR_BASE = "https://scholar.google.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class ScholarProfileError(RuntimeError):
    """Raised when a Google Scholar profile cannot be read as a public profile."""


def parse_scholar_author_id(profile_url: str) -> str:
    parsed = urlparse(profile_url.strip())
    query = parse_qs(parsed.query)
    author_id = query.get("user", [""])[0].strip()
    if not author_id:
        raise ValueError("Could not find a Google Scholar author id in the URL query parameter 'user'.")
    return author_id


def build_profile_url(author_id: str, limit: int = 100, sort_by: str = "pubdate") -> str:
    params = {
        "user": author_id,
        "hl": "en",
        "cstart": 0,
        "pagesize": max(1, min(limit, 100)),
    }
    if sort_by:
        params["sortby"] = sort_by
    return f"{GOOGLE_SCHOLAR_BASE}/citations?{urlencode(params)}"


def fetch_scholar_profile_html(author_id: str, limit: int = 100, timeout: int = 20) -> str:
    url = build_profile_url(author_id, limit=limit)
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    html = response.text
    lowered = html.lower()
    if "sorry" in lowered and ("captcha" in lowered or "unusual traffic" in lowered):
        raise ScholarProfileError(
            "Google Scholar returned an anti-automation page. Try a smaller request, use OpenAlex name search, "
            "or configure a compliant third-party Scholar API."
        )
    return html


def parse_author_name(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    name = soup.select_one("#gsc_prf_in")
    return name.get_text(" ", strip=True) if name else ""


def parse_scholar_profile_html(html: str, limit: int = 100) -> List[ScholarPaper]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.gsc_a_tr")
    if not rows:
        raise ScholarProfileError("No paper rows were found in the public Google Scholar profile page.")

    papers: List[ScholarPaper] = []
    for row in rows[:limit]:
        title_node = row.select_one("a.gsc_a_at")
        if not title_node:
            continue

        gray_nodes = row.select("div.gs_gray")
        authors = gray_nodes[0].get_text(" ", strip=True) if len(gray_nodes) >= 1 else ""
        venue_hint = gray_nodes[1].get_text(" ", strip=True) if len(gray_nodes) >= 2 else ""
        year_node = row.select_one(".gsc_a_y span")
        citation_node = row.select_one(".gsc_a_c a")

        paper = ScholarPaper(
            title=title_node.get_text(" ", strip=True),
            year=_to_int(year_node.get_text(" ", strip=True) if year_node else ""),
            citations=_to_int(citation_node.get_text(" ", strip=True) if citation_node else ""),
            scholar_url=urljoin(GOOGLE_SCHOLAR_BASE, title_node.get("href", "")),
            authors=authors,
            venue_hint=venue_hint,
        )
        papers.append(paper)

    return papers


def fetch_scholar_papers(profile_url: str, limit: int = 100) -> List[ScholarPaper]:
    author_id = parse_scholar_author_id(profile_url)
    html = fetch_scholar_profile_html(author_id, limit=limit)
    return parse_scholar_profile_html(html, limit=limit)


def _to_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"\d+", value.replace(",", ""))
    return int(match.group(0)) if match else None
