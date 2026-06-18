#!/usr/bin/env python3
"""Create curation templates for assay-matrix source-to-canonical ID maps."""

from __future__ import annotations

import argparse
import csv
import re
import tempfile
from pathlib import Path
from typing import Iterable

import normalize_assay_matrix as matrix


MAP_COLUMNS = ["source_id", "canonical_id", "review_status", "notes"]
REPORT_COLUMNS = [
    "source_id",
    "entity_type",
    "source_identifier",
    "mapping_status",
    "existing_canonical_id",
    "existing_review_status",
    "candidate_count",
    "candidate_ids",
    "map_action",
    "notes",
]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
REVIEWED = {"reviewed", "accepted", "approved"}
PHAGE_RECORD_TYPES = {"phage", "cultured_phage", "prophage", "viral_contig"}
HOST_RECORD_TYPES = {"host", "host_genome"}


class MappingTemplateError(Exception):
    """Raised when template generation cannot proceed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create assay matrix mapping templates from a reviewed matrix file.")
    parser.add_argument("--config", required=True, help="Assay matrix source YAML configuration.")
    parser.add_argument("--report-output", required=True, help="Output mapping curation report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative paths.")
    parser.add_argument("--only-source", default="", help="Optional source_id to process from the config.")
    parser.add_argument("--include-disabled", action="store_true", help="Process disabled config sources when their matrix files exist.")
    parser.add_argument("--update-maps", action="store_true", help="Append missing source IDs to configured mapping files as pending rows.")
    parser.add_argument("--phage-manifest", default="results/seed/qc/phage_genome_manifest.tsv", help="Canonical phage/host manifest TSV.")
    parser.add_argument("--host-metadata", default="results/seed/host_features/host_metadata.tsv", help="Canonical host metadata TSV.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm_lower(value: object) -> str:
    return normalize(value).lower()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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


def write_tsv_atomic(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        fieldnames = list(columns)
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})
    tmp.replace(path)


def load_canonical_ids(phage_manifest: Path, host_metadata: Path) -> tuple[set[str], set[str]]:
    phage_ids: set[str] = set()
    host_ids: set[str] = set()
    _fields, manifest_rows = read_tsv(phage_manifest)
    for row in manifest_rows:
        record_type = norm_lower(row.get("record_type"))
        genome_id = normalize(row.get("genome_id") or row.get("phage_genome_id") or row.get("host_genome_id"))
        if not genome_id:
            continue
        if record_type in PHAGE_RECORD_TYPES:
            phage_ids.add(genome_id)
        elif record_type in HOST_RECORD_TYPES:
            host_ids.add(genome_id)
    _fields, host_rows = read_tsv(host_metadata)
    for row in host_rows:
        host_id = normalize(row.get("host_genome_id") or row.get("host_id") or row.get("genome_id"))
        if host_id:
            host_ids.add(host_id)
    return phage_ids, host_ids


def load_map_rows(path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    fieldnames, rows = read_tsv(path)
    if fieldnames and any(column not in fieldnames for column in MAP_COLUMNS):
        missing = [column for column in MAP_COLUMNS if column not in fieldnames]
        raise MappingTemplateError(f"Mapping file {path} is missing required columns: {';'.join(missing)}")
    by_source: dict[str, dict[str, str]] = {}
    clean_rows: list[dict[str, str]] = []
    for row in rows:
        if all(is_missing(row.get(column, "")) for column in MAP_COLUMNS):
            continue
        source_id = normalize(row.get("source_id"))
        if not source_id:
            raise MappingTemplateError(f"Mapping file {path} contains a row without source_id.")
        if source_id in by_source:
            raise MappingTemplateError(f"Mapping file {path} contains duplicate source_id: {source_id}")
        clean_row = {column: normalize(row.get(column, "")) for column in MAP_COLUMNS}
        by_source[source_id] = clean_row
        clean_rows.append(clean_row)
    return clean_rows, by_source


def candidate_ids(source_identifier: str, canonical_ids: set[str]) -> tuple[str, list[str]]:
    if source_identifier in canonical_ids:
        return "exact_match", [source_identifier]
    normalized = normalize_key(source_identifier)
    if not normalized:
        return "no_candidate", []
    candidates = sorted(identifier for identifier in canonical_ids if normalize_key(identifier) == normalized)
    if len(candidates) == 1:
        return "normalized_unique_candidate", candidates
    if len(candidates) > 1:
        return "ambiguous_normalized_candidates", candidates
    return "no_candidate", []


def matrix_source_ids(spec: dict, root: Path) -> tuple[list[str], list[str], str]:
    source_id = normalize(spec.get("source_id")) or "assay_matrix_source"
    matrix_path = resolve(root, normalize(spec.get("matrix_path")))
    if not matrix_path.exists():
        raise MappingTemplateError(f"{source_id} matrix_path does not exist: {matrix_path}")
    fieldnames, rows = matrix.read_table(matrix_path, matrix.delimiter_for(matrix_path, normalize(spec.get("delimiter", "auto"))))
    if not fieldnames:
        raise MappingTemplateError(f"{source_id} matrix has no header.")
    host_column = normalize(spec.get("host_id_column"))
    if not host_column or host_column == "auto_first_column":
        host_column = fieldnames[0]
    if host_column not in fieldnames:
        raise MappingTemplateError(f"{source_id} host_id_column does not exist in matrix: {host_column}")
    phage_ids = sorted({normalize(column) for column in fieldnames if column != host_column and not is_missing(column)})
    host_ids = sorted({normalize(row.get(host_column)) for row in rows if not is_missing(row.get(host_column))})
    return phage_ids, host_ids, matrix_path.as_posix()


def pending_row(source_identifier: str, candidate_status: str, candidates: list[str], source_id: str, entity_type: str) -> dict[str, str]:
    candidate = candidates[0] if len(candidates) == 1 and candidate_status in {"exact_match", "normalized_unique_candidate"} else ""
    return {
        "source_id": source_identifier,
        "canonical_id": candidate,
        "review_status": "pending",
        "notes": f"generated_from={source_id}; entity_type={entity_type}; candidate_status={candidate_status}; reviewer_must_set_review_status_to_reviewed_to_enable",
    }


def report_row(
    source_id: str,
    entity_type: str,
    source_identifier: str,
    existing: dict[str, str] | None,
    candidate_status: str,
    candidates: list[str],
    action: str,
) -> dict[str, str]:
    review_status = normalize(existing.get("review_status")) if existing else "NA"
    canonical_id = normalize(existing.get("canonical_id")) if existing else "NA"
    if existing and review_status.lower() in REVIEWED and canonical_id:
        mapping_status = "reviewed_mapped"
    elif existing:
        mapping_status = "existing_not_reviewed"
    else:
        mapping_status = candidate_status
    return {
        "source_id": source_id,
        "entity_type": entity_type,
        "source_identifier": source_identifier,
        "mapping_status": mapping_status,
        "existing_canonical_id": canonical_id,
        "existing_review_status": review_status,
        "candidate_count": str(len(candidates)),
        "candidate_ids": ";".join(candidates) if candidates else "NA",
        "map_action": action,
        "notes": "review_status=reviewed is required before normalize_assay_matrix.py will use a mapping",
    }


def process_entity(
    source_id: str,
    entity_type: str,
    source_identifiers: list[str],
    canonical_ids: set[str],
    map_path: Path,
    update_maps: bool,
) -> tuple[list[dict[str, str]], int]:
    existing_rows, existing_by_source = load_map_rows(map_path)
    report: list[dict[str, str]] = []
    added = 0
    rows_to_write = list(existing_rows)
    for source_identifier in source_identifiers:
        existing = existing_by_source.get(source_identifier)
        status, candidates = candidate_ids(source_identifier, canonical_ids)
        if existing:
            action = "preserved_existing_mapping"
        elif update_maps:
            rows_to_write.append(pending_row(source_identifier, status, candidates, source_id, entity_type))
            action = "added_pending_mapping_row"
            added += 1
        else:
            action = "report_only"
        report.append(report_row(source_id, entity_type, source_identifier, existing, status, candidates, action))
    if update_maps:
        write_tsv_atomic(map_path, MAP_COLUMNS, rows_to_write)
    return report, added


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    config_path = resolve(root, args.config)
    config = matrix.load_yaml(config_path)
    phage_ids, host_ids = load_canonical_ids(resolve(root, args.phage_manifest), resolve(root, args.host_metadata))
    report_rows: list[dict[str, str]] = []
    processed = 0
    skipped = 0
    added_total = 0
    for index, spec in enumerate(config.get("sources", []), start=1):
        if not isinstance(spec, dict):
            raise MappingTemplateError(f"Source entry {index} is not a mapping.")
        source_id = normalize(spec.get("source_id")) or f"source_{index}"
        if args.only_source and source_id != args.only_source:
            continue
        enabled = matrix.bool_value(spec.get("enabled"), False)
        if not enabled and not args.include_disabled:
            skipped += 1
            continue
        phage_source_ids, host_source_ids, matrix_path = matrix_source_ids(spec, root)
        processed += 1
        phage_map_text = normalize(spec.get("phage_id_map"))
        host_map_text = normalize(spec.get("host_id_map"))
        if not phage_map_text or not host_map_text:
            raise MappingTemplateError(f"{source_id} must define phage_id_map and host_id_map.")
        phage_report, phage_added = process_entity(
            source_id,
            "phage",
            phage_source_ids,
            phage_ids,
            resolve(root, phage_map_text),
            args.update_maps,
        )
        host_report, host_added = process_entity(
            source_id,
            "host",
            host_source_ids,
            host_ids,
            resolve(root, host_map_text),
            args.update_maps,
        )
        added_total += phage_added + host_added
        report_rows.extend(phage_report)
        report_rows.extend(host_report)
        report_rows.append(
            {
                "source_id": source_id,
                "entity_type": "summary",
                "source_identifier": "NA",
                "mapping_status": "summary",
                "existing_canonical_id": "NA",
                "existing_review_status": "NA",
                "candidate_count": "NA",
                "candidate_ids": "NA",
                "map_action": "summary",
                "notes": f"matrix_path={matrix_path}; phage_source_ids={len(phage_source_ids)}; host_source_ids={len(host_source_ids)}; pending_rows_added={phage_added + host_added}",
            }
        )
    if args.only_source and processed == 0:
        raise MappingTemplateError(f"Requested --only-source was not found or not processed: {args.only_source}")
    report_output = resolve(root, args.report_output)
    write_tsv_atomic(report_output, REPORT_COLUMNS, report_rows)
    print(f"Assay matrix mapping template generation complete: processed_sources={processed}; skipped_sources={skipped}; pending_rows_added={added_total}; report_rows={len(report_rows)}.")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except MappingTemplateError as exc:
        print(f"Assay matrix mapping template generation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
