#!/usr/bin/env python3
"""Import local public-source metadata exports into normalized source manifests."""

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

REPORT_COLUMNS = [
    "severity",
    "import_id",
    "input_path",
    "output_path",
    "row_number",
    "input_identifier",
    "field",
    "message",
]

COLUMN_ALIASES = {
    "record_type": ["record_type", "type", "entry_type"],
    "genome_id": ["genome_id", "genome", "id", "sample", "sample_id", "assembly", "assembly_id"],
    "accession": ["accession", "accessions", "public_accession", "nucleotide_accession", "genbank_accession", "refseq_accession", "sequence_accession", "accn", "id"],
    "source": ["source", "database", "source_database", "data_source"],
    "isolation_host": ["isolation_host", "isolation host", "host", "reported_host", "isolate_host"],
    "host_species": ["host_species", "host species", "species", "bacterial_species", "organism", "host_organism"],
    "host_strain": ["host_strain", "host strain", "strain", "isolate", "isolate_name"],
    "country": ["country", "location", "region", "geo_location", "geographic_location"],
    "year": ["year", "isolation_year", "collection_year", "publication_year", "date", "collection_date"],
    "phage_lifestyle": ["phage_lifestyle", "lifestyle", "predicted_lifestyle"],
    "genome_length": ["genome_length", "length", "length_bp", "genome_size", "genome_size_bp", "size", "sequence_length"],
    "gc_percent": ["gc_percent", "gc", "gc_content", "gc_percentage", "gc%"],
    "K_type": ["K_type", "k_type", "capsule_type", "k_locus", "K_locus"],
    "O_type": ["O_type", "o_type", "o_antigen", "o_locus", "O_locus"],
    "ST": ["ST", "st", "mlst", "sequence_type"],
    "AMR_markers": ["AMR_markers", "amr_markers", "amr_genes", "resistance_genes"],
    "virulence_markers": ["virulence_markers", "virulence_genes", "virulence_loci"],
    "raw_sequence_path": ["raw_sequence_path", "sequence_path", "fasta", "fasta_path", "genbank_path", "file", "filepath"],
    "notes": ["notes", "note", "comment", "comments", "description", "title", "definition"],
}

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

MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
PHAGE_TERMS = ("phage", "bacteriophage", "virus", "caudoviricetes", "uroviricota")
KLEBSIELLA_TERM = "klebsiella"


class ImportErrorConfig(Exception):
    """Raised for invalid import configuration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import local public metadata exports into source manifest TSVs.")
    parser.add_argument("--config", required=True, help="YAML import configuration.")
    parser.add_argument("--report-output", required=True, help="Output import report TSV.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ImportErrorConfig("PyYAML is required to read source import configuration.") from exc
    if not path.exists():
        raise ImportErrorConfig(f"Source import config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ImportErrorConfig("Source import config must be a YAML mapping.")
    return data


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def note_value(notes: str, key: str) -> str:
    match = re.search(rf"(?:^|;\s*){re.escape(key)}=([^;]+)", notes)
    return match.group(1).strip() if match else ""


def raw_value_by_alias(raw: dict[str, str], aliases: list[str]) -> str:
    lowered = {normalize_header(key): value for key, value in raw.items()}
    for alias in aliases:
        value = lowered.get(normalize_header(alias), "")
        if not is_missing(value):
            return value
    return ""


def bool_value(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = normalize(value).lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


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


def delimiter_for(path: Path, configured: str) -> str:
    value = configured.strip().lower()
    if value == "tab":
        return "\t"
    if value == "comma":
        return ","
    if value and value != "auto":
        return configured
    if path.suffix.lower() in {".csv"}:
        return ","
    return "\t"


def read_table(path: Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


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


def configured_default(spec: dict, column: str) -> str:
    key = f"{column}_default"
    if key in spec:
        return normalize(spec.get(key))
    if column == "source" and spec.get("source_label"):
        return normalize(spec.get("source_label"))
    return DEFAULTS[column]


def stable_id(record_type: str, accession: str, row_number: int, import_id: str) -> str:
    if not is_missing(accession):
        raw = f"{record_type}_{accession}"
    else:
        raw = f"{record_type}_{import_id}_{row_number}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")


def year_from(value: str) -> str:
    if is_missing(value):
        return "NA"
    match = re.search(r"(19|20)\d{2}", value)
    return match.group(0) if match else value


def gc_from(value: str) -> str:
    value = value.strip().rstrip("%")
    if is_missing(value):
        return "NA"
    try:
        number = float(value)
    except ValueError:
        return value
    if number <= 1:
        number *= 100
    return f"{number:.3f}".rstrip("0").rstrip(".")


def text_blob(raw: dict[str, str]) -> str:
    return " ".join(value.lower() for value in raw.values() if value)


def row_matches_filters(raw: dict[str, str], spec: dict) -> tuple[bool, str]:
    text = text_blob(raw)
    if bool_value(spec.get("require_klebsiella", False), False) and KLEBSIELLA_TERM not in text:
        return False, "skipped_non_klebsiella"
    if bool_value(spec.get("require_phage_keyword", False), False) and not any(term in text for term in PHAGE_TERMS):
        return False, "skipped_non_phage"
    include_regex = normalize(spec.get("include_regex"))
    if include_regex and re.search(include_regex, text, flags=re.IGNORECASE) is None:
        return False, "skipped_include_regex"
    exclude_regex = normalize(spec.get("exclude_regex"))
    if exclude_regex and re.search(exclude_regex, text, flags=re.IGNORECASE):
        return False, "skipped_exclude_regex"
    review_statuses = spec.get("required_note_review_statuses", [])
    if isinstance(review_statuses, str):
        allowed_review_statuses = {item.strip().lower() for item in review_statuses.split(",") if item.strip()}
    elif isinstance(review_statuses, list):
        allowed_review_statuses = {normalize(item).lower() for item in review_statuses if normalize(item)}
    else:
        raise ImportErrorConfig("required_note_review_statuses must be a list or comma-separated string when provided.")
    if allowed_review_statuses:
        notes = raw_value_by_alias(raw, ["notes", "note", "comment", "comments", "description"])
        review_status = note_value(notes, "review_status") or raw_value_by_alias(raw, ["review_status"])
        if review_status.lower() not in allowed_review_statuses:
            return False, "skipped_review_status"
    return True, "included"


def normalize_row(raw: dict[str, str], lookup: dict[str, str], spec: dict, row_number: int, import_id: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for column in SAMPLE_COLUMNS:
        source_column = lookup.get(column, "")
        value = raw.get(source_column, "") if source_column else ""
        if is_missing(value):
            value = configured_default(spec, column)
        output[column] = normalize(value)
    output["year"] = year_from(output["year"])
    output["gc_percent"] = gc_from(output["gc_percent"])
    if output["record_type"] != "host" and any(term in output["host_species"].lower() for term in PHAGE_TERMS):
        output["host_species"] = output["isolation_host"] if not is_missing(output["isolation_host"]) else "NA"
    if is_missing(output["genome_id"]):
        output["genome_id"] = stable_id(output["record_type"], output["accession"], row_number, import_id)
    if spec.get("notes"):
        note = normalize(spec.get("notes"))
        output["notes"] = note if is_missing(output["notes"]) else output["notes"] + "; " + note
    return output


def add_report(
    report: list[dict[str, str]],
    severity: str,
    import_id: str,
    input_path: str,
    output_path: str,
    row_number: str,
    input_identifier: str,
    field: str,
    message: str,
) -> None:
    report.append(
        {
            "severity": severity,
            "import_id": import_id,
            "input_path": input_path,
            "output_path": output_path,
            "row_number": row_number,
            "input_identifier": input_identifier or "NA",
            "field": field,
            "message": message,
        }
    )


def import_one(root: Path, spec: dict, index: int, report: list[dict[str, str]]) -> None:
    import_id = normalize(spec.get("import_id")) or f"import_{index}"
    input_text = normalize(spec.get("input_path"))
    output_text = normalize(spec.get("output_path"))
    enabled = bool_value(spec.get("enabled", False), False)
    if not enabled:
        add_report(report, "info", import_id, input_text, output_text, "NA", "NA", "enabled", "Import disabled; skipped.")
        return
    if is_missing(input_text) or is_missing(output_text):
        add_report(report, "error", import_id, input_text, output_text, "NA", "NA", "path", "Enabled import requires input_path and output_path.")
        return
    input_path = resolve(root, input_text)
    output_path = resolve(root, output_text)
    if not input_path.exists():
        add_report(report, "error", import_id, display_path(root, input_path), display_path(root, output_path), "NA", "NA", "input_path", "Input export does not exist.")
        return
    if output_path.exists() and not bool_value(spec.get("overwrite", True), True):
        add_report(report, "error", import_id, display_path(root, input_path), display_path(root, output_path), "NA", "NA", "overwrite", "Output exists and overwrite is false.")
        return

    delimiter = delimiter_for(input_path, normalize(spec.get("delimiter", "auto")))
    fieldnames, raw_rows = read_table(input_path, delimiter)
    lookup = header_lookup(fieldnames)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    skipped: dict[str, int] = {}
    for row_number, raw in enumerate(raw_rows, start=2):
        keep, reason = row_matches_filters(raw, spec)
        if not keep:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        normalized = normalize_row(raw, lookup, spec, row_number, import_id)
        input_identifier = normalized.get("accession") or normalized.get("genome_id") or f"row_{row_number}"
        if normalized["genome_id"] in seen:
            add_report(report, "warning", import_id, display_path(root, input_path), display_path(root, output_path), str(row_number), input_identifier, "genome_id", "Duplicate genome_id skipped; first occurrence retained.")
            continue
        seen.add(normalized["genome_id"])
        rows.append(normalized)

    write_tsv(output_path, SAMPLE_COLUMNS, rows)
    add_report(report, "info", import_id, display_path(root, input_path), display_path(root, output_path), "NA", "NA", "rows", f"Imported {len(rows)} rows from {len(raw_rows)} input rows.")
    for reason, count in sorted(skipped.items()):
        add_report(report, "info", import_id, display_path(root, input_path), display_path(root, output_path), "NA", "NA", reason, f"Skipped {count} rows.")
    missing_recommended = [column for column in SAMPLE_COLUMNS if column not in lookup]
    if rows and missing_recommended:
        add_report(report, "warning", import_id, display_path(root, input_path), display_path(root, output_path), "NA", "NA", "missing_recommended_columns", "Filled from defaults or NA: " + ";".join(missing_recommended))


def run_imports(config_path: Path, report_output: Path) -> tuple[int, int]:
    root = Path.cwd()
    config = load_yaml(config_path)
    imports = config.get("imports", [])
    if not isinstance(imports, list):
        raise ImportErrorConfig("source import config 'imports' must be a list")
    report: list[dict[str, str]] = []
    if not imports:
        add_report(report, "info", "config", display_path(root, config_path), "NA", "NA", "NA", "imports", "No imports configured.")
    for index, spec in enumerate(imports, start=1):
        if not isinstance(spec, dict):
            add_report(report, "error", f"import_{index}", display_path(root, config_path), "NA", "NA", "NA", "imports", "Import entry is not a mapping.")
            continue
        import_one(root, spec, index, report)
    write_tsv(report_output, REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row.get("severity") == "error")
    warnings = sum(1 for row in report if row.get("severity") == "warning")
    return errors, warnings


def main() -> int:
    args = parse_args()
    try:
        errors, warnings = run_imports(Path(args.config), Path(args.report_output))
        print(f"Source import complete: {errors} errors, {warnings} warnings.")
        return 1 if errors else 0
    except ImportErrorConfig as exc:
        report = [{"severity": "error", "import_id": "config", "input_path": args.config, "output_path": "NA", "row_number": "NA", "input_identifier": "NA", "field": "config", "message": str(exc)}]
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        print(f"Source import failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
