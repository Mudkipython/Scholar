from typing import Dict, Iterable, Optional

import pandas as pd


PRIMARY_RESULT_COLUMNS = [
    "title",
    "year",
    "journal",
    "jcr_quartile",
    "cas_zone",
    "metric_value",
    "metric_source",
    "match_confidence",
    "notes",
]

TECHNICAL_RESULT_COLUMNS = [
    "doi",
    "citations",
    "h_index",
    "i10_index",
    "cas_subject",
    "jcr_category",
    "local_metric_source",
    "source_type",
    "issn_l",
    "openalex_id",
]

REFERENCE_TEMPLATE_COLUMNS = [
    "journal",
    "issn_l",
    "jcr_quartile",
    "cas_zone",
    "cas_subject",
    "jcr_category",
    "local_metric_source",
    "source_type",
    "openalex_metric_value",
    "metric_source",
]

SORT_OPTIONS = {
    "year": "year",
    "citations": "citations",
    "openalex_metric": "metric_value",
    "match_confidence": "match_confidence",
    "journal": "journal",
    "title": "title",
    "jcr_quartile": "jcr_quartile",
    "cas_zone": "cas_zone",
}

NUMERIC_SORT_COLUMNS = {"year", "citations", "metric_value", "match_confidence"}


def compute_result_summary(df: pd.DataFrame) -> Dict[str, object]:
    if df is None or df.empty:
        return {
            "paper_count": 0,
            "journal_count": 0,
            "openalex_match_rate": 0.0,
            "openalex_metric_rate": 0.0,
            "local_metric_rate": 0.0,
            "low_confidence_count": 0,
            "notes_count": 0,
        }

    paper_count = len(df)
    has_openalex = _has_text(df, "openalex_id")
    has_metric = df.get("metric_value", pd.Series(index=df.index, dtype=object)).notna()
    has_local_metric = (
        _has_text(df, "jcr_quartile")
        | _has_text(df, "cas_zone")
        | _has_text(df, "cas_subject")
        | _has_text(df, "jcr_category")
    )
    confidence = pd.to_numeric(df.get("match_confidence", pd.Series(index=df.index)), errors="coerce")

    return {
        "paper_count": paper_count,
        "journal_count": int(df.get("journal", pd.Series(dtype=object)).replace("", pd.NA).dropna().nunique()),
        "openalex_match_rate": round(float(has_openalex.sum()) / paper_count, 3),
        "openalex_metric_rate": round(float(has_metric.sum()) / paper_count, 3),
        "local_metric_rate": round(float(has_local_metric.sum()) / paper_count, 3),
        "low_confidence_count": int((confidence.fillna(0) < 0.75).sum()),
        "notes_count": int(_has_text(df, "notes").sum()),
    }


def split_result_columns(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    primary = [column for column in PRIMARY_RESULT_COLUMNS if column in df.columns]
    primary = _drop_empty_optional_columns(df, primary)
    technical = [column for column in TECHNICAL_RESULT_COLUMNS if column in df.columns]
    return {
        "primary": df[primary].copy(),
        "technical": df[technical].copy(),
    }


def build_result_filter_options(df: pd.DataFrame) -> Dict[str, list]:
    if df is None or df.empty:
        return {"jcr_quartiles": [], "cas_zones": []}

    return {
        "jcr_quartiles": _unique_nonempty_values(df, "jcr_quartile"),
        "cas_zones": _unique_nonempty_values(df, "cas_zone"),
    }


def filter_and_sort_results(
    df: pd.DataFrame,
    query: str = "",
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    require_journal: bool = False,
    require_local_metric: bool = False,
    low_confidence_only: bool = False,
    jcr_quartiles: Optional[Iterable[str]] = None,
    cas_zones: Optional[Iterable[str]] = None,
    sort_by: str = "year",
    ascending: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    work = df.copy()

    query = (query or "").strip().casefold()
    if query:
        search_columns = [column for column in ["title", "journal", "doi", "notes"] if column in work.columns]
        if search_columns:
            search_text = work[search_columns].fillna("").astype(str).agg(" ".join, axis=1).str.casefold()
            work = work[search_text.str.contains(query, regex=False, na=False)]

    if "year" in work.columns and (year_min is not None or year_max is not None):
        years = pd.to_numeric(work["year"], errors="coerce")
        mask = pd.Series([True] * len(work), index=work.index)
        if year_min is not None:
            mask &= years.ge(year_min)
        if year_max is not None:
            mask &= years.le(year_max)
        work = work[mask]

    if require_journal:
        work = work[_has_text(work, "journal")]

    if require_local_metric:
        work = work[_has_local_metric(work)]

    if low_confidence_only and "match_confidence" in work.columns:
        confidence = pd.to_numeric(work["match_confidence"], errors="coerce").fillna(0)
        work = work[confidence.lt(0.75)]

    selected_jcr = _clean_selected_values(jcr_quartiles)
    if selected_jcr and "jcr_quartile" in work.columns:
        work = work[work["jcr_quartile"].fillna("").astype(str).isin(selected_jcr)]

    selected_cas = _clean_selected_values(cas_zones)
    if selected_cas and "cas_zone" in work.columns:
        work = work[work["cas_zone"].fillna("").astype(str).isin(selected_cas)]

    sort_column = SORT_OPTIONS.get(sort_by, "year")
    if sort_column in work.columns:
        if sort_column in NUMERIC_SORT_COLUMNS:
            sort_values = pd.to_numeric(work[sort_column], errors="coerce")
        else:
            sort_values = work[sort_column].fillna("").astype(str).str.casefold()
        work = work.assign(_sort_value=sort_values).sort_values(
            by="_sort_value",
            ascending=ascending,
            na_position="last",
            kind="mergesort",
        )
        work = work.drop(columns=["_sort_value"])

    return work.reset_index(drop=True)


def build_missing_journal_template(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=REFERENCE_TEMPLATE_COLUMNS)

    work = df.copy()
    has_journal = _has_text(work, "journal")
    has_local = (
        _has_text(work, "jcr_quartile")
        | _has_text(work, "cas_zone")
        | _has_text(work, "cas_subject")
        | _has_text(work, "jcr_category")
    )
    work = work[has_journal & ~has_local]
    if work.empty:
        return pd.DataFrame(columns=REFERENCE_TEMPLATE_COLUMNS)

    rows = pd.DataFrame(
        {
            "journal": work.get("journal", ""),
            "issn_l": work.get("issn_l", ""),
            "jcr_quartile": "",
            "cas_zone": "",
            "cas_subject": "",
            "jcr_category": "",
            "local_metric_source": "Lab reference table",
            "source_type": work.get("source_type", ""),
            "openalex_metric_value": work.get("metric_value", ""),
            "metric_source": work.get("metric_source", ""),
        }
    )
    rows = rows.drop_duplicates(subset=["journal", "issn_l"], keep="first")
    return rows[REFERENCE_TEMPLATE_COLUMNS].reset_index(drop=True)


def _has_local_metric(df: pd.DataFrame) -> pd.Series:
    return (
        _has_text(df, "jcr_quartile")
        | _has_text(df, "cas_zone")
        | _has_text(df, "cas_subject")
        | _has_text(df, "jcr_category")
    )


def _has_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[column].fillna("").astype(str).str.strip().ne("")


def _drop_empty_optional_columns(df: pd.DataFrame, columns: list) -> list:
    optional = {"jcr_quartile", "cas_zone"}
    kept = []
    for column in columns:
        if column in optional and not _has_text(df, column).any():
            continue
        kept.append(column)
    return kept


def _unique_nonempty_values(df: pd.DataFrame, column: str) -> list:
    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str).str.strip()
    values = values[values.ne("")]
    return sorted(values.unique().tolist())


def _clean_selected_values(values: Optional[Iterable[str]]) -> set:
    if not values:
        return set()
    return {str(value).strip() for value in values if str(value).strip()}
