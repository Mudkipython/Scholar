"""Tools for matching scholar papers to journal-level metrics."""

from .pipeline import (
    build_results_from_openalex_author,
    build_results_from_scholar_profile,
    results_to_dataframe,
)
from .local_metrics import enrich_with_local_metrics
from .results import compute_result_summary

__all__ = [
    "build_results_from_openalex_author",
    "build_results_from_scholar_profile",
    "compute_result_summary",
    "enrich_with_local_metrics",
    "results_to_dataframe",
]
