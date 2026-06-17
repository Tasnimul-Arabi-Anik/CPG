#!/usr/bin/env python3
"""Check whether source curation work orders are satisfied by reviewed export rows."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


ACCEPTANCE_COLUMNS = [
    "work_order_id",
    "source_id",
    "expected_export_path",
    "export_exists",
    "export_row_count",
    "minimum_rows_to_add",
    "required_fields",
    "missing_required_columns",
    "satisfying_row_count",
    "acceptance_status",
    "blocking_issue",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
IDENTITY_FIELDS = {"genome_id", "accession", "raw_sequence_path"}
COLUMN_ALIASES = {
    "genome_id": ["genome_id", "genome", "id", "sample", "sample_id", "assembly", "assembly_id"],
    "accession": ["accession", "accessions", "public_accession", "nucleotide_accession", "genbank_accession", "refseq_accession", "sequence_accession"],
    "raw_sequence_path": ["raw_sequence_path", "sequence_path", "fasta", "fasta_path", "genbank_path", "file", "filepath"],
    "host_species": ["host_species", "host species", "species", "host", "organism", "bacterial_species", "host_organism"],
    "host_strain": ["host_strain", "host strain", "strain", "isolate", "isolate_name"],
    "isolation_host": ["isolation_host", "isolation host", "reported_host"],
    "K_type": ["K_type", "k_type", "capsule_type", "k_locus", "K_locus"],
    "O_type": ["O_type", "o_type", "o_antigen", "o_locus", "O_locus"],
    "ST": ["ST", "st", "mlst", "sequence_type"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check reviewed source exports against source curation work orders.")
    parser.add_argument("--work-orders", required=True, help="source_curation_work_order.tsv.")
    parser.add_argument("--acceptance-output", required=True, help="Output acceptance TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative export paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def int_value(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def read_export(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    delimiter = "," if path.suffix.lower() == ".csv" else "\t"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return canonicalize(fieldnames, rows)


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def canonicalize(fieldnames: list[str], rows: list[dict[str, str]]) -> tuple[list[str], list[dict[str, str]]]:
    by_normalized = {normalize_header(name): name for name in fieldnames}
    lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original = by_normalized.get(normalize_header(alias))
            if original:
                lookup[canonical] = original
                break
    output_rows: list[dict[str, str]] = []
    for row in rows:
        new_row = dict(row)
        for canonical, original in lookup.items():
            if is_missing(new_row.get(canonical, "")):
                new_row[canonical] = row.get(original, "")
        output_rows.append(new_row)
    return sorted(set(fieldnames) | set(lookup)), output_rows


def missing_columns(required_fields: list[str], fieldnames: list[str]) -> list[str]:
    present = set(fieldnames)
    missing: list[str] = []
    identity_required = [field for field in required_fields if field in IDENTITY_FIELDS]
    if identity_required and not any(field in present for field in identity_required):
        missing.append("identity_any:" + ";".join(identity_required))
    for field in required_fields:
        if field in IDENTITY_FIELDS:
            continue
        if field not in present:
            missing.append(field)
    return missing


def row_satisfies(required_fields: list[str], row: dict[str, str]) -> bool:
    identity_fields = [field for field in required_fields if field in IDENTITY_FIELDS]
    if identity_fields and not any(not is_missing(row.get(field, "")) for field in identity_fields):
        return False
    for field in required_fields:
        if field in IDENTITY_FIELDS:
            continue
        if is_missing(row.get(field, "")):
            return False
    return True


def check_one(root: Path, work: dict[str, str]) -> dict[str, str]:
    export_text = work.get("expected_export_path", "")
    export_path = resolve(root, export_text) if not is_missing(export_text) else Path("")
    required_fields = split_values(work.get("required_fields", ""))
    minimum_rows = int_value(work.get("minimum_rows_to_add", "0"))
    base = {
        "work_order_id": work.get("work_order_id", ""),
        "source_id": work.get("source_id", ""),
        "expected_export_path": display_path(root, export_path) if str(export_path) else "NA",
        "minimum_rows_to_add": str(minimum_rows),
        "required_fields": ";".join(required_fields) if required_fields else "NA",
    }
    if not required_fields:
        return {
            **base,
            "export_exists": "false",
            "export_row_count": "0",
            "missing_required_columns": "NA",
            "satisfying_row_count": "0",
            "acceptance_status": "no_required_fields",
            "blocking_issue": "true",
            "next_action": "Regenerate source readiness dashboard and work orders after source export fields are available.",
        }
    if not str(export_path):
        return {
            **base,
            "export_exists": "false",
            "export_row_count": "0",
            "missing_required_columns": ";".join(required_fields),
            "satisfying_row_count": "0",
            "acceptance_status": "no_export_path_configured",
            "blocking_issue": "true",
            "next_action": "Add an expected export path or remove this source from work-order generation.",
        }
    if not export_path.exists():
        return {
            **base,
            "export_exists": "false",
            "export_row_count": "0",
            "missing_required_columns": ";".join(required_fields) if required_fields else "NA",
            "satisfying_row_count": "0",
            "acceptance_status": "missing_export",
            "blocking_issue": "true",
            "next_action": "Create and populate the reviewed export for this work order.",
        }
    if export_path.is_dir():
        return {
            **base,
            "export_exists": "false",
            "export_row_count": "0",
            "missing_required_columns": ";".join(required_fields),
            "satisfying_row_count": "0",
            "acceptance_status": "export_path_is_directory",
            "blocking_issue": "true",
            "next_action": "Configure expected_export_path as a TSV or CSV file path, not a directory.",
        }
    fieldnames, rows = read_export(export_path)
    missing = missing_columns(required_fields, fieldnames)
    satisfying = 0 if missing else sum(1 for row in rows if row_satisfies(required_fields, row))
    if not rows:
        status = "export_empty"
        blocking = "true"
        action = "Add reviewed rows to this export."
    elif missing:
        status = "missing_required_columns"
        blocking = "true"
        action = "Add required columns to the reviewed export."
    elif satisfying < minimum_rows:
        status = "insufficient_reviewed_rows"
        blocking = "true"
        action = "Populate required fields in additional reviewed rows."
    else:
        status = "accepted"
        blocking = "false"
        action = "Rerun source import, enablement, sample support, and downstream workflow stages."
    return {
        **base,
        "export_exists": "true",
        "export_row_count": str(len(rows)),
        "missing_required_columns": ";".join(missing) if missing else "NA",
        "satisfying_row_count": str(satisfying),
        "acceptance_status": status,
        "blocking_issue": blocking,
        "next_action": action,
    }


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    _, work_rows = read_tsv(resolve(root, args.work_orders))
    acceptance_rows = [check_one(root, row) for row in work_rows]
    accepted = sum(1 for row in acceptance_rows if row.get("acceptance_status") == "accepted")
    blocking = sum(1 for row in acceptance_rows if row.get("blocking_issue") == "true")
    report_rows = [
        {"severity": "info", "item": "source_work_order_acceptance", "message": f"work_orders={len(acceptance_rows)}; accepted={accepted}; blocking={blocking}"}
    ]
    if blocking:
        report_rows.append({"severity": "warning", "item": "source_work_order_acceptance", "message": "One or more source curation work orders are not yet accepted."})
    write_tsv(resolve(root, args.acceptance_output), ACCEPTANCE_COLUMNS, acceptance_rows)
    write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Checked {len(acceptance_rows)} source work order(s); accepted={accepted}; blocking={blocking}.")


if __name__ == "__main__":
    main()
