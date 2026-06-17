#!/usr/bin/env python3
"""Map failed sample-support metrics to source exports that can satisfy them."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


BRIDGE_COLUMNS = [
    "metric",
    "current_value",
    "threshold",
    "metric_status",
    "source_id",
    "recommended_rank",
    "record_layer",
    "expected_record_type",
    "expected_export_path",
    "starter_template_path",
    "starter_readme_path",
    "fields_to_populate",
    "required_for_hypotheses",
    "support_rationale",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

METRIC_REQUIREMENTS = {
    "min_total_records": {
        "layers": {"cultured_phages", "literature_curated_phages", "prophages", "host_genomes", "metagenomic_discovery"},
        "fields": ["genome_id", "accession", "raw_sequence_path"],
        "rationale": "Any enabled source row with an identity field increases total sample rows.",
    },
    "min_cultured_phages": {
        "layers": {"cultured_phages", "literature_curated_phages"},
        "fields": ["genome_id", "accession", "raw_sequence_path", "host_species", "host_strain"],
        "rationale": "Cultured-phage sources provide phage rows for H1, H3, H4, and H6.",
    },
    "min_host_genomes": {
        "layers": {"host_genomes"},
        "fields": ["genome_id", "accession", "raw_sequence_path", "host_species", "host_strain"],
        "rationale": "Host-genome rows provide the bacterial background needed for K/O/ST and defense analyses.",
    },
    "min_prophages": {
        "layers": {"prophages"},
        "fields": ["genome_id", "accession", "raw_sequence_path", "host_species", "host_strain"],
        "rationale": "Prophage rows are required for the prophage reservoir tests in H2 and H5.",
    },
    "min_k_typed_records": {
        "layers": {"host_genomes", "prophages"},
        "fields": ["K_type", "genome_id", "accession", "raw_sequence_path"],
        "rationale": "K-type fields on host or prophage-linked records unlock capsule association tests.",
    },
    "min_o_typed_records": {
        "layers": {"host_genomes", "prophages"},
        "fields": ["O_type", "genome_id", "accession", "raw_sequence_path"],
        "rationale": "O-type fields on host or prophage-linked records unlock LPS association tests.",
    },
    "min_st_typed_records": {
        "layers": {"host_genomes", "prophages"},
        "fields": ["ST", "genome_id", "accession", "raw_sequence_path"],
        "rationale": "ST fields support lineage-linked prophage and defense-burden tests.",
    },
    "min_phage_rows_with_host_metadata": {
        "layers": {"cultured_phages", "literature_curated_phages"},
        "fields": ["host_species", "host_strain", "isolation_host", "genome_id", "accession", "raw_sequence_path"],
        "rationale": "Cultured phage rows need host metadata to connect phage modules to Klebsiella backgrounds.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map sample-support failures to prioritized source exports.")
    parser.add_argument("--sample-support-summary", required=True, help="sample_support_summary.tsv from audit_sample_support.py.")
    parser.add_argument("--minimum-source-plan", required=True, help="minimum_source_curation_plan.tsv.")
    parser.add_argument("--column-dictionary", required=True, help="source_export_column_dictionary.tsv.")
    parser.add_argument("--bridge-output", required=True, help="Output metric-to-source bridge TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def parse_rank(row: dict[str, str]) -> int:
    try:
        return int(float(row.get("recommended_rank", "999")))
    except ValueError:
        return 999


def available_columns(dictionary_rows: list[dict[str, str]], source_id: str) -> set[str]:
    return {row.get("column_name", "") for row in dictionary_rows if row.get("source_id") == source_id}


def expected_record_type(record_layer: str) -> str:
    if record_layer in {"cultured_phages", "literature_curated_phages"}:
        return "phage"
    if record_layer == "host_genomes":
        return "host"
    if record_layer == "prophages":
        return "prophage"
    if record_layer == "metagenomic_discovery":
        return "metagenomic_viral_contig"
    return "NA"


def main() -> None:
    args = parse_args()
    _, support_rows = read_tsv(Path(args.sample_support_summary))
    _, source_rows = read_tsv(Path(args.minimum_source_plan))
    _, dictionary_rows = read_tsv(Path(args.column_dictionary))

    failed_or_all = [row for row in support_rows if row.get("status") == "fail"] or support_rows
    bridge_rows: list[dict[str, str]] = []
    for metric_row in failed_or_all:
        metric = metric_row.get("metric", "")
        requirement = METRIC_REQUIREMENTS.get(metric)
        if not requirement:
            continue
        candidate_sources = [
            row for row in sorted(source_rows, key=parse_rank)
            if row.get("record_layer") in requirement["layers"]
        ]
        for source in candidate_sources:
            source_id = source.get("source_id", "")
            present = available_columns(dictionary_rows, source_id)
            fields = [field for field in requirement["fields"] if field in present]
            if not fields:
                fields = list(requirement["fields"])
            bridge_rows.append({
                "metric": metric,
                "current_value": metric_row.get("value", ""),
                "threshold": metric_row.get("threshold", ""),
                "metric_status": metric_row.get("status", ""),
                "source_id": source_id,
                "recommended_rank": source.get("recommended_rank", ""),
                "record_layer": source.get("record_layer", ""),
                "expected_record_type": expected_record_type(source.get("record_layer", "")),
                "expected_export_path": source.get("expected_export_path", ""),
                "starter_template_path": source.get("starter_template_path", ""),
                "starter_readme_path": source.get("starter_readme_path", ""),
                "fields_to_populate": ";".join(fields) if fields else "NA",
                "required_for_hypotheses": source.get("required_for_hypotheses", ""),
                "support_rationale": requirement["rationale"],
                "next_action": source.get("recommended_action", ""),
            })

    report_rows = [
        {"severity": "info", "item": "sample_support_source_bridge", "message": f"metrics={len(failed_or_all)}; bridge_rows={len(bridge_rows)}"}
    ]
    if any(row.get("metric_status") == "fail" for row in bridge_rows):
        report_rows.append({"severity": "warning", "item": "sample_support_source_bridge", "message": "One or more failed sample-support metrics require source export curation."})
    if not bridge_rows:
        report_rows.append({"severity": "warning", "item": "sample_support_source_bridge", "message": "No source bridge rows were generated; check source plan and sample-support summary inputs."})

    write_tsv(Path(args.bridge_output), BRIDGE_COLUMNS, bridge_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote {len(bridge_rows)} sample-support source bridge rows.")


if __name__ == "__main__":
    main()
