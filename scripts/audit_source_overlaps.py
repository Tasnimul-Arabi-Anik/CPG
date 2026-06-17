#!/usr/bin/env python3
"""Audit duplicate and overlapping records in the built source sample table."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


OVERLAP_COLUMNS = [
    "overlap_key_type",
    "overlap_key",
    "record_count",
    "source_count",
    "sources",
    "record_types",
    "genome_ids",
    "accessions",
    "raw_sequence_paths",
    "overlap_status",
    "recommended_action",
]
SOURCE_SUMMARY_COLUMNS = [
    "source",
    "record_count",
    "record_types",
    "unique_genome_ids",
    "unique_accessions",
    "unique_raw_sequence_paths",
    "duplicate_key_count",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit source overlaps after sample-table generation.")
    parser.add_argument("--samples", required=True, help="Built sample table TSV.")
    parser.add_argument("--overlap-output", required=True, help="Output overlap-group TSV.")
    parser.add_argument("--source-summary-output", required=True, help="Output per-source summary TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def join(values: Iterable[str]) -> str:
    cleaned: list[str] = []
    for value in values:
        if not is_missing(value) and value not in cleaned:
            cleaned.append(value)
    return ";".join(cleaned) if cleaned else "NA"


def key_value(row: dict[str, str], key_type: str) -> str:
    if key_type == "genome_id":
        return row.get("genome_id", "")
    if key_type == "accession":
        return row.get("accession", "")
    if key_type == "raw_sequence_path":
        return row.get("raw_sequence_path", "")
    return ""


def group_rows(rows: list[dict[str, str]], key_type: str) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        value = key_value(row, key_type)
        if is_missing(value):
            continue
        groups.setdefault(value, []).append(row)
    overlap_rows: list[dict[str, str]] = []
    for value, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        sources = [row.get("source", "") for row in members]
        source_count = len({source for source in sources if not is_missing(source)})
        if key_type == "genome_id":
            status = "duplicate_genome_id"
            action = "Review source manifests; sample builder may have retained only the first duplicate genome_id."
        elif key_type == "accession":
            status = "duplicate_accession"
            action = "Review cross-source duplicate accessions before enabling multiple public phage sources."
        else:
            status = "duplicate_raw_sequence_path"
            action = "Review shared raw sequence paths; records may be aliases or host/phage links."
        overlap_rows.append({
            "overlap_key_type": key_type,
            "overlap_key": value,
            "record_count": str(len(members)),
            "source_count": str(source_count),
            "sources": join(sources),
            "record_types": join(row.get("record_type", "") for row in members),
            "genome_ids": join(row.get("genome_id", "") for row in members),
            "accessions": join(row.get("accession", "") for row in members),
            "raw_sequence_paths": join(row.get("raw_sequence_path", "") for row in members),
            "overlap_status": status,
            "recommended_action": action,
        })
    return overlap_rows


def source_summary(rows: list[dict[str, str]], overlap_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_source: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        source = row.get("source", "") or "NA"
        by_source.setdefault(source, []).append(row)
    duplicate_counts: dict[str, int] = {}
    for overlap in overlap_rows:
        for source in overlap.get("sources", "").split(";"):
            if not is_missing(source):
                duplicate_counts[source] = duplicate_counts.get(source, 0) + 1
    summary: list[dict[str, str]] = []
    for source, members in sorted(by_source.items()):
        summary.append({
            "source": source,
            "record_count": str(len(members)),
            "record_types": join(row.get("record_type", "") for row in members),
            "unique_genome_ids": str(len({row.get("genome_id", "") for row in members if not is_missing(row.get("genome_id", ""))})),
            "unique_accessions": str(len({row.get("accession", "") for row in members if not is_missing(row.get("accession", ""))})),
            "unique_raw_sequence_paths": str(len({row.get("raw_sequence_path", "") for row in members if not is_missing(row.get("raw_sequence_path", ""))})),
            "duplicate_key_count": str(duplicate_counts.get(source, 0)),
        })
    return summary


def main() -> None:
    args = parse_args()
    samples_path = Path(args.samples)
    _, rows = read_tsv(samples_path)
    overlap_rows: list[dict[str, str]] = []
    for key_type in ["genome_id", "accession", "raw_sequence_path"]:
        overlap_rows.extend(group_rows(rows, key_type))
    summary_rows = source_summary(rows, overlap_rows)
    report_rows = [
        {"severity": "info", "item": "source_overlap", "message": f"sample_rows={len(rows)}; overlap_groups={len(overlap_rows)}; sources={len(summary_rows)}"},
    ]
    if overlap_rows:
        report_rows.append({"severity": "warning", "item": "source_overlap", "message": "One or more duplicate identity/path groups need source-level review before claims or final atlas counts."})
    write_tsv(Path(args.overlap_output), OVERLAP_COLUMNS, overlap_rows)
    write_tsv(Path(args.source_summary_output), SOURCE_SUMMARY_COLUMNS, summary_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Audited {len(rows)} sample rows and found {len(overlap_rows)} overlap groups.")


if __name__ == "__main__":
    main()
