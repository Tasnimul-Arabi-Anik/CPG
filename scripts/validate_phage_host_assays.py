#!/usr/bin/env python3
"""Validate curated phage-host assay and relationship tables."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


ASSAY_COLUMNS = [
    "interaction_id",
    "phage_id",
    "host_id",
    "study_id",
    "panel_id",
    "assay_type",
    "tested",
    "adsorption_result",
    "spot_result",
    "plaque_result",
    "productive_infection_result",
    "eop",
    "eop_reference_host",
    "growth_inhibition_result",
    "moi",
    "temperature_c",
    "medium",
    "replicate_count",
    "outcome_tier",
    "evidence_tier",
    "reference",
    "notes",
]
RELATIONSHIP_COLUMNS = [
    "relationship_id",
    "phage_id",
    "host_id",
    "relationship_type",
    "relationship_status",
    "relationship_evidence",
    "source_reference",
    "confidence",
    "notes",
]
VALIDATION_COLUMNS = [
    "scope",
    "row_number",
    "entity_id",
    "check_id",
    "severity",
    "status",
    "blocking_issue",
    "message",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
TRUE_VALUES = {"true", "t", "yes", "y", "1"}
FALSE_VALUES = {"false", "f", "no", "n", "0"}
RESULT_VALUES = {"positive", "negative", "inconclusive", "not_measured", "not_tested", "mixed", "unknown"}
NEGATIVE_RESULT_COLUMNS = [
    "adsorption_result",
    "spot_result",
    "plaque_result",
    "productive_infection_result",
    "growth_inhibition_result",
]
ASSAY_TYPES = {
    "adsorption",
    "spot",
    "plaque",
    "eop",
    "growth_inhibition",
    "productive_infection",
    "kill_curve",
    "mixed_panel",
    "other",
}
OUTCOME_TIERS = {
    "initial_interaction",
    "productive_infection_confirmed",
    "productive_infection",
    "tested_negative",
    "no_interaction",
    "mixed",
    "not_tested",
    "unknown",
}
EVIDENCE_TIERS = {
    "curated_assay",
    "supplementary_matrix",
    "literature_table",
    "primary_data",
    "metadata_only",
    "unknown",
}
RELATIONSHIP_TYPES = {
    "isolation_host",
    "reported_host",
    "prophage_resident_host",
    "predicted_host",
    "tested_assay_host",
}
RELATIONSHIP_STATUSES = {"reviewed", "inferred", "predicted", "unresolved", "deprecated", "unknown"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate phage-host assay and relationship TSVs.")
    parser.add_argument("--assays", default="data/metadata/phage_host_assays.tsv", help="Curated phage-host assay TSV.")
    parser.add_argument(
        "--relationships",
        default="data/metadata/phage_host_relationships.tsv",
        help="Curated phage-host relationship TSV.",
    )
    parser.add_argument("--phage-manifest", default="results/qc/phage_genome_manifest.tsv", help="Canonical phage manifest TSV.")
    parser.add_argument("--host-metadata", default="results/host_features/host_metadata.tsv", help="Canonical host metadata TSV.")
    parser.add_argument("--assay-validation-output", required=True, help="Output assay validation TSV.")
    parser.add_argument("--relationship-validation-output", required=True, help="Output relationship validation TSV.")
    parser.add_argument("--report-output", required=True, help="Output summary report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm_lower(value: object) -> str:
    return normalize(value).lower()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def add_issue(
    rows: list[dict[str, str]],
    scope: str,
    row_number: str,
    entity_id: str,
    check_id: str,
    severity: str,
    status: str,
    blocking: bool,
    message: str,
) -> None:
    rows.append(
        {
            "scope": scope,
            "row_number": row_number,
            "entity_id": entity_id,
            "check_id": check_id,
            "severity": severity,
            "status": status,
            "blocking_issue": "true" if blocking else "false",
            "message": message,
        }
    )


def add_report(rows: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    rows.append({"severity": severity, "item": item, "message": message})


def parse_bool(value: str) -> bool | None:
    lowered = norm_lower(value)
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    return None


def normalize_result(value: str) -> str:
    lowered = norm_lower(value)
    if is_missing(value):
        return ""
    if lowered in RESULT_VALUES:
        return lowered
    return "__invalid__"


def parse_float(value: str) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def row_has_content(row: dict[str, str]) -> bool:
    return any(not is_missing(value) for value in row.values())


def load_phage_ids(path: Path) -> tuple[set[str], bool]:
    if not path.exists():
        return set(), False
    _, rows = read_tsv(path)
    ids = set()
    for row in rows:
        record_type = norm_lower(row.get("record_type"))
        genome_id = normalize(row.get("genome_id") or row.get("phage_genome_id"))
        if genome_id and (not record_type or record_type in {"phage", "cultured_phage", "prophage", "viral_contig"}):
            ids.add(genome_id)
    return ids, True


def load_host_ids(path: Path, manifest_path: Path) -> tuple[set[str], bool]:
    ids = set()
    exists = False
    if path.exists():
        exists = True
        _, rows = read_tsv(path)
        for row in rows:
            host_id = normalize(row.get("host_genome_id") or row.get("host_id") or row.get("genome_id"))
            if host_id:
                ids.add(host_id)
    if manifest_path.exists():
        exists = True
        _, rows = read_tsv(manifest_path)
        for row in rows:
            if norm_lower(row.get("record_type")) in {"host_genome", "host"}:
                genome_id = normalize(row.get("genome_id") or row.get("host_genome_id"))
                if genome_id:
                    ids.add(genome_id)
    return ids, exists


def missing_columns(fieldnames: list[str], required: list[str]) -> list[str]:
    return [column for column in required if column not in fieldnames]


def has_positive_eop(row: dict[str, str]) -> bool:
    value = parse_float(row.get("eop", ""))
    return value is not None and value > 0


def validate_assays(path: Path, phage_ids: set[str], host_ids: set[str], phage_reference_exists: bool, host_reference_exists: bool) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not path.exists():
        add_issue(issues, "assay", "NA", path.as_posix(), "file_exists", "error", "fail", True, "Assay table is missing.")
        return issues

    fieldnames, rows = read_tsv(path)
    missing = missing_columns(fieldnames, ASSAY_COLUMNS)
    if missing:
        add_issue(
            issues,
            "assay",
            "1",
            path.as_posix(),
            "required_columns",
            "error",
            "fail",
            True,
            f"Assay table is missing required columns: {';'.join(missing)}",
        )
        return issues

    populated_rows = [(index, row) for index, row in enumerate(rows, start=2) if row_has_content(row)]
    if not populated_rows:
        add_issue(
            issues,
            "assay",
            "NA",
            path.as_posix(),
            "row_count",
            "warning",
            "schema_only",
            False,
            "Header-only assay table is valid for scaffolding but does not support host-range modeling.",
        )
        return issues

    interaction_seen: dict[str, int] = {}
    assay_seen: dict[tuple[str, str, str, str, str], int] = {}
    for index, row in populated_rows:
        interaction_id = normalize(row.get("interaction_id"))
        entity = interaction_id or f"row{index}"
        required = ["interaction_id", "phage_id", "host_id", "study_id", "assay_type", "tested", "evidence_tier", "reference"]
        missing_required = [column for column in required if is_missing(row.get(column))]
        if missing_required:
            add_issue(
                issues,
                "assay",
                str(index),
                entity,
                "required_populated_fields",
                "error",
                "fail",
                True,
                f"Populated assay row is missing required fields: {';'.join(missing_required)}",
            )

        phage_id = normalize(row.get("phage_id"))
        host_id = normalize(row.get("host_id"))
        if phage_id and (not phage_reference_exists or phage_id not in phage_ids):
            add_issue(issues, "assay", str(index), entity, "phage_id_resolves", "error", "fail", True, f"Unknown phage_id: {phage_id}")
        if host_id and (not host_reference_exists or host_id not in host_ids):
            add_issue(issues, "assay", str(index), entity, "host_id_resolves", "error", "fail", True, f"Unknown host_id: {host_id}")

        if interaction_id:
            if interaction_id in interaction_seen:
                add_issue(
                    issues,
                    "assay",
                    str(index),
                    entity,
                    "duplicate_interaction_id",
                    "error",
                    "fail",
                    True,
                    f"Duplicate interaction_id also appears on row {interaction_seen[interaction_id]}.",
                )
            interaction_seen[interaction_id] = index

        duplicate_key = (
            phage_id,
            host_id,
            normalize(row.get("study_id")),
            normalize(row.get("panel_id")),
            norm_lower(row.get("assay_type")),
        )
        if all(duplicate_key):
            if duplicate_key in assay_seen:
                add_issue(
                    issues,
                    "assay",
                    str(index),
                    entity,
                    "duplicate_study_panel_assay",
                    "error",
                    "fail",
                    True,
                    f"Duplicate phage-host-study-panel-assay record also appears on row {assay_seen[duplicate_key]}.",
                )
            assay_seen[duplicate_key] = index

        tested_text = normalize(row.get("tested"))
        tested = parse_bool(tested_text)
        if not is_missing(tested_text) and tested is None:
            add_issue(issues, "assay", str(index), entity, "tested_boolean", "error", "fail", True, f"Invalid tested value: {tested_text}")

        assay_type = norm_lower(row.get("assay_type"))
        if assay_type and assay_type not in ASSAY_TYPES:
            add_issue(issues, "assay", str(index), entity, "assay_type_controlled", "error", "fail", True, f"Invalid assay_type: {assay_type}")

        outcome_tier = norm_lower(row.get("outcome_tier"))
        if outcome_tier and outcome_tier not in OUTCOME_TIERS:
            add_issue(issues, "assay", str(index), entity, "outcome_tier_controlled", "error", "fail", True, f"Invalid outcome_tier: {outcome_tier}")

        evidence_tier = norm_lower(row.get("evidence_tier"))
        if evidence_tier and evidence_tier not in EVIDENCE_TIERS:
            add_issue(issues, "assay", str(index), entity, "evidence_tier_controlled", "error", "fail", True, f"Invalid evidence_tier: {evidence_tier}")

        results: dict[str, str] = {}
        for column in NEGATIVE_RESULT_COLUMNS:
            result = normalize_result(row.get(column, ""))
            results[column] = result
            if result == "__invalid__":
                add_issue(issues, "assay", str(index), entity, f"{column}_controlled", "error", "fail", True, f"Invalid {column}: {row.get(column)}")
                continue
            if result in {"positive", "negative"} and tested is False:
                add_issue(
                    issues,
                    "assay",
                    str(index),
                    entity,
                    "untested_result_contradiction",
                    "error",
                    "fail",
                    True,
                    f"{column}={result} cannot be recorded when tested=false.",
                )
            if result == "negative" and tested is not True:
                add_issue(
                    issues,
                    "assay",
                    str(index),
                    entity,
                    "negative_requires_tested_true",
                    "error",
                    "fail",
                    True,
                    f"{column}=negative requires tested=true.",
                )

        if tested is False and outcome_tier == "tested_negative":
            add_issue(
                issues,
                "assay",
                str(index),
                entity,
                "untested_not_negative",
                "error",
                "fail",
                True,
                "tested=false cannot be paired with outcome_tier=tested_negative.",
            )

        eop = parse_float(row.get("eop", ""))
        if not is_missing(row.get("eop")) and (eop is None or eop < 0):
            add_issue(issues, "assay", str(index), entity, "eop_nonnegative", "error", "fail", True, f"EOP must be numeric and non-negative: {row.get('eop')}")
        if eop is not None and is_missing(row.get("eop_reference_host")):
            add_issue(issues, "assay", str(index), entity, "eop_reference_host", "warning", "warn", False, "EOP is populated but eop_reference_host is missing.")

        moi = parse_float(row.get("moi", ""))
        if not is_missing(row.get("moi")) and (moi is None or moi < 0):
            add_issue(issues, "assay", str(index), entity, "moi_nonnegative", "error", "fail", True, f"MOI must be numeric and non-negative: {row.get('moi')}")

        temperature = parse_float(row.get("temperature_c", ""))
        if not is_missing(row.get("temperature_c")) and temperature is None:
            add_issue(issues, "assay", str(index), entity, "temperature_numeric", "error", "fail", True, f"temperature_c must be numeric: {row.get('temperature_c')}")

        replicate_count = parse_int(row.get("replicate_count", ""))
        if not is_missing(row.get("replicate_count")) and (replicate_count is None or replicate_count <= 0):
            add_issue(issues, "assay", str(index), entity, "replicate_count_positive", "error", "fail", True, f"replicate_count must be a positive integer: {row.get('replicate_count')}")

        productive_positive = results.get("productive_infection_result") == "positive"
        direct_productive_assay = assay_type == "productive_infection" or outcome_tier == "productive_infection_confirmed"
        productive_supported = results.get("plaque_result") == "positive" or has_positive_eop(row) or direct_productive_assay
        if productive_positive and not productive_supported:
            add_issue(
                issues,
                "assay",
                str(index),
                entity,
                "productive_infection_not_spot_only",
                "error",
                "fail",
                True,
                "Productive infection cannot be claimed from spot clearing alone; provide plaque, EOP, or direct productive-infection evidence.",
            )

    if not any(issue["blocking_issue"] == "true" for issue in issues):
        add_issue(issues, "assay", "NA", path.as_posix(), "assay_validation_status", "info", "pass", False, f"Validated populated assay rows: {len(populated_rows)}.")
    return issues


def validate_relationships(path: Path, phage_ids: set[str], host_ids: set[str], phage_reference_exists: bool, host_reference_exists: bool) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not path.exists():
        add_issue(issues, "relationship", "NA", path.as_posix(), "file_exists", "error", "fail", True, "Relationship table is missing.")
        return issues

    fieldnames, rows = read_tsv(path)
    missing = missing_columns(fieldnames, RELATIONSHIP_COLUMNS)
    if missing:
        add_issue(
            issues,
            "relationship",
            "1",
            path.as_posix(),
            "required_columns",
            "error",
            "fail",
            True,
            f"Relationship table is missing required columns: {';'.join(missing)}",
        )
        return issues

    populated_rows = [(index, row) for index, row in enumerate(rows, start=2) if row_has_content(row)]
    if not populated_rows:
        add_issue(
            issues,
            "relationship",
            "NA",
            path.as_posix(),
            "row_count",
            "warning",
            "schema_only",
            False,
            "Header-only relationship table is valid for scaffolding but does not support biological linkage claims.",
        )
        return issues

    relationship_seen: dict[str, int] = {}
    key_seen: dict[tuple[str, str, str, str], int] = {}
    for index, row in populated_rows:
        relationship_id = normalize(row.get("relationship_id"))
        entity = relationship_id or f"row{index}"
        required = ["relationship_id", "phage_id", "host_id", "relationship_type", "relationship_status", "relationship_evidence", "source_reference"]
        missing_required = [column for column in required if is_missing(row.get(column))]
        if missing_required:
            add_issue(
                issues,
                "relationship",
                str(index),
                entity,
                "required_populated_fields",
                "error",
                "fail",
                True,
                f"Populated relationship row is missing required fields: {';'.join(missing_required)}",
            )

        phage_id = normalize(row.get("phage_id"))
        host_id = normalize(row.get("host_id"))
        if phage_id and (not phage_reference_exists or phage_id not in phage_ids):
            add_issue(issues, "relationship", str(index), entity, "phage_id_resolves", "error", "fail", True, f"Unknown phage_id: {phage_id}")
        if host_id and (not host_reference_exists or host_id not in host_ids):
            add_issue(issues, "relationship", str(index), entity, "host_id_resolves", "error", "fail", True, f"Unknown host_id: {host_id}")

        relationship_type = norm_lower(row.get("relationship_type"))
        if relationship_type and relationship_type not in RELATIONSHIP_TYPES:
            add_issue(issues, "relationship", str(index), entity, "relationship_type_controlled", "error", "fail", True, f"Invalid relationship_type: {relationship_type}")

        relationship_status = norm_lower(row.get("relationship_status"))
        if relationship_status and relationship_status not in RELATIONSHIP_STATUSES:
            add_issue(issues, "relationship", str(index), entity, "relationship_status_controlled", "error", "fail", True, f"Invalid relationship_status: {relationship_status}")

        confidence = normalize(row.get("confidence"))
        if confidence and not is_missing(confidence):
            lowered = confidence.lower()
            numeric_confidence = parse_float(confidence)
            confidence_ok = lowered in {"high", "medium", "low", "unknown"} or (numeric_confidence is not None and 0 <= numeric_confidence <= 1)
            if not confidence_ok:
                add_issue(issues, "relationship", str(index), entity, "confidence_controlled", "error", "fail", True, f"Invalid confidence: {confidence}")

        if relationship_id:
            if relationship_id in relationship_seen:
                add_issue(
                    issues,
                    "relationship",
                    str(index),
                    entity,
                    "duplicate_relationship_id",
                    "error",
                    "fail",
                    True,
                    f"Duplicate relationship_id also appears on row {relationship_seen[relationship_id]}.",
                )
            relationship_seen[relationship_id] = index

        duplicate_key = (phage_id, host_id, relationship_type, normalize(row.get("source_reference")))
        if all(duplicate_key):
            if duplicate_key in key_seen:
                add_issue(
                    issues,
                    "relationship",
                    str(index),
                    entity,
                    "duplicate_relationship_record",
                    "error",
                    "fail",
                    True,
                    f"Duplicate phage-host-relationship-source record also appears on row {key_seen[duplicate_key]}.",
                )
            key_seen[duplicate_key] = index

    if not any(issue["blocking_issue"] == "true" for issue in issues):
        add_issue(issues, "relationship", "NA", path.as_posix(), "relationship_validation_status", "info", "pass", False, f"Validated populated relationship rows: {len(populated_rows)}.")
    return issues


def validate_inputs(
    root: Path,
    assays: Path,
    relationships: Path,
    phage_manifest: Path,
    host_metadata: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    phage_ids, phage_reference_exists = load_phage_ids(phage_manifest)
    host_ids, host_reference_exists = load_host_ids(host_metadata, phage_manifest)
    assay_issues = validate_assays(assays, phage_ids, host_ids, phage_reference_exists, host_reference_exists)
    relationship_issues = validate_relationships(relationships, phage_ids, host_ids, phage_reference_exists, host_reference_exists)
    report: list[dict[str, str]] = []
    assay_blocking = sum(1 for issue in assay_issues if issue["blocking_issue"] == "true")
    relationship_blocking = sum(1 for issue in relationship_issues if issue["blocking_issue"] == "true")
    add_report(
        report,
        "info",
        "phage_host_assay_validation",
        f"assay_issues={len(assay_issues)}; assay_blocking={assay_blocking}; relationship_issues={len(relationship_issues)}; relationship_blocking={relationship_blocking}",
    )
    if assay_blocking or relationship_blocking:
        add_report(report, "error", "phage_host_assay_validation", "One or more assay or relationship validation checks are blocking.")
    else:
        add_report(report, "info", "phage_host_assay_validation", "Assay and relationship tables passed blocking validation checks.")
    if not phage_reference_exists:
        add_report(report, "warning", "canonical_phage_reference", f"Phage manifest not found: {phage_manifest.relative_to(root) if phage_manifest.is_relative_to(root) else phage_manifest}")
    if not host_reference_exists:
        add_report(report, "warning", "canonical_host_reference", f"Host metadata not found: {host_metadata.relative_to(root) if host_metadata.is_relative_to(root) else host_metadata}")
    return assay_issues, relationship_issues, report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    assays = resolve(root, args.assays)
    relationships = resolve(root, args.relationships)
    phage_manifest = resolve(root, args.phage_manifest)
    host_metadata = resolve(root, args.host_metadata)
    assay_issues, relationship_issues, report = validate_inputs(root, assays, relationships, phage_manifest, host_metadata)
    write_tsv(resolve(root, args.assay_validation_output), VALIDATION_COLUMNS, assay_issues)
    write_tsv(resolve(root, args.relationship_validation_output), VALIDATION_COLUMNS, relationship_issues)
    write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report)
    blocking = any(issue["blocking_issue"] == "true" for issue in assay_issues + relationship_issues)
    print(f"Phage-host assay validation complete: blocking={'yes' if blocking else 'no'}.")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
