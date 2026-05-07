# Private journal ranking data

Put licensed/private JCR or CAS ranking data here when deploying privately.

Supported filenames:

- `journal_rankings.csv`
- `journal_rankings.xlsx`
- `journal_rankings.xls`
- `public_journal_rankings.csv`
- `public_journal_rankings.xlsx`
- `public_journal_rankings.xls`
- `private_journal_rankings.csv`
- `private_journal_rankings.xlsx`
- `private_journal_rankings.xls`

You can also set `JOURNAL_RANKINGS_PATH` to point to a file elsewhere, or `JOURNAL_RANKINGS_URL` to point to a public CSV URL.

For direct online loading without uploads or secrets, create:

- `journal_rankings_url.txt`

Put one CSV URL per line. The app will try each URL in order and use the first reachable CSV.

Do not commit licensed JCR/CAS data to a public repository. The `.gitignore` file excludes `journal_rankings.*` and `private_journal_rankings.*`. If this is a private repository and you intentionally want the table deployed with the app, either force-add the file or use `public_journal_rankings.*`.
