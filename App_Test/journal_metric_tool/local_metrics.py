import os
from io import StringIO
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import requests


LOCAL_METRIC_COLUMNS = [
    "jcr_quartile",
    "cas_zone",
    "cas_subject",
    "jcr_category",
    "local_metric_source",
]


COLUMN_ALIASES = {
    "journal": ["journal", "journal_name", "source", "source_title", "publication", "期刊", "期刊名称"],
    "issn_l": ["issn_l", "issn-l", "issnl", "issn"],
    "jcr_quartile": ["jcr_quartile", "jcr_q", "jcrq", "jcr", "quartile", "分区", "jcr分区"],
    "cas_zone": ["cas_zone", "cas", "cas_partition", "cas_zone_basic", "中科院分区", "中科院大类分区"],
    "cas_subject": ["cas_subject", "cas_category", "中科院大类", "大类学科", "学科"],
    "jcr_category": ["jcr_category", "web_of_science_category", "wos_category", "jcr学科", "jcr类别"],
    "local_metric_source": ["local_metric_source", "metric_source", "source_file", "来源"],
}


def read_local_metrics(uploaded_file) -> pd.DataFrame:
    return read_metric_table(uploaded_file)


def read_metric_table(path_or_file) -> pd.DataFrame:
    name = str(getattr(path_or_file, "name", path_or_file)).lower()
    if name.startswith("http://") or name.startswith("https://"):
        return pd.read_csv(name)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(path_or_file)
    return pd.read_csv(path_or_file)


def discover_private_metric_path(base_dir: str = ".") -> Optional[Path]:
    env_path = os.getenv("JOURNAL_RANKINGS_PATH", "").strip()
    candidates = [Path(env_path)] if env_path else []
    data_dir = Path(base_dir) / "data"
    candidates.extend(
        [
            data_dir / "journal_rankings.csv",
            data_dir / "journal_rankings.xlsx",
            data_dir / "journal_rankings.xls",
            data_dir / "public_journal_rankings.csv",
            data_dir / "public_journal_rankings.xlsx",
            data_dir / "public_journal_rankings.xls",
            data_dir / "private_journal_rankings.csv",
            data_dir / "private_journal_rankings.xlsx",
            data_dir / "private_journal_rankings.xls",
        ]
    )
    for candidate in candidates:
        if candidate and candidate.exists() and candidate.is_file():
            return candidate
    return None


def discover_metric_urls(base_dir: str = ".") -> list:
    urls = []
    env_url = os.getenv("JOURNAL_RANKINGS_URL", "").strip()
    if env_url:
        urls.append(env_url)

    data_dir = Path(base_dir) / "data"
    for filename in ["journal_rankings_url.txt", "public_journal_rankings_url.txt"]:
        path = data_dir / filename
        if path.exists() and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                clean = line.strip()
                if clean and not clean.startswith("#"):
                    urls.append(clean)
    return urls


def load_private_metrics(base_dir: str = ".") -> Tuple[pd.DataFrame, str]:
    for url in discover_metric_urls(base_dir):
        try:
            return read_metric_url(url), url
        except Exception:
            continue
    path = discover_private_metric_path(base_dir)
    if not path:
        return pd.DataFrame(), ""
    return read_metric_table(path), str(path)


def read_metric_url(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))


def analyze_metric_table(metrics: Optional[pd.DataFrame]) -> Dict[str, object]:
    if metrics is None or metrics.empty:
        return {
            "row_count": 0,
            "recognized_columns": [],
            "unrecognized_columns": [],
            "has_match_key": False,
        }
    column_map = _resolve_columns(metrics)
    recognized_originals = set(column_map.values())
    return {
        "row_count": len(metrics),
        "recognized_columns": sorted(column_map.keys()),
        "unrecognized_columns": [column for column in metrics.columns if column not in recognized_originals],
        "has_match_key": bool(column_map.get("journal") or column_map.get("issn_l")),
    }


def compute_metric_match_stats(results: pd.DataFrame, metrics: Optional[pd.DataFrame]) -> Dict[str, object]:
    if metrics is None or metrics.empty or results.empty:
        return {
            "matched_by_issn": 0,
            "matched_by_journal": 0,
            "unmatched": len(results),
            "match_rate": 0.0,
        }

    normalized_metrics = normalize_metric_table(metrics)
    if normalized_metrics.empty:
        return {
            "matched_by_issn": 0,
            "matched_by_journal": 0,
            "unmatched": len(results),
            "match_rate": 0.0,
        }

    issn_lookup = _build_lookup(normalized_metrics, "issn_l")
    journal_lookup = _build_lookup(normalized_metrics, "journal_key")
    matched_by_issn = 0
    matched_by_journal = 0

    for _, row in results.iterrows():
        issn_key = _normalize_issn(row.get("issn_l", ""))
        journal_key = _normalize_journal(row.get("journal", ""))
        if issn_key and issn_key in issn_lookup:
            matched_by_issn += 1
        elif journal_key and journal_key in journal_lookup:
            matched_by_journal += 1

    matched = matched_by_issn + matched_by_journal
    total = len(results)
    return {
        "matched_by_issn": matched_by_issn,
        "matched_by_journal": matched_by_journal,
        "unmatched": total - matched,
        "match_rate": round(matched / total, 3) if total else 0.0,
    }


def enrich_with_local_metrics(results: pd.DataFrame, metrics: Optional[pd.DataFrame]) -> pd.DataFrame:
    enriched = results.copy()
    for column in LOCAL_METRIC_COLUMNS:
        if column not in enriched.columns:
            enriched[column] = ""

    if metrics is None or metrics.empty or results.empty:
        return enriched

    normalized_metrics = normalize_metric_table(metrics)
    if normalized_metrics.empty:
        return enriched

    issn_lookup = _build_lookup(normalized_metrics, "issn_l")
    journal_lookup = _build_lookup(normalized_metrics, "journal_key")

    for idx, row in enriched.iterrows():
        metric_row = None
        issn_key = _normalize_issn(row.get("issn_l", ""))
        journal_key = _normalize_journal(row.get("journal", ""))
        if issn_key and issn_key in issn_lookup:
            metric_row = issn_lookup[issn_key]
        elif journal_key and journal_key in journal_lookup:
            metric_row = journal_lookup[journal_key]

        if metric_row is not None:
            for column in LOCAL_METRIC_COLUMNS:
                value = metric_row.get(column, "")
                if pd.notna(value) and str(value).strip():
                    enriched.at[idx, column] = value

    return enriched


def normalize_metric_table(metrics: pd.DataFrame) -> pd.DataFrame:
    column_map = _resolve_columns(metrics)
    if not column_map.get("journal") and not column_map.get("issn_l"):
        return pd.DataFrame()

    normalized = pd.DataFrame()
    normalized["journal"] = _series_or_empty(metrics, column_map.get("journal"))
    normalized["issn_l"] = _series_or_empty(metrics, column_map.get("issn_l")).map(_normalize_issn)
    normalized["journal_key"] = normalized["journal"].map(_normalize_journal)

    for column in LOCAL_METRIC_COLUMNS:
        normalized[column] = _series_or_empty(metrics, column_map.get(column))
    if not normalized["local_metric_source"].astype(str).str.strip().any():
        normalized["local_metric_source"] = "Uploaded metric table"

    normalized = normalized.drop_duplicates(subset=["issn_l", "journal_key"], keep="first")
    return normalized


def _resolve_columns(df: pd.DataFrame) -> Dict[str, str]:
    available = {_normalize_column(column): column for column in df.columns}
    resolved = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _normalize_column(alias)
            if key in available:
                resolved[canonical] = available[key]
                break
    return resolved


def _series_or_empty(df: pd.DataFrame, column: Optional[str]) -> pd.Series:
    if column and column in df.columns:
        return df[column].fillna("")
    return pd.Series([""] * len(df), index=df.index)


def _build_lookup(df: pd.DataFrame, key_column: str) -> Dict[str, pd.Series]:
    lookup = {}
    for _, row in df.iterrows():
        key = row.get(key_column, "")
        if key and key not in lookup:
            lookup[key] = row
    return lookup


def _normalize_column(value: str) -> str:
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def _normalize_issn(value: str) -> str:
    text = str(value or "").upper().strip()
    chars = [ch for ch in text if ch.isdigit() or ch == "X"]
    if len(chars) < 8:
        return ""
    return "".join(chars[:4]) + "-" + "".join(chars[4:8])


def _normalize_journal(value: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in str(value or "")).split())
