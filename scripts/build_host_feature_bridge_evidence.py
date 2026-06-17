#!/usr/bin/env python3
"""Build reviewed host-feature bridge evidence TSVs from source manifests."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


KLEBORATE_COLUMNS = [
    "host_genome_id",
    "sample",
    "species",
    "species_match",
    "ST",
    "virulence_score",
    "resistance_score",
    "AMR_markers",
    "virulence_markers",
    "evidence_source",
    "notes",
]
KAPTIVE_COLUMNS = [
    "host_genome_id",
    "sample",
    "K_locus",
    "K_type",
    "K_confidence",
    "O_locus",
    "O_type",
    "O_confidence",
    "evidence_source",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract reviewed host K/O/ST bridge evidence from a source manifest. "
            "This normalizes existing curated metadata only; it does not run Kleborate or Kaptive."
        )
    )
    parser.add_argument("--host-manifest", required=True, help="Reviewed host source manifest TSV.")
    parser.add_argument("--kleborate-output", required=True, help="Output Kleborate-style bridge TSV.")
    parser.add_argument("--kaptive-output", required=True, help="Output Kaptive-style bridge TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
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


def note_value(notes: str, key: str) -> str:
    match = re.search(rf"{re.escape(key)}=([^,;]+)", notes)
    return match.group(1).strip().rstrip(".") if match else ""


def split_virulence(markers: str, prefix: str) -> str:
    values = [part.strip() for part in re.split(r"[;,]", markers) if part.strip()]
    hits = [value for value in values if value.lower().startswith(prefix.lower())]
    return ";".join(hits)


def reviewed_host_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        if row.get("record_type") != "host":
            continue
        if is_missing(row.get("genome_id")):
            continue
        output.append(row)
    return output


def build_rows(host_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    kleborate_rows: list[dict[str, str]] = []
    kaptive_rows: list[dict[str, str]] = []
    for row in host_rows:
        notes = row.get("notes", "")
        genome_id = row.get("genome_id", "")
        virulence = row.get("virulence_markers", "")
        shared_note = (
            "Bridge evidence normalized from reviewed host source manifest; "
            "source notes report temporary Kleborate/Kaptive validation; rerun production tools for manuscript-scale analysis. "
            + notes
        )
        kleborate_rows.append(
            {
                "host_genome_id": genome_id,
                "sample": genome_id,
                "species": row.get("host_species", ""),
                "species_match": note_value(notes, "species") or row.get("host_species", ""),
                "ST": row.get("ST", ""),
                "virulence_score": note_value(notes, "virulence_score"),
                "resistance_score": note_value(notes, "resistance_score"),
                "AMR_markers": row.get("AMR_markers", ""),
                "virulence_markers": virulence,
                "evidence_source": "build_host_feature_bridge_evidence.py",
                "notes": shared_note,
            }
        )
        kaptive_rows.append(
            {
                "host_genome_id": genome_id,
                "sample": genome_id,
                "K_locus": note_value(notes, "K_locus"),
                "K_type": row.get("K_type", ""),
                "K_confidence": note_value(notes, "K_locus_confidence"),
                "O_locus": note_value(notes, "O_locus"),
                "O_type": row.get("O_type", ""),
                "O_confidence": note_value(notes, "O_locus_confidence"),
                "evidence_source": "build_host_feature_bridge_evidence.py",
                "notes": shared_note,
            }
        )
    return kleborate_rows, kaptive_rows


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    fields, rows = read_tsv(Path(args.host_manifest))
    missing = [column for column in ["record_type", "genome_id", "host_species", "K_type", "O_type", "ST", "notes"] if column not in fields]
    if missing:
        report.append({"severity": "error", "item": "host_manifest", "message": "Missing required columns: " + ";".join(missing)})
        write_tsv(Path(args.kleborate_output), KLEBORATE_COLUMNS, [])
        write_tsv(Path(args.kaptive_output), KAPTIVE_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1
    host_rows = reviewed_host_rows(rows)
    kleborate_rows, kaptive_rows = build_rows(host_rows)
    write_tsv(Path(args.kleborate_output), KLEBORATE_COLUMNS, kleborate_rows)
    write_tsv(Path(args.kaptive_output), KAPTIVE_COLUMNS, kaptive_rows)
    report.append(
        {
            "severity": "info",
            "item": "host_feature_bridge_evidence",
            "message": f"host_rows={len(host_rows)}; kleborate_rows={len(kleborate_rows)}; kaptive_rows={len(kaptive_rows)}",
        }
    )
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
