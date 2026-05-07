from typing import Dict

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
