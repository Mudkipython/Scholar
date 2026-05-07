import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a normalized journal ranking CSV from JCR/CAS workbooks.")
    parser.add_argument("--jcr", type=Path, required=True)
    parser.add_argument("--cas2025", type=Path, required=True)
    parser.add_argument("--cas2023", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/journal_rankings.csv"))
    args = parser.parse_args()

    df = build_reference_table(args.jcr, args.cas2025, args.cas2023)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(df)} rows to {args.output}")


def build_reference_table(jcr_path: Path, cas2025_path: Path, cas2023_path: Path) -> pd.DataFrame:
    records = {}

    jcr = pd.read_excel(jcr_path, sheet_name="2024JCR")
    for _, row in jcr.iterrows():
        journal = _clean(row.get("期刊名"))
        if not journal:
            continue
        record = _record(records, journal)
        record["journal"] = journal
        record["issn_l"] = _clean(row.get("ISSN")) or record.get("issn_l", "")
        record["eissn"] = _clean(row.get("eISSN")) or record.get("eissn", "")
        record["jcr_quartile"] = _clean(row.get("Quartile")) or record.get("jcr_quartile", "")
        record["jcr_category"] = _clean(row.get("Category")) or record.get("jcr_category", "")
        record["jif_2024"] = _clean(row.get("2024JIF")) or record.get("jif_2024", "")
        record["jif_rank"] = _clean(row.get("JIF rank")) or record.get("jif_rank", "")
        record["jcr_2023_quartile"] = _clean(row.get("2023分区")) or record.get("jcr_2023_quartile", "")
        record["local_metric_source"] = _append_source(record.get("local_metric_source", ""), "2024 JCR")

    for path, sheet_name in [(jcr_path, "2025中国科学院分区表"), (cas2025_path, "Sheet1")]:
        cas = pd.read_excel(path, sheet_name=sheet_name)
        for _, row in cas.iterrows():
            journal = _clean(row.get("期刊名称")) or _clean(row.get("Journal"))
            if not journal:
                continue
            record = _record(records, journal)
            record.setdefault("journal", journal)
            record["cas_zone"] = _zone(row.get("2025分区", row.get("分区"))) or record.get("cas_zone", "")
            record["cas_2025_zone"] = _zone(row.get("2025分区", row.get("分区"))) or record.get("cas_2025_zone", "")
            record["cas_top"] = _clean(row.get("Top")) or record.get("cas_top", "")
            record["open_access"] = _clean(row.get("Open Access")) or record.get("open_access", "")
            record["local_metric_source"] = _append_source(record.get("local_metric_source", ""), "2025 CAS")

    for sheet_name, prefix in [("大类学科", "large"), ("小类学科", "small")]:
        cas = pd.read_excel(cas2023_path, sheet_name=sheet_name)
        for _, row in cas.iterrows():
            journal = _clean(row.get("刊名"))
            if not journal:
                continue
            record = _record(records, journal)
            record.setdefault("journal", journal)
            record["issn_l"] = record.get("issn_l", "") or _clean(row.get("ISSN"))
            record[f"cas_2023_{prefix}_zone"] = _zone(row.get("分区"))
            record[f"cas_2023_{prefix}_subject"] = _clean(row.get("学科"))
            if prefix == "large":
                record["cas_zone"] = record.get("cas_zone", "") or record[f"cas_2023_{prefix}_zone"]
                record["cas_subject"] = record.get("cas_subject", "") or record[f"cas_2023_{prefix}_subject"]
            record["is_review"] = record.get("is_review", "") or _clean(row.get("是否review"))
            record["local_metric_source"] = _append_source(record.get("local_metric_source", ""), "2023 CAS")

    columns = [
        "journal",
        "issn_l",
        "eissn",
        "jcr_quartile",
        "cas_zone",
        "cas_subject",
        "jcr_category",
        "local_metric_source",
        "jif_2024",
        "jif_rank",
        "jcr_2023_quartile",
        "cas_2025_zone",
        "cas_2023_large_zone",
        "cas_2023_large_subject",
        "cas_2023_small_zone",
        "cas_2023_small_subject",
        "cas_top",
        "open_access",
        "is_review",
    ]
    df = pd.DataFrame(records.values())
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    df = df[columns].sort_values("journal", key=lambda s: s.str.lower()).reset_index(drop=True)
    return df


def _record(records: dict, journal: str) -> dict:
    key = _journal_key(journal)
    if key not in records:
        records[key] = {"journal": journal}
    return records[key]


def _clean(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _zone(value) -> str:
    text = _clean(value)
    if not text:
        return ""
    if text.endswith("区"):
        return text
    if text in {"1", "2", "3", "4"}:
        return f"{text}区"
    return text


def _journal_key(value: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def _append_source(existing: str, source: str) -> str:
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    if source not in parts:
        parts.append(source)
    return "; ".join(parts)


if __name__ == "__main__":
    main()
