#!/usr/bin/env python3
"""Preflight reviewed exports against metric-specific sample-support requirements."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


PREFLIGHT_COLUMNS = [
    "metric",
    "source_id",
    "recommended_rank",
    "expected_export_path",
    "export_exists",
    "export_row_count",
    "fields_to_populate",
    "missing_fields",
    "satisfying_row_count",
    "preflight_status",
    "blocking_issue",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
IDENTITY_FIELDS = {"genome_id", "accession", "raw_sequence_path"}
HOST_METADATA_FIELDS = {"host_species", "host_strain", "isolation_host"}
COLUMN_ALIASES = {
    "genome_id": ["genome_id", "genome", "id", "sample", "sample_id", "assembly", "assembly_id"],
    "accession": ["accession", "accessions", "public_accession", "nucleotide_accession", "genbank_accession", "refseq_accession"],
    "raw_sequence_path": ["raw_sequence_path", "sequence_path", "fasta", "fasta_path", "genbank_path"],
    "host_species": ["host_species", "host species", "species", "host", "organism", "bacterial_species"],
    "host_strain": ["host_strain", "host strain", "strain", "bacterial_strain"],
    "isolation_host": ["isolation_host", "isolation host", "reported_host"],
    "K_type": ["K_type", "k_type", "capsule_type", "k_locus", "K_locus"],
    "O_type": ["O_type", "o_type", "o_antigen", "o_locus", "O_locus"],
    "ST": ["ST", "st", "mlst", "sequence_type"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight source exports against sample-support bridge requirements.")
    parser.add_argument("--bridge", required=True, help="sample_support_source_bridge.tsv.")
    parser.add_argument("--preflight-output", required=True, help="Output metric/source preflight TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [token.strip() for token in value.replace(",", ";").split(";") if token.strip()]


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def canonical_header_lookup(fieldnames: list[str]) -> dict[str, str]:
    by_normalized = {normalize_header(name): name for name in fieldnames}
    lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized = normalize_header(alias)
            if normalized in by_normalized:
                lookup[canonical] = by_normalized[normalized]
                break
    return lookup


def canonicalize_export(fieldnames: list[str], rows: list[dict[str, str]]) -> tuple[list[str], list[dict[str, str]]]:
    lookup = canonical_header_lookup(fieldnames)
    canonical_fields = set(fieldnames) | set(lookup)
    canonical_rows: list[dict[str, str]] = []
    for row in rows:
        new_row = dict(row)
        for canonical, original in lookup.items():
            if is_missing(new_row.get(canonical, "")) and original in row:
                new_row[canonical] = row.get(original, "")
        canonical_rows.append(new_row)
    return sorted(canonical_fields), canonical_rows


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def read_export(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    delimiter = "," if path.suffix.lower() == ".csv" else "\t"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return canonicalize_export(fieldnames, rows)


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def row_has_any(row: dict[str, str], fields: Iterable[str]) -> bool:
    return any(not is_missing(row.get(field, "")) for field in fields)


def missing_required_fields(metric: str, fields: list[str], fieldnames: list[str]) -> list[str]:
    present = set(fieldnames)
    identity_fields = [field for field in fields if field in IDENTITY_FIELDS]
    host_fields = [field for field in fields if field in HOST_METADATA_FIELDS]
    specific_fields = [field for field in fields if field not in IDENTITY_FIELDS and field not in HOST_METADATA_FIELDS]
    missing: list[str] = []
    if identity_fields and not any(field in present for field in identity_fields):
        missing.append("identity_any:" + ";".join(identity_fields))
    if metric == "min_phage_rows_with_host_metadata" and host_fields and not any(field in present for field in host_fields):
        missing.append("host_metadata_any:" + ";".join(host_fields))
    for field in specific_fields:
        if field not in present:
            missing.append(field)
    return missing


def row_satisfies(metric: str, fields: list[str], row: dict[str, str]) -> bool:
    available_identity = [field for field in fields if field in IDENTITY_FIELDS]
    available_host = [field for field in fields if field in HOST_METADATA_FIELDS]
    non_identity = [field for field in fields if field not in IDENTITY_FIELDS and field not in HOST_METADATA_FIELDS]
    if metric == "min_total_records":
        return row_has_any(row, available_identity or fields)
    if metric in {"min_cultured_phages", "min_host_genomes", "min_prophages"}:
        return row_has_any(row, available_identity) if available_identity else True
    if metric == "min_phage_rows_with_host_metadata":
        return row_has_any(row, available_identity) and row_has_any(row, available_host)
    if non_identity:
        return all(not is_missing(row.get(field, "")) for field in non_identity) and (row_has_any(row, available_identity) if available_identity else True)
    return row_has_any(row, fields)


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    bridge_path = resolve(root, args.bridge)
    _, bridge_rows = read_tsv(bridge_path)
    preflight_rows: list[dict[str, str]] = []

    for bridge in bridge_rows:
        export_text = bridge.get("expected_export_path", "")
        export_path = resolve(root, export_text) if not is_missing(export_text) else Path("")
        fields = split_values(bridge.get("fields_to_populate", ""))
        base = {
            "metric": bridge.get("metric", ""),
            "source_id": bridge.get("source_id", ""),
            "recommended_rank": bridge.get("recommended_rank", ""),
            "expected_export_path": display_path(root, export_path) if str(export_path) else "NA",
            "fields_to_populate": ";".join(fields) if fields else "NA",
        }
        if not export_path.exists():
            preflight_rows.append({
                **base,
                "export_exists": "false",
                "export_row_count": "0",
                "missing_fields": ";".join(fields) if fields else "NA",
                "satisfying_row_count": "0",
                "preflight_status": "missing_export",
                "blocking_issue": "true",
                "next_action": "Create this reviewed export, then rerun source and sample-support preflight.",
            })
            continue

        fieldnames, export_rows = read_export(export_path)
        missing_fields = missing_required_fields(bridge.get("metric", ""), fields, fieldnames)
        if missing_fields:
            satisfying = 0
            status = "missing_metric_fields"
            blocking = "true"
            action = "Add missing metric-critical columns to the reviewed export template/output."
        else:
            satisfying = sum(1 for row in export_rows if row_satisfies(bridge.get("metric", ""), fields, row))
            if not export_rows:
                status = "empty_export"
                blocking = "true"
                action = "Add reviewed data rows or disable this source until curated."
            elif satisfying == 0:
                status = "no_metric_supporting_rows"
                blocking = "true"
                action = "Populate metric-critical fields for at least one reviewed row."
            else:
                status = "metric_support_ready"
                blocking = "false"
                action = "Run source export validation/import and regenerate sample support outputs."
        preflight_rows.append({
            **base,
            "export_exists": "true",
            "export_row_count": str(len(export_rows)),
            "missing_fields": ";".join(missing_fields) if missing_fields else "NA",
            "satisfying_row_count": str(satisfying),
            "preflight_status": status,
            "blocking_issue": blocking,
            "next_action": action,
        })

    blocking_count = sum(1 for row in preflight_rows if row.get("blocking_issue") == "true")
    ready_count = sum(1 for row in preflight_rows if row.get("preflight_status") == "metric_support_ready")
    report_rows = [
        {"severity": "info", "item": "sample_support_export_preflight", "message": f"bridge_rows={len(preflight_rows)}; ready={ready_count}; blocking={blocking_count}"}
    ]
    if blocking_count:
        report_rows.append({"severity": "warning", "item": "sample_support_export_preflight", "message": "One or more source exports do not yet satisfy metric-specific sample-support requirements."})

    write_tsv(resolve(root, args.preflight_output), PREFLIGHT_COLUMNS, preflight_rows)
    write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Preflighted {len(preflight_rows)} sample-support export requirements with {blocking_count} blocking rows.")


if __name__ == "__main__":
    main()
