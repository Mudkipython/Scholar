# Scholar Journal Metrics

Research-oriented Streamlit tool for matching a scholar's publications to journal-level metrics.

The app supports two query workflows:

1. Paste a public Google Scholar profile URL and parse visible profile papers at low frequency.
2. Search an author by name and optional institution keyword through OpenAlex, then fetch their OpenAlex works.

The interface supports English and Chinese through the sidebar language switcher. Exported column names stay in English so CSV/XLSX outputs remain stable for downstream analysis.

The UI is organized for research workflows:

- Query panel for Scholar profile URLs or OpenAlex author-name search.
- Optional JCR/CAS upload panel with field recognition preview.
- Result quality summary with match rates, low-confidence rows, and notes count.
- Primary result table plus expandable technical/audit columns.
- CSV/XLSX export with all stable columns preserved.

By default this project uses OpenAlex `summary_stats.2yr_mean_citedness` for journal-level metrics. This is an open proxy metric and is **not** official Journal Impact Factor. Official JIF requires Clarivate JCR / Web of Science Journals API access or a JCR export.

You can optionally upload a local JCR/CAS ranking table in the sidebar. The app will merge extra columns such as JCR Q1-Q4 and CAS zones by ISSN-L/ISSN first, then by journal name.

If no file is uploaded, the app can use a private built-in ranking table. Add one of these files before deployment:

- `data/private_journal_rankings.csv`
- `data/private_journal_rankings.xlsx`
- `data/private_journal_rankings.xls`

You can also set `JOURNAL_RANKINGS_PATH` to an absolute or relative file path. User uploads override the private built-in table for that session. The supported private filenames are ignored by Git so licensed data is not accidentally committed.

Supported local ranking columns include:

- `journal`, `journal_name`, `期刊名称`
- `issn_l`, `issn`, `ISSN`
- `jcr_quartile`, `JCR_Q`, `JCR分区`
- `cas_zone`, `中科院分区`, `中科院大类分区`
- `cas_subject`, `中科院大类`, `大类学科`
- `jcr_category`, `JCR类别`, `wos_category`

See `sample_metric_template.csv` for a minimal upload template.

## Deploy on Streamlit Community Cloud

1. Upload this folder to a GitHub repository.
2. In Streamlit Community Cloud, create a new app from that repository.
3. Set the main file path to `streamlit_app.py`.
4. Deploy. Streamlit will install dependencies from `requirements.txt`.

Recommended runtime:

- Python 3.10 or newer.
- Streamlit 1.50 or newer.

No API key is required for the default OpenAlex workflow. The optional `OPENALEX_MAILTO` value can be entered in the app sidebar after deployment. JCR/CAS ranking files are either uploaded at runtime or loaded from your private deployment file; the app does not write uploads to disk.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
python3 -m streamlit run app.py
```

Optional:

```bash
export OPENALEX_MAILTO="you@example.com"
```

## Notebook

Open `notebooks/scholar_journal_metrics_demo.ipynb` and run the cells. The notebook uses the same pipeline functions as the Streamlit app.

## Notes

- Google Scholar does not provide official bulk access. This prototype does not bypass CAPTCHAs, use proxy pools, or reuse login sessions.
- OpenAlex author-name search is the more stable no-key workflow.
- Uploaded JCR/CAS files are processed in memory during the Streamlit session and are not written to disk by the app. Private built-in ranking files are read from `data/` or `JOURNAL_RANKINGS_PATH`.
- Low-confidence matches should be manually reviewed before reporting or publication use.
- Future API extension points:
  - `SERPAPI_API_KEY` for Google Scholar profile/search APIs.
  - `CLARIVATE_API_KEY` for official JCR/JIF through Web of Science Journals API.

## Manual UI acceptance checklist

- Desktop and mobile widths do not overlap text, buttons, or tables.
- Language switch changes labels, helper text, status messages, and errors.
- Scholar URL validation rejects URLs without a `user=` author id.
- Author search shows candidates before querying works.
- JCR/CAS upload shows recognized columns and template download.
- Results show summary metrics, primary columns, technical columns, and both export buttons.
- OpenAlex metrics are never described as official JIF.
