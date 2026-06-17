#!/usr/bin/env python3
"""Audit source catalog readiness before building config/samples.tsv."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


SAMPLE_COLUMNS = [
    "record_type",
    "genome_id",
    "accession",
    "source",
    "isolation_host",
    "host_species",
    "host_strain",
    "country",
    "year",
    "phage_lifestyle",
    "genome_length",
    "gc_percent",
    "K_type",
    "O_type",
    "ST",
    "AMR_markers",
    "virulence_markers",
    "raw_sequence_path",
    "notes",
]

DEFAULT_IDENTITY_COLUMNS_ANY = ["genome_id", "accession", "raw_sequence_path"]

COLUMN_ALIASES = {
    "record_type": ["record_type", "type", "entry_type"],
    "genome_id": ["genome_id", "genome", "id", "sample", "sample_id", "assembly", "assembly_id"],
    "accession": ["accession", "accessions", "nucleotide_accession", "genbank_accession", "refseq_accession"],
    "source": ["source", "database", "source_database", "data_source"],
    "isolation_host": ["isolation_host", "isolation host", "host", "reported_host"],
    "host_species": ["host_species", "host species", "species", "bacterial_species"],
    "host_strain": ["host_strain", "host strain", "strain", "bacterial_strain"],
    "country": ["country", "location", "region"],
    "year": ["year", "isolation_year", "collection_year", "publication_year"],
    "phage_lifestyle": ["phage_lifestyle", "lifestyle", "predicted_lifestyle"],
    "genome_length": ["genome_length", "length", "length_bp", "genome_size", "genome_size_bp"],
    "gc_percent": ["gc_percent", "gc", "gc_content", "gc_percentage"],
    "K_type": ["K_type", "k_type", "capsule_type", "k_locus", "K_locus"],
    "O_type": ["O_type", "o_type", "o_antigen", "o_locus", "O_locus"],
    "ST": ["ST", "st", "mlst", "sequence_type"],
    "AMR_markers": ["AMR_markers", "amr_markers", "amr_genes", "resistance_genes"],
    "virulence_markers": ["virulence_markers", "virulence_genes", "virulence_loci"],
    "raw_sequence_path": ["raw_sequence_path", "sequence_path", "fasta", "fasta_path", "genbank_path"],
    "notes": ["notes", "note", "comment", "comments"],
}

READINESS_COLUMNS = [
    "source_id",
    "path",
    "enabled",
    "required",
    "exists",
    "row_count",
    "recognized_columns",
    "identity_columns_present",
    "missing_identity_columns",
    "missing_recommended_columns",
    "duplicate_genome_ids",
    "ready_status",
    "suggested_action",
    "notes",
]

REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


class AuditError(Exception):
    """Raised for invalid catalog configuration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit source catalog readiness for dataset curation.")
    parser.add_argument("--catalog", required=True, help="YAML source catalog.")
    parser.add_argument("--readiness-output", required=True, help="Output readiness TSV.")
    parser.add_argument("--report-output", required=True, help="Output audit report TSV.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise AuditError("PyYAML is required to read the source catalog.") from exc
    if not path.exists():
        raise AuditError(f"Source catalog does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise AuditError("Source catalog must be a YAML mapping.")
    return data


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def bool_value(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = normalize(value).lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
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


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


def recognized_columns(fieldnames: list[str]) -> set[str]:
    by_normalized = {normalize_header(name) for name in fieldnames}
    recognized = set()
    for canonical, aliases in COLUMN_ALIASES.items():
        if any(normalize_header(alias) in by_normalized for alias in aliases):
            recognized.add(canonical)
    return recognized


def configured_list(value: object, fallback: list[str]) -> list[str]:
    if value is None:
        return fallback
    if isinstance(value, list):
        parsed = [normalize(item) for item in value]
    else:
        parsed = [item.strip() for item in re.split(r"[;,]", normalize(value))]
    parsed = [item for item in parsed if item]
    return parsed or fallback


def identity_columns_any(catalog: dict, source: dict) -> list[str]:
    value = source.get("identity_columns_any", catalog.get("identity_columns_any"))
    candidates = configured_list(value, DEFAULT_IDENTITY_COLUMNS_ANY)
    return [column for column in candidates if column in SAMPLE_COLUMNS] or DEFAULT_IDENTITY_COLUMNS_ANY


def duplicate_ids(rows: list[dict[str, str]], fieldnames: list[str]) -> list[str]:
    recognized = recognized_columns(fieldnames)
    if "genome_id" not in recognized:
        return []
    id_columns = [name for name in fieldnames if normalize_header(name) in {normalize_header(alias) for alias in COLUMN_ALIASES["genome_id"]}]
    if not id_columns:
        return []
    id_col = id_columns[0]
    counts = Counter(row.get(id_col, "") for row in rows if not is_missing(row.get(id_col, "")))
    return sorted(value for value, count in counts.items() if count > 1)


def classify_source(source: dict, catalog_path: Path, catalog: dict, index: int) -> dict[str, str]:
    source_id = normalize(source.get("source_id")) or f"source_{index}"
    enabled = bool_value(source.get("enabled", True), True)
    required = bool_value(source.get("required", False), False)
    path_text = normalize(source.get("path"))
    identity_candidates = identity_columns_any(catalog, source)
    if is_missing(path_text):
        return {
            "source_id": source_id,
            "path": "",
            "enabled": str(enabled).lower(),
            "required": str(required).lower(),
            "exists": "false",
            "row_count": "0",
            "recognized_columns": "",
            "identity_columns_present": "",
            "missing_identity_columns": ";".join(identity_candidates),
            "missing_recommended_columns": ";".join(SAMPLE_COLUMNS),
            "duplicate_genome_ids": "",
            "ready_status": "invalid_catalog_entry",
            "suggested_action": "add a path for this source or disable/remove the source entry",
            "notes": "source entry has no path",
        }
    path = resolve_path(path_text)
    if not path.exists():
        return {
            "source_id": source_id,
            "path": display_path(path),
            "enabled": str(enabled).lower(),
            "required": str(required).lower(),
            "exists": "false",
            "row_count": "0",
            "recognized_columns": "",
            "identity_columns_present": "",
            "missing_identity_columns": ";".join(identity_candidates),
            "missing_recommended_columns": ";".join(SAMPLE_COLUMNS),
            "duplicate_genome_ids": "",
            "ready_status": "missing_required" if required else "missing_optional",
            "suggested_action": "create the source manifest or set enabled false until available",
            "notes": "source manifest path does not exist",
        }
    fieldnames, rows = read_tsv(path)
    recognized = recognized_columns(fieldnames)
    identity_present = [column for column in identity_candidates if column in recognized]
    missing_identity = [column for column in identity_candidates if column not in recognized]
    missing = [column for column in SAMPLE_COLUMNS if column not in recognized]
    duplicates = duplicate_ids(rows, fieldnames)
    row_count = len(rows)
    if duplicates:
        status = "duplicate_ids"
        action = "deduplicate genome_id values before enabling this source"
    elif row_count == 0 and enabled:
        status = "enabled_empty"
        action = "populate rows or disable this source until curated"
    elif row_count == 0:
        status = "planned_placeholder"
        action = "populate rows and enable this source after review"
    elif not identity_present:
        status = "missing_identity_columns"
        action = "add at least one identity column: " + ";".join(identity_candidates)
    elif missing:
        status = "ready_with_defaults" if enabled else "populated_disabled_with_defaults"
        action = "review missing recommended columns; builder will fill defaults or NA"
    elif enabled:
        status = "ready_enabled"
        action = "source will be included by the sample builder"
    else:
        status = "populated_disabled"
        action = "review rows and set enabled true when ready"
    return {
        "source_id": source_id,
        "path": display_path(path),
        "enabled": str(enabled).lower(),
        "required": str(required).lower(),
        "exists": "true",
        "row_count": str(row_count),
        "recognized_columns": ";".join(sorted(recognized)),
        "identity_columns_present": ";".join(identity_present),
        "missing_identity_columns": ";".join(missing_identity),
        "missing_recommended_columns": ";".join(missing),
        "duplicate_genome_ids": ";".join(duplicates),
        "ready_status": status,
        "suggested_action": action,
        "notes": normalize(source.get("notes")),
    }


def audit_catalog(catalog_path: Path, catalog: dict) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sources = catalog.get("sources", [])
    if not isinstance(sources, list):
        raise AuditError("source catalog 'sources' must be a list")
    rows = []
    report: list[dict[str, str]] = []
    if not sources:
        add_report(report, "warning", "sources", "No sources configured in the catalog.")
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            rows.append(
                {
                    "source_id": f"source_{index}",
                    "path": "",
                    "enabled": "false",
                    "required": "false",
                    "exists": "false",
                    "row_count": "0",
                    "recognized_columns": "",
                    "identity_columns_present": "",
                    "missing_identity_columns": ";".join(DEFAULT_IDENTITY_COLUMNS_ANY),
                    "missing_recommended_columns": ";".join(SAMPLE_COLUMNS),
                    "duplicate_genome_ids": "",
                    "ready_status": "invalid_catalog_entry",
                    "suggested_action": "replace source entry with a mapping",
                    "notes": "source entry is not a mapping",
                }
            )
            add_report(report, "error", f"source_{index}", "Source entry is not a mapping.")
            continue
        row = classify_source(source, catalog_path, catalog, index)
        rows.append(row)
        if row["ready_status"] in {"ready_enabled", "populated_disabled"}:
            add_report(report, "info", row["source_id"], f"{row['ready_status']}: {row['row_count']} rows.")
        elif row["ready_status"] in {"ready_with_defaults", "populated_disabled_with_defaults"}:
            add_report(report, "warning", row["source_id"], f"{row['ready_status']}: {row['suggested_action']}")
        elif row["ready_status"] in {"planned_placeholder", "missing_optional"}:
            add_report(report, "warning", row["source_id"], f"{row['ready_status']}: {row['suggested_action']}")
        else:
            add_report(report, "error", row["source_id"], f"{row['ready_status']}: {row['suggested_action']}")
    return rows, report


def main() -> int:
    args = parse_args()
    catalog_path = Path(args.catalog)
    try:
        catalog = load_yaml(catalog_path)
        readiness, report = audit_catalog(catalog_path, catalog)
        write_tsv(Path(args.readiness_output), READINESS_COLUMNS, readiness)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        error_count = sum(1 for row in report if row.get("severity") == "error")
        warning_count = sum(1 for row in report if row.get("severity") == "warning")
        print(f"Audited {len(readiness)} sources: {error_count} errors, {warning_count} warnings.")
        return 1 if error_count else 0
    except AuditError as exc:
        report = [{"severity": "error", "item": "catalog", "message": str(exc)}]
        write_tsv(Path(args.readiness_output), READINESS_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        print(f"Source catalog audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
