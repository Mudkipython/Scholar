import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_streamlit_app_renders_main_controls(self):
        app = AppTest.from_file("streamlit_app.py")
        app.run(timeout=10)
        self.assertFalse(app.exception)
        self.assertGreaterEqual(len(app.title), 1)
        self.assertGreaterEqual(len(app.text_input), 2)
        self.assertGreaterEqual(len(app.button), 1)

    def test_streamlit_app_renders_result_browser_controls(self):
        app = AppTest.from_file("streamlit_app.py")
        app.session_state["results_df"] = pd.DataFrame(
            [
                {
                    "title": "Remote sensing change detection",
                    "year": 2024,
                    "journal": "IEEE Transactions on Geoscience and Remote Sensing",
                    "doi": "10.1/example",
                    "citations": 12,
                    "metric_value": 9.1,
                    "metric_source": "OpenAlex 2-year mean citedness (not official JIF)",
                    "h_index": 100,
                    "i10_index": 200,
                    "jcr_quartile": "Q1",
                    "cas_zone": "1区",
                    "cas_subject": "地球科学",
                    "jcr_category": "Remote sensing",
                    "local_metric_source": "Lab reference table",
                    "match_confidence": 0.96,
                    "source_type": "journal",
                    "issn_l": "0196-2892",
                    "openalex_id": "https://openalex.org/W1",
                    "notes": "",
                },
                {
                    "title": "Repository record",
                    "year": 2022,
                    "journal": "",
                    "doi": "",
                    "citations": 2,
                    "metric_value": None,
                    "metric_source": "OpenAlex",
                    "h_index": None,
                    "i10_index": None,
                    "jcr_quartile": "",
                    "cas_zone": "",
                    "cas_subject": "",
                    "jcr_category": "",
                    "local_metric_source": "",
                    "match_confidence": 0.41,
                    "source_type": "",
                    "issn_l": "",
                    "openalex_id": "https://openalex.org/W2",
                    "notes": "No source.",
                },
            ]
        )

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertGreaterEqual(len(app.slider), 1)
        self.assertGreaterEqual(len(app.multiselect), 2)
        self.assertGreaterEqual(len(app.toggle), 3)


if __name__ == "__main__":
    unittest.main()
