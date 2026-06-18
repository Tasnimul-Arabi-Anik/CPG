#!/usr/bin/env python3
"""Audit PhageHostLearn benchmark matrix support from RBPbase and Locibase files."""

from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable


SUPPORT_COLUMNS = [
    "entity_type",
    "source_id",
    "canonical_id",
    "matrix_present",
    "matrix_tested_cells",
    "matrix_positive_cells",
    "matrix_negative_cells",
    "source_export_present",
    "source_export_review_status",
    "id_map_present",
    "id_map_review_status",
    "rbpbase_rows",
    "rbpbase_protein_count",
    "locibase_entry_count",
    "locibase_invitro_entry_count",
    "metadata_support_status",
    "blocking_for_assay_import",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
REVIEWED = {"reviewed", "accepted", "approved"}


class PhageHostLearnSupportError(Exception):
    """Raised when benchmark support inputs are malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PhageHostLearn matrix support from RBPbase and Locibase metadata.")
    parser.add_argument("--matrix", default="data/metadata/external/phagehostlearn/phage_host_interactions.csv")
    parser.add_argument("--rbpbase", default="data/metadata/external/phagehostlearn/RBPbase.csv")
    parser.add_argument("--locibase", default="data/metadata/external/phagehostlearn/Locibase.json")
    parser.add_argument("--locibase-invitro", default="data/metadata/external/phagehostlearn/Locibase_invitro.json")
    parser.add_argument("--phage-export", default="data/metadata/source_exports/phagehostlearn_2024_phages.tsv")
    parser.add_argument("--host-export", default="data/metadata/source_exports/phagehostlearn_2024_hosts.tsv")
    parser.add_argument("--phage-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv")
    parser.add_argument("--host-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv")
    parser.add_argument("--support-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


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
    status = note_value(notes, "review_status")
    return status if status else "NA"


def read_matrix(path: Path) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]], list[dict[str, str]]]:
    if not path.exists():
        return {}, {}, [{"severity": "warning", "item": "matrix", "message": f"matrix input missing: {path}"}]
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if len(fieldnames) < 2:
            raise PhageHostLearnSupportError(f"Matrix must contain a host ID column and at least one phage column: {path}")
        host_column = fieldnames[0]
        phage_stats = {normalize(column): {"tested": 0, "positive": 0, "negative": 0} for column in fieldnames[1:] if not is_missing(column)}
        host_stats: dict[str, dict[str, int]] = {}
        rows = list(reader)
    blank_cells = 0
    for row in rows:
        host_id = normalize(row.get(host_column))
        if is_missing(host_id):
            continue
        host_stats.setdefault(host_id, {"tested": 0, "positive": 0, "negative": 0})
        for column in fieldnames[1:]:
            phage_id = normalize(column)
            if is_missing(phage_id):
                continue
            value = normalize(row.get(column))
            if value in {"1", "1.0"}:
                phage_stats[phage_id]["tested"] += 1
                phage_stats[phage_id]["positive"] += 1
                host_stats[host_id]["tested"] += 1
                host_stats[host_id]["positive"] += 1
            elif value in {"0", "0.0"}:
                phage_stats[phage_id]["tested"] += 1
                phage_stats[phage_id]["negative"] += 1
                host_stats[host_id]["tested"] += 1
                host_stats[host_id]["negative"] += 1
            elif is_missing(value):
                blank_cells += 1
            else:
                raise PhageHostLearnSupportError(f"Unexpected matrix value {value!r} for host={host_id}, phage={phage_id}")
    tested = sum(stats["tested"] for stats in phage_stats.values())
    positives = sum(stats["positive"] for stats in phage_stats.values())
    negatives = sum(stats["negative"] for stats in phage_stats.values())
    report = [
        {
            "severity": "info",
            "item": "matrix",
            "message": f"phages={len(phage_stats)}; hosts={len(host_stats)}; tested_cells={tested}; positives={positives}; negatives={negatives}; blanks={blank_cells}",
        }
    ]
    return phage_stats, host_stats, report


def read_rbpbase(path: Path) -> tuple[dict[str, dict[str, int]], list[dict[str, str]]]:
    if not path.exists():
        return {}, [{"severity": "warning", "item": "rbpbase", "message": f"RBPbase input missing: {path}"}]
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if "phage_ID" not in fieldnames:
            raise PhageHostLearnSupportError(f"RBPbase input is missing phage_ID column: {path}")
        rows = list(reader)
    row_counts: dict[str, int] = defaultdict(int)
    proteins: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        phage_id = normalize(row.get("phage_ID"))
        if is_missing(phage_id):
            continue
        row_counts[phage_id] += 1
        protein_id = normalize(row.get("protein_ID"))
        if not is_missing(protein_id):
            proteins[phage_id].add(protein_id)
    support = {
        phage_id: {"rows": count, "proteins": len(proteins.get(phage_id, set()))}
        for phage_id, count in row_counts.items()
    }
    report = [{"severity": "info", "item": "rbpbase", "message": f"rows={len(rows)}; phages={len(support)}"}]
    return support, report


def json_entry_count(value: object) -> int:
    if isinstance(value, (list, dict)):
        return len(value)
    if value is None:
        return 0
    return 1


def read_locibase(path: Path, label: str) -> tuple[dict[str, int], list[dict[str, str]]]:
    if not path.exists():
        return {}, [{"severity": "warning", "item": label, "message": f"{label} input missing: {path}"}]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PhageHostLearnSupportError(f"{label} input is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PhageHostLearnSupportError(f"{label} input must be a JSON object keyed by host/source ID: {path}")
    support = {normalize(key): json_entry_count(value) for key, value in data.items() if not is_missing(key)}
    report = [{"severity": "info", "item": label, "message": f"hosts={len(support)}; entries={sum(support.values())}"}]
    return support, report


def export_support(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    support: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = note_value(row.get("notes", ""), "source_id")
        if is_missing(source_id):
            continue
        support[source_id] = {
            "canonical_id": row.get("genome_id", ""),
            "present": "true",
            "review_status": review_status_from_notes(row.get("notes", "")),
        }
    return support


def map_support(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    support: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = normalize(row.get("source_id"))
        if is_missing(source_id):
            continue
        support[source_id] = {
            "canonical_id": normalize(row.get("canonical_id")),
            "present": "true",
            "review_status": normalize(row.get("review_status")) or "NA",
        }
    return support


def status_for_phage(matrix_present: bool, matrix_missing: bool, rbpbase_missing: bool, rbp_rows: int) -> str:
    if matrix_missing:
        return "matrix_input_missing"
    if not matrix_present:
        return "not_in_interaction_matrix"
    if rbpbase_missing:
        return "matrix_present_rbpbase_input_missing"
    if rbp_rows > 0:
        return "matrix_present_rbpbase_supported"
    return "matrix_present_no_rbpbase_support"


def status_for_host(matrix_present: bool, matrix_missing: bool, locibase_missing: bool, locibase_count: int, invitro_count: int) -> str:
    if matrix_missing:
        return "matrix_input_missing"
    if not matrix_present:
        return "not_in_interaction_matrix"
    if locibase_missing:
        return "matrix_present_locibase_input_missing"
    if locibase_count > 0 or invitro_count > 0:
        return "matrix_present_locibase_supported"
    return "matrix_present_no_locibase_support"


def row_for_entity(
    entity_type: str,
    source_id: str,
    matrix_stats: dict[str, int] | None,
    source_export: dict[str, dict[str, str]],
    id_map: dict[str, dict[str, str]],
    rbpbase: dict[str, dict[str, int]],
    locibase: dict[str, int],
    locibase_invitro: dict[str, int],
    rbpbase_missing: bool,
    locibase_missing: bool,
    matrix_missing: bool,
) -> dict[str, str]:
    source_info = source_export.get(source_id, {})
    map_info = id_map.get(source_id, {})
    canonical_id = map_info.get("canonical_id") or source_info.get("canonical_id") or "NA"
    map_review_status = map_info.get("review_status", "NA")
    source_review_status = source_info.get("review_status", "NA")
    matrix_present = matrix_stats is not None
    tested = matrix_stats.get("tested", 0) if matrix_stats else 0
    positive = matrix_stats.get("positive", 0) if matrix_stats else 0
    negative = matrix_stats.get("negative", 0) if matrix_stats else 0
    rbp_rows = rbpbase.get(source_id, {}).get("rows", 0)
    rbp_proteins = rbpbase.get(source_id, {}).get("proteins", 0)
    locibase_count = locibase.get(source_id, 0)
    locibase_invitro_count = locibase_invitro.get(source_id, 0)
    if entity_type == "phage":
        metadata_status = status_for_phage(matrix_present, matrix_missing, rbpbase_missing, rbp_rows)
    else:
        metadata_status = status_for_host(matrix_present, matrix_missing, locibase_missing, locibase_count, locibase_invitro_count)
    map_reviewed = map_review_status.lower() in REVIEWED
    blocking = matrix_present and (not map_info or not map_reviewed or is_missing(canonical_id))
    notes = []
    if matrix_missing:
        notes.append("matrix_input_missing")
    if matrix_present:
        notes.append("matrix_entity=true")
    if blocking:
        notes.append("assay_import_blocked_until_id_map_reviewed")
    if entity_type == "phage" and rbp_rows == 0:
        notes.append("no_RBPbase_support_for_source_id")
    if entity_type == "host" and locibase_count == 0 and locibase_invitro_count == 0:
        notes.append("no_Locibase_support_for_source_id")
    return {
        "entity_type": entity_type,
        "source_id": source_id,
        "canonical_id": canonical_id,
        "matrix_present": "true" if matrix_present else "false",
        "matrix_tested_cells": str(tested),
        "matrix_positive_cells": str(positive),
        "matrix_negative_cells": str(negative),
        "source_export_present": source_info.get("present", "false"),
        "source_export_review_status": source_review_status,
        "id_map_present": map_info.get("present", "false"),
        "id_map_review_status": map_review_status,
        "rbpbase_rows": str(rbp_rows) if entity_type == "phage" else "NA",
        "rbpbase_protein_count": str(rbp_proteins) if entity_type == "phage" else "NA",
        "locibase_entry_count": str(locibase_count) if entity_type == "host" else "NA",
        "locibase_invitro_entry_count": str(locibase_invitro_count) if entity_type == "host" else "NA",
        "metadata_support_status": metadata_status,
        "blocking_for_assay_import": "true" if blocking else "false",
        "notes": "; ".join(notes) if notes else "NA",
    }


def validate_paths(args: argparse.Namespace, root: Path) -> None:
    inputs = [
        resolve(root, args.matrix),
        resolve(root, args.rbpbase),
        resolve(root, args.locibase),
        resolve(root, args.locibase_invitro),
        resolve(root, args.phage_export),
        resolve(root, args.host_export),
        resolve(root, args.phage_map),
        resolve(root, args.host_map),
    ]
    outputs = [resolve(root, args.support_output), resolve(root, args.report_output)]
    for out in outputs:
        for inp in inputs:
            if out.resolve() == inp.resolve():
                raise PhageHostLearnSupportError(f"Output path must not overwrite input path: {display(root, out)}")
    if outputs[0].resolve() == outputs[1].resolve():
        raise PhageHostLearnSupportError("support-output and report-output must be different paths")


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    validate_paths(args, root)
    matrix_path = resolve(root, args.matrix)
    rbpbase_path = resolve(root, args.rbpbase)
    locibase_path = resolve(root, args.locibase)
    locibase_invitro_path = resolve(root, args.locibase_invitro)
    _phage_fields, phage_export_rows = read_tsv(resolve(root, args.phage_export))
    _host_fields, host_export_rows = read_tsv(resolve(root, args.host_export))
    _phage_map_fields, phage_map_rows = read_tsv(resolve(root, args.phage_map))
    _host_map_fields, host_map_rows = read_tsv(resolve(root, args.host_map))

    report: list[dict[str, str]] = []
    phage_matrix, host_matrix, matrix_report = read_matrix(matrix_path)
    report.extend(matrix_report)
    rbpbase, rbp_report = read_rbpbase(rbpbase_path)
    report.extend(rbp_report)
    locibase, locibase_report = read_locibase(locibase_path, "locibase")
    report.extend(locibase_report)
    locibase_invitro, locibase_invitro_report = read_locibase(locibase_invitro_path, "locibase_invitro")
    report.extend(locibase_invitro_report)

    phage_export = export_support(phage_export_rows)
    host_export = export_support(host_export_rows)
    phage_map = map_support(phage_map_rows)
    host_map = map_support(host_map_rows)
    matrix_missing = not matrix_path.exists()
    rbpbase_missing = not rbpbase_path.exists()
    locibase_missing = not locibase_path.exists() and not locibase_invitro_path.exists()

    phage_ids = sorted(set(phage_matrix) | set(phage_export) | set(phage_map) | set(rbpbase))
    host_ids = sorted(set(host_matrix) | set(host_export) | set(host_map) | set(locibase) | set(locibase_invitro))
    support_rows: list[dict[str, str]] = []
    for source_id in phage_ids:
        support_rows.append(
            row_for_entity(
                "phage",
                source_id,
                phage_matrix.get(source_id),
                phage_export,
                phage_map,
                rbpbase,
                {},
                {},
                rbpbase_missing,
                False,
                matrix_missing,
            )
        )
    for source_id in host_ids:
        support_rows.append(
            row_for_entity(
                "host",
                source_id,
                host_matrix.get(source_id),
                host_export,
                host_map,
                {},
                locibase,
                locibase_invitro,
                False,
                locibase_missing,
                matrix_missing,
            )
        )
    matrix_phage_count = sum(1 for row in support_rows if row["entity_type"] == "phage" and row["matrix_present"] == "true")
    rbp_supported = sum(1 for row in support_rows if row["entity_type"] == "phage" and row["rbpbase_rows"] not in {"0", "NA"})
    matrix_rbp_supported = sum(
        1
        for row in support_rows
        if row["entity_type"] == "phage" and row["matrix_present"] == "true" and row["rbpbase_rows"] not in {"0", "NA"}
    )
    matrix_host_count = sum(1 for row in support_rows if row["entity_type"] == "host" and row["matrix_present"] == "true")
    locibase_supported = sum(
        1
        for row in support_rows
        if row["entity_type"] == "host"
        and (row["locibase_entry_count"] not in {"0", "NA"} or row["locibase_invitro_entry_count"] not in {"0", "NA"})
    )
    matrix_locibase_supported = sum(
        1
        for row in support_rows
        if row["entity_type"] == "host"
        and row["matrix_present"] == "true"
        and (row["locibase_entry_count"] not in {"0", "NA"} or row["locibase_invitro_entry_count"] not in {"0", "NA"})
    )
    blocking = sum(1 for row in support_rows if row["blocking_for_assay_import"] == "true")
    report.append(
        {
            "severity": "info",
            "item": "support_summary",
            "message": f"rows={len(support_rows)}; matrix_phages={matrix_phage_count}; matrix_rbpbase_supported_phages={matrix_rbp_supported}; total_rbpbase_supported_phages={rbp_supported}; matrix_hosts={matrix_host_count}; matrix_locibase_supported_hosts={matrix_locibase_supported}; total_locibase_supported_hosts={locibase_supported}; blocking_map_rows={blocking}",
        }
    )
    report.append(
        {
            "severity": "info",
            "item": "claim_boundary",
            "message": "This audit supports benchmark curation only; RBPbase/Locibase presence is not accepted receptor specificity or host-range evidence.",
        }
    )
    write_tsv_atomic(resolve(root, args.support_output), SUPPORT_COLUMNS, support_rows)
    write_tsv_atomic(resolve(root, args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn metadata support audit complete: rows={len(support_rows)}; blocking_map_rows={blocking}.")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except PhageHostLearnSupportError as exc:
        report_path = Path(args.report_output)
        write_tsv_atomic(report_path, REPORT_COLUMNS, [{"severity": "error", "item": "phagehostlearn_metadata_support", "message": str(exc)}])
        print(f"PhageHostLearn metadata support audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
