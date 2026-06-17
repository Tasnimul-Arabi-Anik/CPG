#!/usr/bin/env python3
"""Build a normalized samples.tsv table from configured source manifests."""

from __future__ import annotations

import argparse
import csv
import re
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

REPORT_COLUMNS = [
    "severity",
    "source_id",
    "path",
    "row_number",
    "genome_id",
    "field",
    "message",
]

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

MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
DEFAULTS = {
    "record_type": "phage",
    "genome_id": "",
    "accession": "NA",
    "source": "NA",
    "isolation_host": "NA",
    "host_species": "NA",
    "host_strain": "NA",
    "country": "NA",
    "year": "NA",
    "phage_lifestyle": "NA",
    "genome_length": "NA",
    "gc_percent": "NA",
    "K_type": "NA",
    "O_type": "NA",
    "ST": "NA",
    "AMR_markers": "NA",
    "virulence_markers": "NA",
    "raw_sequence_path": "",
    "notes": "",
}


class BuilderError(Exception):
    """Raised for invalid source catalog configuration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build config/samples.tsv from configured source manifests.")
    parser.add_argument("--catalog", required=True, help="YAML source catalog.")
    parser.add_argument("--output-samples", required=True, help="Output normalized samples TSV.")
    parser.add_argument("--report-output", required=True, help="Output source-build report TSV.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise BuilderError("PyYAML is required to read the source catalog.") from exc
    if not path.exists():
        raise BuilderError(f"Source catalog does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BuilderError("Source catalog must be a YAML mapping.")
    return data


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def normalize(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(path)
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


def add_report(
    report: list[dict[str, str]],
    severity: str,
    source_id: str,
    path: str,
    row_number: str,
    genome_id: str,
    field: str,
    message: str,
) -> None:
    report.append(
        {
            "severity": severity,
            "source_id": source_id,
            "path": path,
            "row_number": row_number,
            "genome_id": genome_id or "NA",
            "field": field,
            "message": message,
        }
    )


def source_enabled(source: dict) -> bool:
    value = source.get("enabled", True)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"false", "0", "no", "off"}


def resolve_path(catalog_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def configured_list(value: object, fallback: list[str]) -> list[str]:
    if value is None:
        return fallback
    if isinstance(value, list):
        parsed = [normalize(str(item)) for item in value]
    else:
        parsed = [item.strip() for item in re.split(r"[;,]", normalize(str(value)))]
    parsed = [item for item in parsed if item]
    return parsed or fallback


def identity_columns_any(catalog: dict, source: dict) -> list[str]:
    value = source.get("identity_columns_any", catalog.get("identity_columns_any"))
    candidates = configured_list(value, DEFAULT_IDENTITY_COLUMNS_ANY)
    return [column for column in candidates if column in SAMPLE_COLUMNS] or DEFAULT_IDENTITY_COLUMNS_ANY


def header_lookup(fieldnames: list[str]) -> dict[str, str]:
    by_normalized = {normalize_header(name): name for name in fieldnames}
    lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized = normalize_header(alias)
            if normalized in by_normalized:
                lookup[canonical] = by_normalized[normalized]
                break
    return lookup


def stable_id(record_type: str, accession: str, row_number: int, source_id: str) -> str:
    if not is_missing(accession):
        raw = f"{record_type}_{accession}"
    else:
        raw = f"{record_type}_{source_id}_{row_number}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")


def source_default(source: dict, column: str) -> str:
    key = f"{column}_default"
    if key in source:
        return normalize(source.get(key))
    if column == "source" and source.get("source_label"):
        return normalize(source.get("source_label"))
    return DEFAULTS[column]


def normalize_row(raw: dict[str, str], lookup: dict[str, str], source: dict, row_number: int) -> dict[str, str]:
    output = {}
    for column in SAMPLE_COLUMNS:
        source_column = lookup.get(column, "")
        value = raw.get(source_column, "") if source_column else ""
        if is_missing(value):
            value = source_default(source, column)
        output[column] = normalize(value)

    if is_missing(output["genome_id"]):
        output["genome_id"] = stable_id(output["record_type"], output["accession"], row_number, normalize(source.get("source_id", "source")))
    if source.get("notes"):
        note = normalize(source.get("notes"))
        output["notes"] = note if is_missing(output["notes"]) else output["notes"] + "; " + note
    return output


def build_samples(catalog_path: Path, catalog: dict) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    report: list[dict[str, str]] = []
    samples: list[dict[str, str]] = []
    seen: set[str] = set()
    sources = catalog.get("sources", [])
    if not isinstance(sources, list):
        raise BuilderError("source catalog 'sources' must be a list")
    if not sources:
        add_report(report, "info", "catalog", str(catalog_path), "NA", "NA", "sources", "No sources configured; samples table contains headers only.")
        return samples, report

    for source_index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            add_report(report, "error", f"source_{source_index}", str(catalog_path), "NA", "NA", "source", "Source entry is not a mapping.")
            continue
        source_id = normalize(source.get("source_id")) or f"source_{source_index}"
        if not source_enabled(source):
            add_report(report, "info", source_id, normalize(source.get("path")), "NA", "NA", "enabled", "Source disabled; skipped.")
            continue
        source_path_text = normalize(source.get("path"))
        if is_missing(source_path_text):
            add_report(report, "error", source_id, "NA", "NA", "NA", "path", "Enabled source is missing a path.")
            continue
        source_path = resolve_path(catalog_path, source_path_text)
        required = str(source.get("required", False)).lower() in {"true", "1", "yes"}
        if not source_path.exists():
            severity = "error" if required else "warning"
            add_report(report, severity, source_id, str(source_path), "NA", "NA", "path", "Source manifest does not exist.")
            continue
        fieldnames, rows = read_tsv(source_path)
        lookup = header_lookup(fieldnames)
        recognized = set(lookup)
        identity_candidates = identity_columns_any(catalog, source)
        identity_present = [column for column in identity_candidates if column in recognized]
        missing_recommended = [column for column in SAMPLE_COLUMNS if column not in recognized]
        add_report(report, "info", source_id, str(source_path), "NA", "NA", "rows", f"Loaded {len(rows)} rows with {len(fieldnames)} columns.")
        if rows and not identity_present:
            add_report(
                report,
                "error",
                source_id,
                str(source_path),
                "NA",
                "NA",
                "identity_columns_any",
                "Source has data rows but no recognized identity column; add at least one of " + ";".join(identity_candidates) + ".",
            )
            continue
        if rows and missing_recommended:
            add_report(
                report,
                "warning",
                source_id,
                str(source_path),
                "NA",
                "NA",
                "missing_recommended_columns",
                "Missing recommended columns will be filled from source defaults or NA: " + ";".join(missing_recommended),
            )
        for row_number, raw in enumerate(rows, start=2):
            normalized = normalize_row(raw, lookup, source, row_number)
            genome_id = normalized["genome_id"]
            if genome_id in seen:
                add_report(report, "warning", source_id, str(source_path), str(row_number), genome_id, "genome_id", "Duplicate genome_id skipped; first occurrence retained.")
                continue
            seen.add(genome_id)
            samples.append(normalized)
    return samples, report


def main() -> int:
    args = parse_args()
    catalog_path = Path(args.catalog)
    try:
        catalog = load_yaml(catalog_path)
        samples, report = build_samples(catalog_path, catalog)
        write_tsv(Path(args.output_samples), SAMPLE_COLUMNS, samples)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        error_count = sum(1 for row in report if row.get("severity") == "error")
        print(f"Built {len(samples)} sample rows from source catalog with {error_count} errors.")
        return 1 if error_count else 0
    except (BuilderError, FileNotFoundError) as exc:
        report = [{"severity": "error", "source_id": "catalog", "path": str(catalog_path), "row_number": "NA", "genome_id": "NA", "field": "catalog", "message": str(exc)}]
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        write_tsv(Path(args.output_samples), SAMPLE_COLUMNS, [])
        print(f"Sample build failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
