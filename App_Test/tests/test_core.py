import requests
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from journal_metric_tool.errors import classify_error
from journal_metric_tool.export import dataframe_to_csv_bytes, dataframe_to_xlsx_bytes
from journal_metric_tool.i18n import TRANSLATIONS, translate
from journal_metric_tool.local_metrics import compute_metric_match_stats, discover_private_metric_path, enrich_with_local_metrics
from journal_metric_tool.openalex import work_to_match
from journal_metric_tool.pipeline import RESULT_COLUMNS, results_to_dataframe
from journal_metric_tool.results import compute_result_summary, split_result_columns
from journal_metric_tool.scholar import parse_scholar_author_id, parse_scholar_profile_html


SCHOLAR_HTML = """
<html>
  <body>
    <div id="gsc_prf_in">Example Scholar</div>
    <table>
      <tr class="gsc_a_tr">
        <td class="gsc_a_t">
          <a class="gsc_a_at" href="/citations?view_op=view_citation&citation_for_view=abc">
            A sample paper about cities
          </a>
          <div class="gs_gray">A Scholar, B Author</div>
          <div class="gs_gray">Journal of Urban Research 12 (3), 1-10</div>
        </td>
        <td class="gsc_a_c"><a>42</a></td>
        <td class="gsc_a_y"><span>2024</span></td>
      </tr>
    </table>
  </body>
</html>
"""


OPENALEX_WORK = {
    "id": "https://openalex.org/W123",
    "title": "A sample paper about cities",
    "publication_year": 2024,
    "doi": "https://doi.org/10.1234/example",
    "cited_by_count": 12,
    "primary_location": {
        "source": {
            "id": "https://openalex.org/S456",
            "display_name": "Journal of Urban Research",
            "issn_l": "1234-5678",
            "type": "journal",
        }
    },
}


class CoreTests(unittest.TestCase):
    def test_parse_scholar_author_id(self):
        url = "https://scholar.google.com/citations?user=abc123&hl=en"
        self.assertEqual(parse_scholar_author_id(url), "abc123")

    def test_parse_scholar_profile_html(self):
        papers = parse_scholar_profile_html(SCHOLAR_HTML)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].title, "A sample paper about cities")
        self.assertEqual(papers[0].year, 2024)
        self.assertEqual(papers[0].citations, 42)
        self.assertIn("Journal of Urban Research", papers[0].venue_hint)

    def test_work_to_match(self):
        match = work_to_match(OPENALEX_WORK, requested_title="A sample paper about cities", requested_year=2024)
        self.assertEqual(match.journal, "Journal of Urban Research")
        self.assertEqual(match.doi, "10.1234/example")
        self.assertEqual(match.issn_l, "1234-5678")
        self.assertGreater(match.match_confidence, 0.95)

    def test_results_dataframe_columns_and_exports(self):
        df = results_to_dataframe(
            [
                {
                    "title": "A sample paper about cities",
                    "year": 2024,
                    "journal": "Journal of Urban Research",
                    "doi": "10.1234/example",
                    "citations": 12,
                    "metric_value": 2.5,
                    "metric_source": "OpenAlex 2-year mean citedness (not official JIF)",
                    "h_index": 50,
                    "i10_index": 200,
                    "jcr_quartile": "",
                    "cas_zone": "",
                    "cas_subject": "",
                    "jcr_category": "",
                    "local_metric_source": "",
                    "match_confidence": 1.0,
                    "source_type": "journal",
                    "issn_l": "1234-5678",
                    "openalex_id": "https://openalex.org/W123",
                    "notes": "",
                }
            ]
        )
        self.assertEqual(list(df.columns), RESULT_COLUMNS)
        self.assertIn(b"A sample paper", dataframe_to_csv_bytes(df))
        self.assertGreater(len(dataframe_to_xlsx_bytes(df)), 100)
        self.assertIsInstance(df, pd.DataFrame)

    def test_enrich_with_local_metrics_by_issn_and_journal_name(self):
        results = results_to_dataframe(
            [
                {
                    "title": "A sample paper about cities",
                    "year": 2024,
                    "journal": "Journal of Urban Research",
                    "doi": "10.1234/example",
                    "citations": 12,
                    "metric_value": 2.5,
                    "metric_source": "OpenAlex 2-year mean citedness (not official JIF)",
                    "h_index": 50,
                    "i10_index": 200,
                    "jcr_quartile": "",
                    "cas_zone": "",
                    "cas_subject": "",
                    "jcr_category": "",
                    "local_metric_source": "",
                    "match_confidence": 1.0,
                    "source_type": "journal",
                    "issn_l": "1234-5678",
                    "openalex_id": "https://openalex.org/W123",
                    "notes": "",
                },
                {
                    "title": "A journal-name-only paper",
                    "year": 2024,
                    "journal": "Name Only Journal",
                    "doi": "",
                    "citations": 1,
                    "metric_value": None,
                    "metric_source": "OpenAlex",
                    "h_index": None,
                    "i10_index": None,
                    "jcr_quartile": "",
                    "cas_zone": "",
                    "cas_subject": "",
                    "jcr_category": "",
                    "local_metric_source": "",
                    "match_confidence": 0.5,
                    "source_type": "journal",
                    "issn_l": "",
                    "openalex_id": "",
                    "notes": "",
                },
            ]
        )
        metrics = pd.DataFrame(
            [
                {
                    "ISSN": "12345678",
                    "JCR_Q": "Q1",
                    "中科院大类分区": "3区",
                    "大类学科": "地理学",
                    "JCR类别": "GEOGRAPHY",
                },
                {
                    "期刊名称": "Name Only Journal",
                    "JCR_Q": "Q2",
                    "中科院大类分区": "2区",
                },
            ]
        )
        enriched = enrich_with_local_metrics(results, metrics)
        self.assertEqual(enriched.loc[0, "jcr_quartile"], "Q1")
        self.assertEqual(enriched.loc[0, "cas_zone"], "3区")
        self.assertEqual(enriched.loc[0, "cas_subject"], "地理学")
        self.assertEqual(enriched.loc[0, "jcr_category"], "GEOGRAPHY")
        self.assertEqual(enriched.loc[1, "jcr_quartile"], "Q2")
        self.assertEqual(enriched.loc[1, "cas_zone"], "2区")
        stats = compute_metric_match_stats(results, metrics)
        self.assertEqual(stats["matched_by_issn"], 1)
        self.assertEqual(stats["matched_by_journal"], 1)
        self.assertEqual(stats["unmatched"], 0)
        self.assertEqual(stats["match_rate"], 1.0)

    def test_result_summary_and_column_split(self):
        df = results_to_dataframe(
            [
                {
                    "title": "A sample paper about cities",
                    "year": 2024,
                    "journal": "Journal of Urban Research",
                    "doi": "10.1234/example",
                    "citations": 12,
                    "metric_value": 2.5,
                    "metric_source": "OpenAlex 2-year mean citedness (not official JIF)",
                    "h_index": 50,
                    "i10_index": 200,
                    "jcr_quartile": "Q1",
                    "cas_zone": "3区",
                    "cas_subject": "地理学",
                    "jcr_category": "GEOGRAPHY",
                    "local_metric_source": "Uploaded metric table",
                    "match_confidence": 1.0,
                    "source_type": "journal",
                    "issn_l": "1234-5678",
                    "openalex_id": "https://openalex.org/W123",
                    "notes": "",
                },
                {
                    "title": "Low confidence paper",
                    "year": 2022,
                    "journal": "",
                    "doi": "",
                    "citations": None,
                    "metric_value": None,
                    "metric_source": "OpenAlex",
                    "h_index": None,
                    "i10_index": None,
                    "jcr_quartile": "",
                    "cas_zone": "",
                    "cas_subject": "",
                    "jcr_category": "",
                    "local_metric_source": "",
                    "match_confidence": 0.4,
                    "source_type": "",
                    "issn_l": "",
                    "openalex_id": "",
                    "notes": "No source.",
                },
            ]
        )
        summary = compute_result_summary(df)
        self.assertEqual(summary["paper_count"], 2)
        self.assertEqual(summary["journal_count"], 1)
        self.assertEqual(summary["openalex_match_rate"], 0.5)
        self.assertEqual(summary["local_metric_rate"], 0.5)
        self.assertEqual(summary["low_confidence_count"], 1)
        split = split_result_columns(df)
        self.assertIn("title", split["primary"].columns)
        self.assertIn("openalex_id", split["technical"].columns)

    def test_error_classification(self):
        self.assertEqual(classify_error(requests.Timeout("slow")), "timeout")
        self.assertEqual(classify_error(requests.ConnectionError("offline")), "network")

    def test_discover_private_metric_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir()
            private_path = data_dir / "private_journal_rankings.csv"
            private_path.write_text("journal,issn_l,jcr_quartile\nTest Journal,1234-5678,Q1\n", encoding="utf-8")
            self.assertEqual(discover_private_metric_path(temp_dir), private_path)

    def test_i18n_keys_are_complete(self):
        english_keys = set(TRANSLATIONS["en"].keys())
        chinese_keys = set(TRANSLATIONS["zh"].keys())
        self.assertEqual(english_keys, chinese_keys)
        self.assertEqual(translate("zh", "download_csv"), "下载 CSV")
        self.assertEqual(translate("en", "found_papers", count=3), "Found 3 papers.")


if __name__ == "__main__":
    unittest.main()
