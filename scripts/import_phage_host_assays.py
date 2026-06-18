#!/usr/bin/env python3
"""Import reviewed phage-host assay source exports into canonical assay tables."""

from __future__ import annotations

import argparse
import csv
import re
import tempfile
from pathlib import Path
from typing import Iterable

from validate_phage_host_assays import (
    ASSAY_COLUMNS,
    ASSAY_TYPES,
    EVIDENCE_TIERS,
    NEGATIVE_RESULT_COLUMNS,
    OUTCOME_TIERS,
    RELATIONSHIP_COLUMNS,
    RESULT_VALUES,
)

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
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
TRUE_VALUES = {"true", "t", "yes", "y", "1", "positive", "+"}
FALSE_VALUES = {"false", "f", "no", "n", "0", "negative", "-"}
ASSAY_DEFAULTS = {
    "interaction_id": "",
    "phage_id": "",
    "host_id": "",
    "study_id": "",
    "panel_id": "NA",
    "assay_type": "unknown",
    "tested": "",
    "adsorption_result": "",
    "spot_result": "",
    "plaque_result": "",
    "productive_infection_result": "",
    "eop": "NA",
    "eop_reference_host": "NA",
    "growth_inhibition_result": "",
    "moi": "NA",
    "temperature_c": "NA",
    "medium": "NA",
    "replicate_count": "NA",
    "outcome_tier": "unknown",
    "evidence_tier": "unknown",
    "reference": "",
    "notes": "",
}
COLUMN_ALIASES = {
    "interaction_id": ["interaction_id", "interaction", "interaction_pair", "pair_id", "assay_id", "id"],
    "phage_id": ["phage_id", "phage", "phage_name", "phage_genome_id", "virus_id", "virus"],
    "host_id": ["host_id", "host", "host_name", "host_genome_id", "strain_id", "bacterium_id", "bacterial_strain"],
    "study_id": ["study_id", "study", "dataset", "source_study", "publication_id"],
    "panel_id": ["panel_id", "panel", "assay_panel", "screen_panel"],
    "assay_type": ["assay_type", "assay", "test_type", "method"],
    "tested": ["tested", "was_tested", "test_performed", "screened"],
    "adsorption_result": ["adsorption_result", "adsorption", "adsorption_outcome"],
    "spot_result": ["spot_result", "spot", "spot_test", "spot_test_result"],
    "plaque_result": ["plaque_result", "plaque", "plaque_assay", "plaque_result"],
    "productive_infection_result": ["productive_infection_result", "productive_infection", "replication_result", "propagation_result"],
    "eop": ["eop", "efficiency_of_plating", "relative_eop"],
    "eop_reference_host": ["eop_reference_host", "reference_host", "eop_reference"],
    "growth_inhibition_result": ["growth_inhibition_result", "growth_inhibition", "killing_result"],
    "moi": ["moi", "multiplicity_of_infection"],
    "temperature_c": ["temperature_c", "temperature", "temp_c"],
    "medium": ["medium", "media", "growth_medium"],
    "replicate_count": ["replicate_count", "replicates", "n_replicates"],
    "outcome_tier": ["outcome_tier", "outcome", "outcome_class"],
    "evidence_tier": ["evidence_tier", "evidence", "evidence_class"],
    "reference": ["reference", "source_reference", "citation", "doi", "pmid", "url"],
    "notes": ["notes", "note", "comment", "comments", "provenance"],
}


class AssayImportError(Exception):
    """Raised when assay import configuration is malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import reviewed phage-host assay exports into canonical TSVs.")
    parser.add_argument("--config", required=True, help="Assay import YAML configuration.")
    parser.add_argument("--assays-output", required=True, help="Canonical assay TSV output.")
    parser.add_argument("--relationships-output", required=True, help="Canonical relationship TSV output.")
    parser.add_argument("--report-output", required=True, help="Import report TSV output.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def bool_value(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = normalize(value).lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


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
    return "," if path.suffix.lower() == ".csv" else "\t"


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise AssayImportError("PyYAML is required to read assay import configuration.") from exc
    if not path.exists():
        raise AssayImportError(f"Assay import config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise AssayImportError("Assay import config must be a YAML mapping.")
    imports = data.get("imports", [])
    if not isinstance(imports, list):
        raise AssayImportError("Assay import config field 'imports' must be a list.")
    return data


def read_table(path: Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv_atomic(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        tmp_path = Path(handle.name)
        fieldnames = list(columns)
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})
    tmp_path.replace(path)


def add_report(
    rows: list[dict[str, str]],
    severity: str,
    import_id: str,
    input_path: str,
    output_path: str,
    row_number: str,
    input_identifier: str,
    field: str,
    message: str,
) -> None:
    rows.append(
        {
            "severity": severity,
            "import_id": import_id,
            "input_path": input_path,
            "output_path": output_path,
            "row_number": row_number,
            "input_identifier": input_identifier,
            "field": field,
            "message": message,
        }
    )


def configured_default(spec: dict, column: str) -> str:
    key = f"{column}_default"
    if key in spec:
        return normalize(spec.get(key))
    return ASSAY_DEFAULTS[column]


def explicit_column_map(spec: dict) -> dict[str, str]:
    mapping = spec.get("column_map", {}) or {}
    if not isinstance(mapping, dict):
        raise AssayImportError("Assay import column_map must be a mapping when provided.")
    return {normalize(key): normalize(value) for key, value in mapping.items() if normalize(key) and normalize(value)}


def header_lookup(fieldnames: list[str], spec: dict) -> dict[str, str]:
    by_normalized = {normalize_header(name): name for name in fieldnames}
    lookup: dict[str, str] = {}
    for canonical, source_column in explicit_column_map(spec).items():
        if canonical not in ASSAY_COLUMNS:
            raise AssayImportError(f"Unsupported assay column_map target: {canonical}")
        normalized_source = normalize_header(source_column)
        if normalized_source not in by_normalized:
            raise AssayImportError(f"column_map source column does not exist: {source_column}")
        lookup[canonical] = by_normalized[normalized_source]
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in lookup:
            continue
        for alias in aliases:
            normalized = normalize_header(alias)
            if normalized in by_normalized:
                lookup[canonical] = by_normalized[normalized]
                break
    return lookup


def normalize_bool(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return "true"
    if lowered in FALSE_VALUES:
        return "false"
    return value


def normalize_result(value: str, tested: str) -> str:
    lowered = value.strip().lower()
    if is_missing(value):
        return "not_tested" if tested == "false" else "not_measured"
    aliases = {
        "+": "positive",
        "pos": "positive",
        "yes": "positive",
        "1": "positive",
        "-": "negative",
        "neg": "negative",
        "no": "negative",
        "0": "negative",
        "na": "not_measured",
        "n/a": "not_measured",
        "not done": "not_measured",
    }
    return aliases.get(lowered, lowered)


def stable_interaction_id(row: dict[str, str], import_id: str, row_number: int) -> str:
    parts = [row.get("study_id", ""), row.get("panel_id", ""), row.get("phage_id", ""), row.get("host_id", ""), row.get("assay_type", ""), str(row_number)]
    raw = "_".join(part for part in parts if not is_missing(part)) or f"{import_id}_{row_number}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")


def normalize_row(raw: dict[str, str], lookup: dict[str, str], spec: dict, row_number: int, import_id: str) -> dict[str, str]:
    row: dict[str, str] = {}
    for column in ASSAY_COLUMNS:
        source_column = lookup.get(column, "")
        value = raw.get(source_column, "") if source_column else ""
        if is_missing(value):
            value = configured_default(spec, column)
        row[column] = normalize(value)

    row["tested"] = normalize_bool(row["tested"])
    for column in NEGATIVE_RESULT_COLUMNS:
        row[column] = normalize_result(row[column], row["tested"])
    row["assay_type"] = row["assay_type"].lower()
    row["outcome_tier"] = row["outcome_tier"].lower()
    row["evidence_tier"] = row["evidence_tier"].lower()
    if is_missing(row["interaction_id"]):
        row["interaction_id"] = stable_interaction_id(row, import_id, row_number)
    if row.get("notes"):
        row["notes"] = f"{row['notes']}; imported_from={import_id}"
    else:
        row["notes"] = f"imported_from={import_id}"
    return row


def validate_imported_row(row: dict[str, str], report: list[dict[str, str]], import_id: str, input_path: str, output_path: str, row_number: int) -> int:
    errors = 0
    entity = row.get("interaction_id", f"row{row_number}")
    required = ["interaction_id", "phage_id", "host_id", "study_id", "assay_type", "tested", "evidence_tier", "reference"]
    missing_required = [column for column in required if is_missing(row.get(column))]
    if missing_required:
        errors += 1
        add_report(report, "error", import_id, input_path, output_path, str(row_number), entity, ";".join(missing_required), "Populated assay row is missing required fields after import normalization.")
    if row.get("tested") not in {"true", "false"}:
        errors += 1
        add_report(report, "error", import_id, input_path, output_path, str(row_number), entity, "tested", f"Invalid tested value after normalization: {row.get('tested')}")
    if row.get("assay_type") not in ASSAY_TYPES:
        errors += 1
        add_report(report, "error", import_id, input_path, output_path, str(row_number), entity, "assay_type", f"Invalid assay_type: {row.get('assay_type')}")
    if row.get("outcome_tier") not in OUTCOME_TIERS:
        errors += 1
        add_report(report, "error", import_id, input_path, output_path, str(row_number), entity, "outcome_tier", f"Invalid outcome_tier: {row.get('outcome_tier')}")
    if row.get("evidence_tier") not in EVIDENCE_TIERS:
        errors += 1
        add_report(report, "error", import_id, input_path, output_path, str(row_number), entity, "evidence_tier", f"Invalid evidence_tier: {row.get('evidence_tier')}")
    for column in NEGATIVE_RESULT_COLUMNS:
        if row.get(column) not in RESULT_VALUES:
            errors += 1
            add_report(report, "error", import_id, input_path, output_path, str(row_number), entity, column, f"Invalid controlled result value: {row.get(column)}")
    return errors


def relationship_from_assay(row: dict[str, str]) -> dict[str, str]:
    return {
        "relationship_id": f"tested_{row['interaction_id']}",
        "phage_id": row.get("phage_id", ""),
        "host_id": row.get("host_id", ""),
        "relationship_type": "tested_assay_host",
        "relationship_status": "reviewed",
        "relationship_evidence": "curated_phage_host_assay_import",
        "source_reference": row.get("reference", ""),
        "confidence": "high" if row.get("evidence_tier") in {"curated_assay", "primary_data", "supplementary_matrix", "literature_table"} else "unknown",
        "notes": f"derived_from_interaction_id={row.get('interaction_id', '')}",
    }


def import_assays(config_path: Path, assays_output: Path, relationships_output: Path, root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], int]:
    config = load_yaml(config_path)
    reports: list[dict[str, str]] = []
    assay_rows: list[dict[str, str]] = []
    relationship_rows: list[dict[str, str]] = []
    errors = 0
    seen_interactions: dict[str, str] = {}

    output_label = display_path(root, assays_output)
    for index, spec in enumerate(config.get("imports", []), start=1):
        if not isinstance(spec, dict):
            errors += 1
            add_report(reports, "error", f"import_{index}", display_path(root, config_path), output_label, "NA", "NA", "imports", "Import entry is not a mapping.")
            continue
        import_id = normalize(spec.get("import_id")) or f"import_{index}"
        if not bool_value(spec.get("enabled"), False):
            add_report(reports, "info", import_id, normalize(spec.get("input_path", "NA")), output_label, "NA", "NA", "enabled", "Import disabled; skipped.")
            continue
        input_text = normalize(spec.get("input_path"))
        if is_missing(input_text):
            errors += 1
            add_report(reports, "error", import_id, display_path(root, config_path), output_label, "NA", "NA", "input_path", "Enabled import is missing input_path.")
            continue
        input_path = resolve(root, input_text)
        input_label = display_path(root, input_path)
        if input_path.resolve() in {assays_output.resolve(), relationships_output.resolve()}:
            errors += 1
            add_report(reports, "error", import_id, input_label, output_label, "NA", "NA", "path_collision", "Assay import input cannot be the same path as a canonical output.")
            continue
        if not input_path.exists():
            errors += 1
            add_report(reports, "error", import_id, input_label, output_label, "NA", "NA", "input_path", "Enabled assay import input does not exist.")
            continue
        try:
            fieldnames, raw_rows = read_table(input_path, delimiter_for(input_path, normalize(spec.get("delimiter", "auto"))))
            lookup = header_lookup(fieldnames, spec)
        except AssayImportError as exc:
            raise
        except Exception as exc:
            errors += 1
            add_report(reports, "error", import_id, input_label, output_label, "NA", "NA", "read_table", str(exc))
            continue
        add_report(reports, "info", import_id, input_label, output_label, "NA", "NA", "rows", f"Read {len(raw_rows)} row(s).")
        for row_number, raw in enumerate(raw_rows, start=2):
            if all(is_missing(value) for value in raw.values()):
                continue
            row = normalize_row(raw, lookup, spec, row_number, import_id)
            errors += validate_imported_row(row, reports, import_id, input_label, output_label, row_number)
            interaction_id = row.get("interaction_id", "")
            if interaction_id in seen_interactions:
                errors += 1
                add_report(reports, "error", import_id, input_label, output_label, str(row_number), interaction_id, "interaction_id", f"Duplicate interaction_id already imported from {seen_interactions[interaction_id]}.")
            else:
                seen_interactions[interaction_id] = import_id
            assay_rows.append(row)
            if bool_value(spec.get("derive_relationships"), True):
                relationship_rows.append(relationship_from_assay(row))

    if errors:
        add_report(reports, "error", "assay_imports", display_path(root, config_path), output_label, "NA", "NA", "import_status", "Assay import failed; canonical assay outputs were not rewritten.")
    else:
        add_report(reports, "info", "assay_imports", display_path(root, config_path), output_label, "NA", "NA", "import_status", f"Prepared {len(assay_rows)} assay row(s) and {len(relationship_rows)} relationship row(s).")
    return assay_rows, relationship_rows, reports, errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    assays_output = resolve(root, args.assays_output)
    relationships_output = resolve(root, args.relationships_output)
    report_output = resolve(root, args.report_output)
    try:
        if assays_output.resolve() == relationships_output.resolve():
            raise AssayImportError("assays-output and relationships-output must be distinct paths.")
        if report_output.resolve() in {assays_output.resolve(), relationships_output.resolve()}:
            raise AssayImportError("report-output must be distinct from canonical assay outputs.")
        assay_rows, relationship_rows, reports, errors = import_assays(resolve(root, args.config), assays_output, relationships_output, root)
    except AssayImportError as exc:
        reports = [{"severity": "error", "import_id": "assay_imports", "input_path": args.config, "output_path": args.assays_output, "row_number": "NA", "input_identifier": "NA", "field": "config", "message": str(exc)}]
        errors = 1
        assay_rows = []
        relationship_rows = []
    write_tsv_atomic(report_output, REPORT_COLUMNS, reports)
    if not errors:
        write_tsv_atomic(assays_output, ASSAY_COLUMNS, assay_rows)
        write_tsv_atomic(relationships_output, RELATIONSHIP_COLUMNS, relationship_rows)
    print(f"Assay import complete: assay_rows={len(assay_rows)}; relationship_rows={len(relationship_rows)}; errors={errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
