#!/usr/bin/env python3
"""Audit PhageHostLearn source-to-canonical ID maps for manual review readiness."""

from __future__ import annotations

import argparse
import csv
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


REVIEW_COLUMNS = [
    "entity_type",
    "source_id",
    "canonical_id",
    "map_review_status",
    "source_export_present",
    "source_export_review_status",
    "canonical_matches_export",
    "metadata_support_present",
    "matrix_present",
    "metadata_support_status",
    "structural_status",
    "review_recommendation",
    "blocking_for_assay_import",
    "required_action",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
REVIEWED = {"reviewed", "accepted", "approved"}


class MapReviewAuditError(Exception):
    """Raised when map-review audit inputs are malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PhageHostLearn source-to-canonical maps for manual review readiness.")
    parser.add_argument("--metadata-support", default="results/qc/phagehostlearn_2024_metadata_support.tsv")
    parser.add_argument("--phage-export", default="data/metadata/source_exports/phagehostlearn_2024_phages.tsv")
    parser.add_argument("--host-export", default="data/metadata/source_exports/phagehostlearn_2024_hosts.tsv")
    parser.add_argument("--phage-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv")
    parser.add_argument("--host-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv")
    parser.add_argument("--review-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--root", default=".")
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


def display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def write_tsv_atomic(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})
    tmp.replace(path)


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def note_value(notes: str, key: str) -> str:
    match = re.search(rf"(?:^|;\s*){re.escape(key)}=([^;]+)", notes)
    return match.group(1).strip() if match else ""


def review_status_from_notes(notes: str) -> str:
    return note_value(notes, "review_status") or "NA"


def validate_paths(args: argparse.Namespace, root: Path) -> None:
    inputs = [
        resolve(root, args.metadata_support),
        resolve(root, args.phage_export),
        resolve(root, args.host_export),
        resolve(root, args.phage_map),
        resolve(root, args.host_map),
    ]
    outputs = [resolve(root, args.review_output), resolve(root, args.report_output)]
    for out in outputs:
        for inp in inputs:
            if out.resolve() == inp.resolve():
                raise MapReviewAuditError(f"Output path must not overwrite input path: {display(root, out)}")
    if outputs[0].resolve() == outputs[1].resolve():
        raise MapReviewAuditError("review-output and report-output must be different paths")


def export_by_source(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = note_value(row.get("notes", ""), "source_id")
        if is_missing(source_id):
            continue
        out[source_id] = {
            "canonical_id": row.get("genome_id", ""),
            "review_status": review_status_from_notes(row.get("notes", "")),
        }
    return out


def support_by_entity(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        entity_type = norm_lower(row.get("entity_type"))
        source_id = normalize(row.get("source_id"))
        if entity_type and source_id:
            out[(entity_type, source_id)] = row
    return out


def duplicate_source_ids(rows: list[dict[str, str]]) -> set[str]:
    counts = Counter(normalize(row.get("source_id")) for row in rows if not is_missing(row.get("source_id")))
    return {source_id for source_id, count in counts.items() if count > 1}


def duplicate_canonical_ids(rows: list[dict[str, str]]) -> set[str]:
    source_by_canonical: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        source_id = normalize(row.get("source_id"))
        canonical_id = normalize(row.get("canonical_id"))
        if not is_missing(source_id) and not is_missing(canonical_id):
            source_by_canonical[canonical_id].add(source_id)
    return {canonical for canonical, sources in source_by_canonical.items() if len(sources) > 1}


def recommendation_for(
    source_id: str,
    canonical_id: str,
    map_review_status: str,
    export_info: dict[str, str],
    support_info: dict[str, str],
    duplicate_sources: set[str],
    duplicate_canonicals: set[str],
) -> tuple[str, str, str, str, str]:
    notes: list[str] = []
    export_present = bool(export_info)
    export_status = export_info.get("review_status", "NA")
    export_canonical = export_info.get("canonical_id", "")
    canonical_matches_export = export_present and canonical_id == export_canonical
    support_present = bool(support_info)
    metadata_status = support_info.get("metadata_support_status", "support_input_missing") if support_present else "support_input_missing"
    matrix_present = support_info.get("matrix_present", "unknown") if support_present else "unknown"
    map_status_reviewed = norm_lower(map_review_status) in REVIEWED
    export_reviewed = norm_lower(export_status) in REVIEWED

    if is_missing(source_id):
        return "invalid_missing_source_id", "invalid", "true", "Fill source_id in the map row.", "source_id missing"
    if source_id in duplicate_sources:
        return "invalid_duplicate_source_id", "invalid", "true", "Resolve duplicate source_id rows before review.", "duplicate source_id"
    if is_missing(canonical_id):
        return "invalid_missing_canonical_id", "invalid", "true", "Fill canonical_id in the map row.", "canonical_id missing"
    if canonical_id in duplicate_canonicals:
        return "invalid_duplicate_canonical_id", "invalid", "true", "Resolve canonical_id assigned to multiple source IDs before review.", "duplicate canonical_id"
    if not export_present:
        return "missing_source_export_entity", "missing_entity", "true", "Create or review the matching benchmark source export row.", "source_id absent from source export"
    if not canonical_matches_export:
        return "canonical_mismatch", "invalid", "true", "Fix canonical_id so it matches the benchmark source export genome_id.", f"export_canonical_id={export_canonical or 'NA'}"
    if not support_present:
        return "needs_metadata_support_audit", "waiting_support", "true", "Run stage_0_phagehostlearn_metadata_support before map review.", "metadata support audit row missing"
    if metadata_status == "matrix_input_missing":
        return "waiting_matrix_input", "waiting_matrix", "true", "Provide the reviewed PhageHostLearn matrix locally before map review.", "matrix input missing"
    if matrix_present != "true":
        return "not_in_matrix", "not_applicable", "false", "No assay-map approval needed unless this source ID enters an assay matrix.", "source ID not in matrix"
    if not export_reviewed:
        return "pending_entity_review", "structurally_valid", "true", "Review the source export entity before marking the map row reviewed.", f"source_export_review_status={export_status}"
    if map_status_reviewed:
        return "reviewed_ready_for_assay_normalization", "reviewed", "false", "No action required for this map row.", "reviewed map row is usable by normalize_assay_matrix.py"
    if norm_lower(map_review_status) in {"pending", ""}:
        return "ready_for_manual_map_review", "structurally_valid", "true", "If source provenance has been manually checked, set review_status to reviewed.", "map row is structurally reviewable"
    return "unrecognized_map_review_status", "invalid", "true", "Use review_status pending, reviewed, accepted, or approved.", f"map_review_status={map_review_status}"


def audit_entity(
    entity_type: str,
    map_rows: list[dict[str, str]],
    exports: dict[str, dict[str, str]],
    support: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    duplicate_sources = duplicate_source_ids(map_rows)
    duplicate_canonicals = duplicate_canonical_ids(map_rows)
    review_rows: list[dict[str, str]] = []
    for row in map_rows:
        source_id = normalize(row.get("source_id"))
        canonical_id = normalize(row.get("canonical_id"))
        map_review_status = normalize(row.get("review_status")) or "NA"
        export_info = exports.get(source_id, {})
        support_info = support.get((entity_type, source_id), {})
        recommendation, structural_status, blocking, action, note = recommendation_for(
            source_id,
            canonical_id,
            map_review_status,
            export_info,
            support_info,
            duplicate_sources,
            duplicate_canonicals,
        )
        support_present = bool(support_info)
        export_present = bool(export_info)
        export_status = export_info.get("review_status", "NA")
        export_canonical = export_info.get("canonical_id", "")
        review_rows.append(
            {
                "entity_type": entity_type,
                "source_id": source_id or "NA",
                "canonical_id": canonical_id or "NA",
                "map_review_status": map_review_status,
                "source_export_present": "true" if export_present else "false",
                "source_export_review_status": export_status,
                "canonical_matches_export": "true" if export_present and canonical_id == export_canonical else "false",
                "metadata_support_present": "true" if support_present else "false",
                "matrix_present": support_info.get("matrix_present", "unknown") if support_present else "unknown",
                "metadata_support_status": support_info.get("metadata_support_status", "support_input_missing") if support_present else "support_input_missing",
                "structural_status": structural_status,
                "review_recommendation": recommendation,
                "blocking_for_assay_import": blocking,
                "required_action": action,
                "notes": note,
            }
        )
    return review_rows


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    validate_paths(args, root)
    metadata_support_path = resolve(root, args.metadata_support)
    phage_export_path = resolve(root, args.phage_export)
    host_export_path = resolve(root, args.host_export)
    phage_map_path = resolve(root, args.phage_map)
    host_map_path = resolve(root, args.host_map)
    _support_fields, support_rows = read_tsv(metadata_support_path)
    _phage_export_fields, phage_export_rows = read_tsv(phage_export_path)
    _host_export_fields, host_export_rows = read_tsv(host_export_path)
    phage_map_fields, phage_map_rows = read_tsv(phage_map_path)
    host_map_fields, host_map_rows = read_tsv(host_map_path)
    report: list[dict[str, str]] = []

    for label, fields in [("phage_map", phage_map_fields), ("host_map", host_map_fields)]:
        missing = [column for column in ("source_id", "canonical_id", "review_status") if column not in fields]
        if missing:
            raise MapReviewAuditError(f"{label} is missing required columns: {';'.join(missing)}")
    if not metadata_support_path.exists():
        report.append({"severity": "warning", "item": "metadata_support", "message": f"metadata support audit is missing: {display(root, metadata_support_path)}"})

    support = support_by_entity(support_rows)
    phage_exports = export_by_source(phage_export_rows)
    host_exports = export_by_source(host_export_rows)
    review_rows = audit_entity("phage", phage_map_rows, phage_exports, support)
    review_rows.extend(audit_entity("host", host_map_rows, host_exports, support))
    rec_counts = Counter(row["review_recommendation"] for row in review_rows)
    blocking = sum(1 for row in review_rows if row["blocking_for_assay_import"] == "true")
    report.append(
        {
            "severity": "info",
            "item": "map_review_summary",
            "message": f"rows={len(review_rows)}; blocking={blocking}; " + "; ".join(f"{key}={value}" for key, value in sorted(rec_counts.items())),
        }
    )
    report.append(
        {
            "severity": "info",
            "item": "claim_boundary",
            "message": "This audit recommends manual map-review actions only; it does not approve mappings or import assay outcomes.",
        }
    )
    write_tsv_atomic(resolve(root, args.review_output), REVIEW_COLUMNS, review_rows)
    write_tsv_atomic(resolve(root, args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn map review audit complete: rows={len(review_rows)}; blocking={blocking}.")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except MapReviewAuditError as exc:
        write_tsv_atomic(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "phagehostlearn_map_review", "message": str(exc)}])
        print(f"PhageHostLearn map review audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
