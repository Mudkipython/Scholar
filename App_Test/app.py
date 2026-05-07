import os
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from journal_metric_tool.errors import classify_error
from journal_metric_tool.export import dataframe_to_csv_bytes, dataframe_to_xlsx_bytes
from journal_metric_tool.i18n import LANGUAGES, translate
from journal_metric_tool.local_metrics import (
    analyze_metric_table,
    compute_metric_match_stats,
    enrich_with_local_metrics,
    load_private_metrics,
    read_local_metrics,
)
from journal_metric_tool.pipeline import (
    build_results_from_openalex_author,
    build_results_from_scholar_profile,
    results_to_dataframe,
    search_author_candidates,
)
from journal_metric_tool.results import compute_result_summary, split_result_columns
from journal_metric_tool.scholar import parse_scholar_author_id


SAMPLE_TEMPLATE_PATH = Path(__file__).with_name("sample_metric_template.csv")
APP_DIR = Path(__file__).resolve().parent


@st.cache_data(ttl="1h", max_entries=32, show_spinner=False)
def cached_scholar_results(profile_url: str, max_papers: int, mailto: str) -> pd.DataFrame:
    rows = build_results_from_scholar_profile(profile_url, max_papers=max_papers, mailto=mailto)
    return results_to_dataframe(rows)


@st.cache_data(ttl="1h", max_entries=64, show_spinner=False)
def cached_author_candidates(name: str, institution_keyword: str, mailto: str) -> list:
    return search_author_candidates(name, institution_keyword=institution_keyword, per_page=10, mailto=mailto)


@st.cache_data(ttl="1h", max_entries=64, show_spinner=False)
def cached_author_results(author_id: str, max_papers: int, mailto: str) -> pd.DataFrame:
    rows = build_results_from_openalex_author(author_id, max_papers=max_papers, mailto=mailto)
    return results_to_dataframe(rows)


def main() -> None:
    st.set_page_config(
        page_title="Scholar Journal Metrics",
        page_icon=":material/query_stats:",
        layout="wide",
    )

    selected_language = st.sidebar.selectbox(
        translate("en", "language") + " / " + translate("zh", "language"),
        list(LANGUAGES.keys()),
        index=0,
    )
    lang = LANGUAGES[selected_language]
    t = lambda key, **kwargs: translate(lang, key, **kwargs)

    mailto, max_papers = render_sidebar(t)
    render_header(t)

    local_metrics = render_metric_upload(t)
    base_results = render_query_panel(t, mailto=mailto, max_papers=max_papers)

    if base_results is None:
        render_empty_state(t)
        return

    enriched_results = enrich_with_local_metrics(base_results, local_metrics)
    render_results(t, enriched_results, base_results=base_results, local_metrics=local_metrics)


def render_sidebar(t):
    st.sidebar.subheader(t("settings"))
    mailto = st.sidebar.text_input(
        t("mailto_label"),
        value=os.getenv("OPENALEX_MAILTO", ""),
        help=t("mailto_help"),
    )
    max_papers = st.sidebar.number_input(t("max_papers"), min_value=1, max_value=200, value=20, step=5)
    st.sidebar.caption(t("sidebar_scope"))
    return mailto, max_papers


def render_header(t) -> None:
    st.title(t("page_title"))
    st.caption(t("caption"))
    st.markdown(
        " ".join(
            [
                f":blue-badge[{t('badge_openalex')}]",
                f":orange-badge[{t('badge_not_official_jif')}]",
                f":green-badge[{t('badge_upload_optional')}]",
            ]
        )
    )

    with st.container(border=True):
        col_source, col_privacy, col_reliability = st.columns(3)
        col_source.markdown(f"**:material/database: {t('source_policy_title')}**")
        col_source.caption(t("source_policy_body"))
        col_privacy.markdown(f"**:material/lock: {t('privacy_title')}**")
        col_privacy.caption(t("privacy_body"))
        col_reliability.markdown(f"**:material/verified: {t('reliability_title')}**")
        col_reliability.caption(t("reliability_body"))


def render_metric_upload(t) -> pd.DataFrame:
    st.subheader(t("metric_upload_title"), anchor=False)
    st.caption(t("metric_upload_caption"))
    with st.container(border=True):
        upload_col, preview_col = st.columns([1, 2])
        with upload_col:
            uploaded = st.file_uploader(
                t("upload_rankings"),
                type=["csv", "xlsx", "xls"],
                help=t("upload_rankings_help"),
            )
            if SAMPLE_TEMPLATE_PATH.exists():
                st.download_button(
                    t("download_template"),
                    data=SAMPLE_TEMPLATE_PATH.read_bytes(),
                    file_name="sample_metric_template.csv",
                    mime="text/csv",
                    icon=":material/download:",
                )

        if not uploaded:
            with preview_col:
                private_metrics, private_source = load_private_metrics_for_app(str(APP_DIR))
                if private_metrics.empty:
                    st.warning(t("private_metric_missing"), icon=":material/database_off:")
                    st.caption(t("private_metric_missing_help"))
                    return pd.DataFrame()
                st.success(t("private_metric_loaded", source=private_source), icon=":material/database:")
                render_metric_table_analysis(t, private_metrics)
                return private_metrics

        try:
            metrics = read_local_metrics(uploaded)
        except Exception as exc:
            with preview_col:
                st.error(t("read_metric_error", error=exc), icon=":material/error:")
            return pd.DataFrame()

        with preview_col:
            st.success(t("uploaded_metric_active"), icon=":material/upload_file:")
            render_metric_table_analysis(t, metrics)
        return metrics


@st.cache_data(ttl="10m", max_entries=4, show_spinner=False)
def load_cached_private_metrics(base_dir: str):
    return load_private_metrics(base_dir)


def load_private_metrics_for_app(base_dir: str):
    metrics, source = load_private_metrics_from_secrets()
    if not metrics.empty:
        return metrics, source
    return load_cached_private_metrics(base_dir)


def load_private_metrics_from_secrets():
    try:
        csv_text = st.secrets.get("journal_rankings_csv", "")
        secret_path = st.secrets.get("journal_rankings_path", "")
    except Exception:
        return pd.DataFrame(), ""

    if csv_text:
        return pd.read_csv(StringIO(str(csv_text))), "Streamlit secrets: journal_rankings_csv"
    if secret_path:
        return load_private_metrics_from_path(str(secret_path)), f"Streamlit secrets: {secret_path}"
    return pd.DataFrame(), ""


def load_private_metrics_from_path(path: str) -> pd.DataFrame:
    suffix = Path(path).suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    return pd.read_csv(path)


def render_metric_table_analysis(t, metrics: pd.DataFrame) -> None:
    analysis = analyze_metric_table(metrics)
    metric_cols = st.columns(3)
    metric_cols[0].metric(t("uploaded_rows"), analysis["row_count"])
    metric_cols[1].metric(t("recognized_columns"), len(analysis["recognized_columns"]))
    metric_cols[2].metric(t("match_key_status"), t("available") if analysis["has_match_key"] else t("missing"))
    if not analysis["has_match_key"]:
        st.warning(t("metric_missing_key"), icon=":material/warning:")
    if analysis["unrecognized_columns"]:
        st.caption(t("unrecognized_columns", columns=", ".join(map(str, analysis["unrecognized_columns"]))))
    st.dataframe(metrics.head(5), hide_index=True, use_container_width=True)


def render_query_panel(t, mailto: str, max_papers: int) -> pd.DataFrame:
    st.subheader(t("query_title"), anchor=False)
    mode = st.radio(
        t("query_mode"),
        [t("tab_scholar_url"), t("tab_author_search")],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == t("tab_scholar_url"):
        return render_scholar_url_query(t, mailto=mailto, max_papers=max_papers)
    return render_author_query(t, mailto=mailto, max_papers=max_papers)


def render_scholar_url_query(t, mailto: str, max_papers: int) -> pd.DataFrame:
    with st.form("scholar_profile_form", border=True):
        profile_url = st.text_input(
            t("scholar_url_label"),
            placeholder="https://scholar.google.com/citations?user=LSsXyncAAAAJ",
            help=t("scholar_url_help"),
        )
        submitted = st.form_submit_button(t("query_scholar"), type="primary", icon=":material/search:")

    if not submitted:
        return st.session_state.get("results_df")

    try:
        parse_scholar_author_id(profile_url)
    except Exception:
        st.warning(t("invalid_scholar_url"), icon=":material/warning:")
        return st.session_state.get("results_df")

    with st.status(t("scholar_spinner"), expanded=True) as status:
        try:
            st.write(t("status_fetch_profile"))
            df = cached_scholar_results(profile_url.strip(), max_papers, mailto)
            st.write(t("status_match_metrics"))
            st.session_state["results_df"] = df
            status.update(label=t("query_complete"), state="complete", expanded=False)
            return df
        except Exception as exc:
            status.update(label=t("query_failed"), state="error", expanded=True)
            render_error(t, exc)
            return st.session_state.get("results_df")


def render_author_query(t, mailto: str, max_papers: int) -> pd.DataFrame:
    with st.form("author_search_form", border=True):
        col_name, col_inst = st.columns([2, 1])
        with col_name:
            author_name = st.text_input(t("author_name"), placeholder="Jane Smith")
        with col_inst:
            institution_keyword = st.text_input(t("institution_keyword"), placeholder="Toronto")
        submitted = st.form_submit_button(t("search_authors"), type="primary", icon=":material/person_search:")

    if submitted:
        if not author_name.strip():
            st.warning(t("author_name_required"), icon=":material/warning:")
        else:
            with st.spinner(t("search_authors_spinner")):
                try:
                    st.session_state["author_candidates"] = cached_author_candidates(
                        author_name.strip(),
                        institution_keyword.strip(),
                        mailto,
                    )
                except Exception as exc:
                    render_error(t, exc)

    candidates = st.session_state.get("author_candidates", [])
    if not candidates:
        return st.session_state.get("results_df")

    st.markdown(f"**{t('select_author')}**")
    candidate_options = {
        f"{item.display_name} | {item.institution or t('no_institution')} | "
        f"{item.works_count} {t('works')} | {item.cited_by_count} {t('citations')}": item.id
        for item in candidates
    }
    selected_label = st.selectbox(t("select_author"), list(candidate_options.keys()), label_visibility="collapsed")
    st.dataframe(
        pd.DataFrame([candidate.__dict__ for candidate in candidates]),
        hide_index=True,
        use_container_width=True,
        column_config={
            "id": st.column_config.LinkColumn("OpenAlex ID"),
            "display_name": st.column_config.TextColumn(t("author_name"), pinned=True),
        },
    )

    if st.button(t("query_selected_author"), type="primary", icon=":material/manage_search:"):
        with st.status(t("query_author_spinner"), expanded=True) as status:
            try:
                df = cached_author_results(candidate_options[selected_label], max_papers, mailto)
                st.session_state["results_df"] = df
                status.update(label=t("query_complete"), state="complete", expanded=False)
                return df
            except Exception as exc:
                status.update(label=t("query_failed"), state="error", expanded=True)
                render_error(t, exc)
    return st.session_state.get("results_df")


def render_results(t, df: pd.DataFrame, base_results: pd.DataFrame, local_metrics: pd.DataFrame) -> None:
    st.subheader(t("results_title"), anchor=False)
    render_summary_metrics(t, df)
    if local_metrics is not None and not local_metrics.empty:
        render_local_match_stats(t, base_results, local_metrics)
    render_result_table(t, df)
    render_exports(t, df)


def render_summary_metrics(t, df: pd.DataFrame) -> None:
    summary = compute_result_summary(df)
    cols = st.columns(4)
    cols[0].metric(t("summary_papers"), summary["paper_count"])
    cols[1].metric(t("summary_journals"), summary["journal_count"])
    cols[2].metric(t("summary_openalex_match"), _format_percent(summary["openalex_match_rate"]))
    cols[3].metric(t("summary_local_match"), _format_percent(summary["local_metric_rate"]))
    cols = st.columns(3)
    cols[0].metric(t("summary_openalex_metric"), _format_percent(summary["openalex_metric_rate"]))
    cols[1].metric(t("summary_low_confidence"), summary["low_confidence_count"])
    cols[2].metric(t("summary_notes"), summary["notes_count"])


def render_local_match_stats(t, base_results: pd.DataFrame, local_metrics: pd.DataFrame) -> None:
    stats = compute_metric_match_stats(base_results, local_metrics)
    st.caption(
        t(
            "local_match_caption",
            rate=_format_percent(stats["match_rate"]),
            issn=stats["matched_by_issn"],
            journal=stats["matched_by_journal"],
            unmatched=stats["unmatched"],
        )
    )


def render_result_table(t, df: pd.DataFrame) -> None:
    split = split_result_columns(df)
    st.dataframe(
        split["primary"],
        hide_index=True,
        use_container_width=True,
        column_config={
            "title": st.column_config.TextColumn(t("col_title"), pinned=True, width="large"),
            "year": st.column_config.NumberColumn(t("col_year"), format="%d"),
            "journal": st.column_config.TextColumn(t("col_journal"), width="medium"),
            "metric_value": st.column_config.NumberColumn(t("col_metric_value"), format="%.3f"),
            "match_confidence": st.column_config.ProgressColumn(
                t("col_match_confidence"),
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
        },
    )
    with st.expander(t("technical_columns"), icon=":material/tune:"):
        st.dataframe(split["technical"], hide_index=True, use_container_width=True)
    if compute_result_summary(df)["low_confidence_count"]:
        st.warning(t("low_confidence_warning"), icon=":material/warning:")
    st.caption(t("result_source_caption"))


def render_exports(t, df: pd.DataFrame) -> None:
    st.subheader(t("export_title"), anchor=False)
    csv_bytes = dataframe_to_csv_bytes(df)
    xlsx_bytes = dataframe_to_xlsx_bytes(df)
    col_csv, col_xlsx = st.columns(2)
    with col_csv:
        st.download_button(
            t("download_csv"),
            data=csv_bytes,
            file_name="journal_metrics.csv",
            mime="text/csv",
            icon=":material/download:",
            use_container_width=True,
        )
    with col_xlsx:
        st.download_button(
            t("download_xlsx"),
            data=xlsx_bytes,
            file_name="journal_metrics.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            use_container_width=True,
        )


def render_error(t, exc: Exception) -> None:
    code = classify_error(exc)
    st.error(t(f"error_{code}"), icon=":material/error:")
    with st.expander(t("error_details"), icon=":material/bug_report:"):
        st.code(str(exc))


def render_empty_state(t) -> None:
    with st.container(border=True):
        st.markdown(f"**:material/search: {t('empty_title')}**")
        st.caption(t("empty_body"))


def _format_percent(value: float) -> str:
    return f"{value * 100:.0f}%"


if __name__ == "__main__":
    main()
