#!/usr/bin/env python3
"""Normalize reviewed phage-host interaction matrices into assay source exports."""

from __future__ import annotations

import argparse
import csv
import re
import tempfile
from pathlib import Path
from typing import Iterable

from validate_phage_host_assays import ASSAY_COLUMNS


REPORT_COLUMNS = [
    "severity",
    "source_id",
    "input_path",
    "output_path",
    "row_number",
    "host_source_id",
    "phage_source_id",
    "field",
    "message",
]
MAPPING_COLUMNS = ["source_id", "canonical_id", "review_status", "notes"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
TRUE_DEFAULTS = {"1", "1.0", "true", "positive", "pos", "+"}
FALSE_DEFAULTS = {"0", "0.0", "false", "negative", "neg", "-"}
SKIP_DEFAULTS = {"", "NA", "N/A", "na", "n/a", "not_tested", "untested", "nan"}
REVIEWED_STATUSES = {"reviewed", "accepted", "approved"}


class MatrixNormalizationError(Exception):
    """Raised when matrix normalization cannot proceed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize phage-host assay matrices into canonical source-export rows.")
    parser.add_argument("--config", required=True, help="Assay matrix source YAML configuration.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative paths.")
    parser.add_argument("--only-source", default="", help="Optional source_id to process from the config.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm_lower(value: object) -> str:
    return normalize(value).lower()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def sanitize_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def bool_value(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = norm_lower(value)
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def list_value(value: object, default: set[str]) -> set[str]:
    if value is None:
        return set(default)
    if isinstance(value, list):
        return {normalize(item) for item in value}
    text = normalize(value)
    if not text:
        return set(default)
    return {item.strip() for item in text.split(",")}


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
    except ImportError as exc:  # pragma: no cover - environment issue
        raise MatrixNormalizationError("PyYAML is required to read assay matrix configuration.") from exc
    if not path.exists():
        raise MatrixNormalizationError(f"Assay matrix config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise MatrixNormalizationError("Assay matrix config must be a YAML mapping.")
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise MatrixNormalizationError("Assay matrix config field 'sources' must be a list.")
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
    source_id: str,
    input_path: str,
    output_path: str,
    row_number: str,
    host_source_id: str,
    phage_source_id: str,
    field: str,
    message: str,
) -> None:
    rows.append(
        {
            "severity": severity,
            "source_id": source_id,
            "input_path": input_path,
            "output_path": output_path,
            "row_number": row_number,
            "host_source_id": host_source_id,
            "phage_source_id": phage_source_id,
            "field": field,
            "message": message,
        }
    )


def load_mapping(path: Path, entity_type: str) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return {}, [f"{entity_type} mapping file is missing: {path}"]
    fieldnames, rows = read_table(path, "\t")
    missing = [column for column in ("source_id", "canonical_id") if column not in fieldnames]
    if missing:
        raise MatrixNormalizationError(f"{entity_type} mapping file is missing required columns: {';'.join(missing)}")
    mapping: dict[str, str] = {}
    for index, row in enumerate(rows, start=2):
        source_id = normalize(row.get("source_id"))
        canonical_id = normalize(row.get("canonical_id"))
        review_status = norm_lower(row.get("review_status") or "reviewed")
        if is_missing(source_id) and is_missing(canonical_id):
            continue
        if is_missing(source_id):
            raise MatrixNormalizationError(f"{entity_type} mapping row {index} must include source_id.")
        if review_status not in REVIEWED_STATUSES:
            warnings.append(f"{entity_type} mapping row {index} has non-reviewed status {review_status}; mapping skipped for {source_id}.")
            continue
        if is_missing(canonical_id):
            raise MatrixNormalizationError(f"{entity_type} mapping row {index} is reviewed but missing canonical_id.")
        previous = mapping.get(source_id)
        if previous and previous != canonical_id:
            raise MatrixNormalizationError(f"{entity_type} source_id maps to multiple canonical IDs: {source_id}")
        mapping[source_id] = canonical_id
    return mapping, warnings


def canonical_id(
    source_id: str,
    mapping: dict[str, str],
    use_source_ids_as_canonical: bool,
) -> tuple[str, str]:
    if source_id in mapping:
        return mapping[source_id], "mapped"
    if use_source_ids_as_canonical:
        return source_id, "source_id"
    return "", "unresolved"


def assay_row(
    source_id: str,
    row_number: int,
    host_source_id: str,
    host_id: str,
    phage_source_id: str,
    phage_id: str,
    result: str,
    spec: dict,
    matrix_value: str,
) -> dict[str, str]:
    study_id = normalize(spec.get("study_id")) or source_id
    panel_id = normalize(spec.get("panel_id")) or "matrix_panel"
    assay_type = norm_lower(spec.get("assay_type")) or "spot"
    reference = normalize(spec.get("reference")) or "source_reference_pending"
    evidence_tier = norm_lower(spec.get("evidence_tier")) or "supplementary_matrix"
    positive_tier = norm_lower(spec.get("positive_outcome_tier")) or "initial_interaction"
    negative_tier = norm_lower(spec.get("negative_outcome_tier")) or "tested_negative"
    interaction_id = sanitize_id(f"{study_id}_{panel_id}_{phage_id}_{host_id}_{assay_type}")
    note_parts = [
        f"source_matrix={source_id}",
        f"source_host_id={host_source_id}",
        f"source_phage_id={phage_source_id}",
        f"matrix_value={matrix_value}",
        "blank_cells_treated_as_untested",
    ]
    extra_notes = normalize(spec.get("notes"))
    if extra_notes:
        note_parts.append(extra_notes)
    return {
        "interaction_id": interaction_id,
        "phage_id": phage_id,
        "host_id": host_id,
        "study_id": study_id,
        "panel_id": panel_id,
        "assay_type": assay_type,
        "tested": "true",
        "adsorption_result": "not_measured",
        "spot_result": result,
        "plaque_result": "not_measured",
        "productive_infection_result": "not_measured",
        "eop": "NA",
        "eop_reference_host": "NA",
        "growth_inhibition_result": "not_measured",
        "moi": "NA",
        "temperature_c": "NA",
        "medium": "NA",
        "replicate_count": "NA",
        "outcome_tier": positive_tier if result == "positive" else negative_tier,
        "evidence_tier": evidence_tier,
        "reference": reference,
        "notes": "; ".join(note_parts),
    }


def validate_paths(root: Path, source_id: str, matrix_path: Path, output_path: Path, report_path: Path, map_paths: list[Path]) -> None:
    resolved = {
        "matrix_path": matrix_path.resolve(),
        "output_path": output_path.resolve(),
        "report_output": report_path.resolve(),
    }
    for index, map_path in enumerate(map_paths, start=1):
        resolved[f"mapping_{index}"] = map_path.resolve()
    seen: dict[Path, str] = {}
    for label, path in resolved.items():
        if path in seen:
            raise MatrixNormalizationError(f"{source_id} path collision: {label} matches {seen[path]}.")
        seen[path] = label
    try:
        output_path.relative_to(root)
        report_path.relative_to(root)
    except ValueError as exc:
        raise MatrixNormalizationError(f"{source_id} outputs must be inside the repository root.") from exc


def normalize_source(spec: dict, root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], Path, Path, int]:
    source_id = normalize(spec.get("source_id")) or "assay_matrix_source"
    matrix_text = normalize(spec.get("matrix_path"))
    output_text = normalize(spec.get("output_path"))
    report_text = normalize(spec.get("report_output"))
    if is_missing(matrix_text) or is_missing(output_text) or is_missing(report_text):
        raise MatrixNormalizationError(f"{source_id} must define matrix_path, output_path, and report_output.")
    matrix_path = resolve(root, matrix_text)
    output_path = resolve(root, output_text)
    report_output = resolve(root, report_text)
    phage_map_text = normalize(spec.get("phage_id_map", ""))
    host_map_text = normalize(spec.get("host_id_map", ""))
    phage_map_path = resolve(root, phage_map_text) if phage_map_text else None
    host_map_path = resolve(root, host_map_text) if host_map_text else None
    reports: list[dict[str, str]] = []
    assay_rows: list[dict[str, str]] = []
    errors = 0

    if not matrix_path.exists():
        raise MatrixNormalizationError(f"{source_id} matrix_path does not exist: {matrix_path}")
    map_paths = [path for path in (phage_map_path, host_map_path) if path is not None]
    validate_paths(root, source_id, matrix_path, output_path, report_output, map_paths)

    use_source_ids_as_canonical = bool_value(spec.get("use_source_ids_as_canonical"), False)
    fail_on_unresolved = bool_value(spec.get("fail_on_unresolved"), False)
    phage_map, phage_warnings = load_mapping(phage_map_path, "phage") if phage_map_path is not None else ({}, ["phage_id_map not configured."])
    host_map, host_warnings = load_mapping(host_map_path, "host") if host_map_path is not None else ({}, ["host_id_map not configured."])
    input_label = display_path(root, matrix_path)
    output_label = display_path(root, output_path)
    for warning in phage_warnings + host_warnings:
        add_report(reports, "warning", source_id, input_label, output_label, "NA", "NA", "NA", "mapping", warning)

    fieldnames, rows = read_table(matrix_path, delimiter_for(matrix_path, normalize(spec.get("delimiter", "auto"))))
    if not fieldnames:
        raise MatrixNormalizationError(f"{source_id} matrix has no header.")
    host_column = normalize(spec.get("host_id_column"))
    if not host_column or host_column == "auto_first_column":
        host_column = fieldnames[0]
    if host_column not in fieldnames:
        raise MatrixNormalizationError(f"{source_id} host_id_column does not exist in matrix: {host_column}")
    phage_columns = [column for column in fieldnames if column != host_column and not is_missing(column)]
    if not phage_columns:
        raise MatrixNormalizationError(f"{source_id} matrix has no phage columns.")

    positive_values = {value.lower() for value in list_value(spec.get("positive_values"), TRUE_DEFAULTS)}
    negative_values = {value.lower() for value in list_value(spec.get("negative_values"), FALSE_DEFAULTS)}
    skip_values = {value.lower() for value in list_value(spec.get("skip_values"), SKIP_DEFAULTS)}
    seen_interactions: dict[str, int] = {}
    total_cells = 0
    tested_cells = 0
    skipped_blank = 0
    unresolved = 0
    positives = 0
    negatives = 0

    for row_number, matrix_row in enumerate(rows, start=2):
        host_source_id = normalize(matrix_row.get(host_column))
        if is_missing(host_source_id):
            add_report(reports, "warning", source_id, input_label, output_label, str(row_number), "NA", "NA", "host_id", "Matrix row has no host identifier; row skipped.")
            continue
        host_id, host_status = canonical_id(host_source_id, host_map, use_source_ids_as_canonical)
        for phage_source_id in phage_columns:
            total_cells += 1
            value = normalize(matrix_row.get(phage_source_id))
            lowered = value.lower()
            if lowered in skip_values:
                skipped_blank += 1
                continue
            if lowered in positive_values:
                result = "positive"
                positives += 1
            elif lowered in negative_values:
                result = "negative"
                negatives += 1
            else:
                errors += 1
                add_report(reports, "error", source_id, input_label, output_label, str(row_number), host_source_id, phage_source_id, "matrix_value", f"Unsupported matrix value: {value}")
                continue
            tested_cells += 1
            phage_id, phage_status = canonical_id(phage_source_id, phage_map, use_source_ids_as_canonical)
            if not host_id or not phage_id:
                unresolved += 1
                severity = "error" if fail_on_unresolved else "warning"
                if fail_on_unresolved:
                    errors += 1
                add_report(
                    reports,
                    severity,
                    source_id,
                    input_label,
                    output_label,
                    str(row_number),
                    host_source_id,
                    phage_source_id,
                    "entity_mapping",
                    f"Skipped tested cell because host_status={host_status}; phage_status={phage_status}.",
                )
                continue
            row = assay_row(source_id, row_number, host_source_id, host_id, phage_source_id, phage_id, result, spec, value)
            interaction_id = row["interaction_id"]
            if interaction_id in seen_interactions:
                errors += 1
                add_report(reports, "error", source_id, input_label, output_label, str(row_number), host_source_id, phage_source_id, "interaction_id", f"Duplicate normalized interaction_id also appears on row {seen_interactions[interaction_id]}.")
                continue
            seen_interactions[interaction_id] = row_number
            assay_rows.append(row)

    add_report(
        reports,
        "info",
        source_id,
        input_label,
        output_label,
        "NA",
        "NA",
        "NA",
        "summary",
        f"matrix_rows={len(rows)}; phage_columns={len(phage_columns)}; cells={total_cells}; tested_cells={tested_cells}; positives={positives}; negatives={negatives}; skipped_blank={skipped_blank}; unresolved_tested_cells={unresolved}; emitted_rows={len(assay_rows)}; errors={errors}",
    )
    if not assay_rows:
        add_report(reports, "warning", source_id, input_label, output_label, "NA", "NA", "NA", "emitted_rows", "No assay rows were emitted. Check entity mappings before enabling this source in the main assay import.")
    return assay_rows, reports, output_path, report_output, errors


def run(config_path: Path, root: Path, only_source: str = "") -> int:
    config = load_yaml(config_path)
    all_reports: dict[Path, list[dict[str, str]]] = {}
    output_plans: list[tuple[Path, list[dict[str, str]]]] = []
    errors = 0
    processed = 0
    for index, spec in enumerate(config.get("sources", []), start=1):
        if not isinstance(spec, dict):
            errors += 1
            continue
        source_id = normalize(spec.get("source_id")) or f"source_{index}"
        if only_source and source_id != only_source:
            continue
        if not bool_value(spec.get("enabled"), False):
            continue
        processed += 1
        try:
            assay_rows, reports, output_path, report_path, source_errors = normalize_source(spec, root)
        except MatrixNormalizationError as exc:
            report_path = resolve(root, normalize(spec.get("report_output", "results/qc/assay_matrix_normalization_report.tsv")))
            output_path = resolve(root, normalize(spec.get("output_path", "data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv")))
            reports = [
                {
                    "severity": "error",
                    "source_id": source_id,
                    "input_path": normalize(spec.get("matrix_path", "NA")),
                    "output_path": display_path(root, output_path),
                    "row_number": "NA",
                    "host_source_id": "NA",
                    "phage_source_id": "NA",
                    "field": "config",
                    "message": str(exc),
                }
            ]
            source_errors = 1
            assay_rows = []
        all_reports.setdefault(report_path, []).extend(reports)
        errors += source_errors
        if not source_errors:
            output_plans.append((output_path, assay_rows))

    if only_source and processed == 0:
        raise MatrixNormalizationError(f"Requested --only-source was not found or enabled: {only_source}")
    for report_path, reports in all_reports.items():
        write_tsv_atomic(report_path, REPORT_COLUMNS, reports)
    if not errors:
        for output_path, assay_rows in output_plans:
            write_tsv_atomic(output_path, ASSAY_COLUMNS, assay_rows)
    print(f"Assay matrix normalization complete: sources={processed}; output_plans={len(output_plans)}; errors={errors}.")
    return 1 if errors else 0


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        return run(resolve(root, args.config), root, args.only_source)
    except MatrixNormalizationError as exc:
        print(f"Assay matrix normalization failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
