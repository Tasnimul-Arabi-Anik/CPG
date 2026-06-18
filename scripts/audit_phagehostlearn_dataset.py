#!/usr/bin/env python3
"""Consolidated PhageHostLearn dataset audit.

This audit is the source-specific adapter behind the generic assay dataset audit
stage. It summarizes whether the benchmark files, matrix IDs, canonical ID maps,
source exports, feature metadata, and reviewed assay export are usable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Iterable


AUDIT_COLUMNS = [
    "check_id",
    "area",
    "readiness_level",
    "status",
    "severity",
    "blocking_for_assay_import",
    "evidence_path",
    "evidence_summary",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
REVIEWED = {"reviewed", "accepted", "approved"}


class DatasetAuditError(Exception):
    """Raised when required audit inputs are malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PhageHostLearn dataset readiness in one source-level report.")
    parser.add_argument("--file-manifest", default="data/metadata/external/phagehostlearn/phagehostlearn_file_manifest.tsv")
    parser.add_argument("--matrix", default="data/metadata/external/phagehostlearn/phage_host_interactions.csv")
    parser.add_argument("--phage-archive", default="data/metadata/external/phagehostlearn/phages_genomes.zip")
    parser.add_argument("--host-archive", default="data/metadata/external/phagehostlearn/klebsiella_genomes.zip")
    parser.add_argument("--rbpbase", default="data/metadata/external/phagehostlearn/RBPbase.csv")
    parser.add_argument("--locibase", default="data/metadata/external/phagehostlearn/Locibase.json")
    parser.add_argument("--locibase-invitro", default="data/metadata/external/phagehostlearn/Locibase_invitro.json")
    parser.add_argument("--phage-export", default="data/metadata/source_exports/phagehostlearn_2024_phages.tsv")
    parser.add_argument("--host-export", default="data/metadata/source_exports/phagehostlearn_2024_hosts.tsv")
    parser.add_argument("--phage-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv")
    parser.add_argument("--host-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv")
    parser.add_argument("--assay-export", default="data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv")
    parser.add_argument("--audit-output", required=True)
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


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def read_tsv(path: Path, required: bool = False) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        if required:
            raise DatasetAuditError(f"Missing required TSV input: {path}")
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def note_value(notes: str, key: str) -> str:
    for part in notes.split(";"):
        part = part.strip()
        if part.startswith(f"{key}="):
            return part.split("=", 1)[1].strip()
    return ""


def add_row(
    rows: list[dict[str, str]],
    check_id: str,
    area: str,
    readiness_level: str,
    status: str,
    severity: str,
    blocking: bool,
    evidence_path: str,
    summary: str,
    next_action: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "area": area,
            "readiness_level": readiness_level,
            "status": status,
            "severity": severity,
            "blocking_for_assay_import": "true" if blocking else "false",
            "evidence_path": evidence_path,
            "evidence_summary": summary,
            "next_action": next_action,
        }
    )


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_file_manifest(root: Path, manifest: Path) -> tuple[str, str, str, bool]:
    fields, rows = read_tsv(manifest)
    if not rows:
        return "missing_manifest", "warning", "manifest_rows=0", False
    present = missing = mismatch = sha_pending = 0
    for row in rows:
        expected_path = resolve(root, row.get("expected_path", ""))
        if not expected_path.exists():
            missing += 1
            continue
        present += 1
        expected_size = row.get("expected_size_bytes", "")
        if not is_missing(expected_size) and expected_path.stat().st_size != int(float(expected_size)):
            mismatch += 1
        expected_md5 = row.get("expected_md5", "")
        if not is_missing(expected_md5) and file_hash(expected_path, "md5") != expected_md5:
            mismatch += 1
        expected_sha = row.get("expected_sha256", "")
        if is_missing(expected_sha):
            sha_pending += 1
        elif file_hash(expected_path, "sha256") != expected_sha:
            mismatch += 1
    if mismatch:
        return "fail_checksum_or_size_mismatch", "error", f"manifest_rows={len(rows)}; present={present}; missing={missing}; mismatches={mismatch}; sha256_pending={sha_pending}", True
    if missing:
        return "warn_missing_local_files", "warning", f"manifest_rows={len(rows)}; present={present}; missing={missing}; mismatches={mismatch}; sha256_pending={sha_pending}", False
    return "pass", "info", f"manifest_rows={len(rows)}; present={present}; missing={missing}; mismatches={mismatch}; sha256_pending={sha_pending}", False


def read_matrix(path: Path, allowed_phages: set[str] | None = None, allowed_hosts: set[str] | None = None) -> tuple[set[str], set[str], dict[str, int]]:
    if not path.exists():
        return set(), set(), {"rows": 0, "phages": 0, "tested": 0, "positive": 0, "negative": 0, "blank": 0}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if len(fields) < 2:
            raise DatasetAuditError(f"Matrix requires one host ID column and at least one phage column: {path}")
        host_column = fields[0]
        all_phages = {normalize(value) for value in fields[1:] if not is_missing(value)}
        phages = all_phages if allowed_phages is None else all_phages & allowed_phages
        hosts: set[str] = set()
        stats = {"rows": 0, "phages": len(phages), "tested": 0, "positive": 0, "negative": 0, "blank": 0}
        for row in reader:
            host_id = normalize(row.get(host_column))
            if is_missing(host_id) or (allowed_hosts is not None and host_id not in allowed_hosts):
                continue
            stats["rows"] += 1
            hosts.add(host_id)
            for phage_id in phages:
                value = normalize(row.get(phage_id))
                if value in {"1", "1.0"}:
                    stats["tested"] += 1
                    stats["positive"] += 1
                elif value in {"0", "0.0"}:
                    stats["tested"] += 1
                    stats["negative"] += 1
                elif is_missing(value):
                    stats["blank"] += 1
                else:
                    raise DatasetAuditError(f"Unexpected matrix value {value!r} for host={host_id}, phage={phage_id}")
    return phages, hosts, stats


def export_by_source(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result = {}
    for row in rows:
        source_id = note_value(row.get("notes", ""), "source_id")
        if not is_missing(source_id):
            result[source_id] = row
    return result


def reviewed_export_ids(rows: list[dict[str, str]]) -> set[str]:
    reviewed = set()
    for row in rows:
        source_id = note_value(row.get("notes", ""), "source_id")
        status = note_value(row.get("notes", ""), "review_status").lower()
        if source_id and status in REVIEWED:
            reviewed.add(source_id)
    return reviewed


def map_stats(map_rows: list[dict[str, str]], source_ids: set[str], canonical_ids: set[str]) -> dict[str, int]:
    mapped_ids = {row.get("source_id", "") for row in map_rows if row.get("source_id")}
    reviewed = {row.get("source_id", "") for row in map_rows if row.get("review_status", "").lower() in REVIEWED}
    canonical_values = [row.get("canonical_id", "") for row in map_rows]
    duplicate_source_ids = len(mapped_ids) != len([row.get("source_id", "") for row in map_rows if row.get("source_id")])
    duplicate_canonical_ids = len(set(canonical_values)) != len([value for value in canonical_values if value])
    return {
        "rows": len(map_rows),
        "mapped_ids": len(mapped_ids),
        "reviewed": len(reviewed),
        "pending": len(map_rows) - len(reviewed),
        "missing_source_ids": len(source_ids - mapped_ids),
        "extra_source_ids": len(mapped_ids - source_ids),
        "missing_canonical": sum(1 for value in canonical_values if is_missing(value)),
        "unresolved_canonical": sum(1 for value in canonical_values if not is_missing(value) and value not in canonical_ids),
        "duplicate_source_ids": int(duplicate_source_ids),
        "duplicate_canonical_ids": int(duplicate_canonical_ids),
    }


def map_blocking(stats: dict[str, int]) -> bool:
    return any(stats[key] for key in ("missing_source_ids", "extra_source_ids", "missing_canonical", "unresolved_canonical", "duplicate_source_ids", "duplicate_canonical_ids")) or stats["reviewed"] == 0


def reviewed_map_source_ids(map_rows: list[dict[str, str]], source_ids: set[str], canonical_ids: set[str]) -> set[str]:
    return {
        row.get("source_id", "")
        for row in map_rows
        if row.get("review_status", "").lower() in REVIEWED
        and row.get("source_id", "") in source_ids
        and row.get("canonical_id", "") in canonical_ids
    }


def zip_members(path: Path) -> tuple[set[str], str]:
    if not path.exists():
        return set(), "missing_archive"
    try:
        with zipfile.ZipFile(path) as archive:
            return set(archive.namelist()), "present"
    except zipfile.BadZipFile as exc:
        raise DatasetAuditError(f"Malformed ZIP archive: {path}: {exc}") from exc


def archive_membership(rows: list[dict[str, str]], archive: Path, member_key: str) -> tuple[str, str, str, bool]:
    members, archive_status = zip_members(archive)
    expected = [note_value(row.get("notes", ""), member_key) for row in rows]
    expected = [value for value in expected if value]
    if archive_status == "missing_archive":
        return "warn_archive_not_checked", "warning", f"expected_members={len(expected)}; archive_status=missing", False
    missing = [value for value in expected if value not in members]
    if missing:
        return "fail_missing_archive_members", "error", f"expected_members={len(expected)}; archive_members={len(members)}; missing_members={len(missing)}", True
    return "pass", "info", f"expected_members={len(expected)}; archive_members={len(members)}; missing_members=0", False


def rbpbase_phages(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if "phage_ID" not in (reader.fieldnames or []):
            raise DatasetAuditError(f"RBPbase is missing phage_ID column: {path}")
        return {normalize(row.get("phage_ID")) for row in reader if not is_missing(row.get("phage_ID"))}


def json_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetAuditError(f"Invalid JSON input: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DatasetAuditError(f"Expected JSON object keyed by source ID: {path}")
    return {normalize(key) for key in data if not is_missing(key)}


def assay_stats(path: Path, phage_ids: set[str] | None = None, host_ids: set[str] | None = None) -> dict[str, int]:
    _fields, rows = read_tsv(path)
    interaction_ids: list[str] = []
    stats = {
        "rows": len(rows),
        "tested": 0,
        "tested_false": 0,
        "positive": 0,
        "negative": 0,
        "productive_measured": 0,
        "unresolved_phage_ids": 0,
        "unresolved_host_ids": 0,
        "duplicate_interaction_ids": 0,
    }
    for row in rows:
        interaction_id = row.get("interaction_id", "")
        if not is_missing(interaction_id):
            interaction_ids.append(interaction_id)
        if row.get("tested") == "true":
            stats["tested"] += 1
        else:
            stats["tested_false"] += 1
        if row.get("spot_result") == "positive":
            stats["positive"] += 1
        if row.get("spot_result") == "negative":
            stats["negative"] += 1
        if row.get("productive_infection_result") not in {"", "NA", "not_measured"}:
            stats["productive_measured"] += 1
        if phage_ids is not None and row.get("phage_id", "") not in phage_ids:
            stats["unresolved_phage_ids"] += 1
        if host_ids is not None and row.get("host_id", "") not in host_ids:
            stats["unresolved_host_ids"] += 1
    stats["duplicate_interaction_ids"] = len(interaction_ids) - len(set(interaction_ids))
    return stats


def assay_matrix_parity(assay: dict[str, int], matrix_counts: dict[str, int]) -> tuple[bool, str]:
    checks = {
        "canonical_rows": assay["rows"],
        "expected_canonical_rows": matrix_counts["tested"],
        "spot_positive": assay["positive"],
        "expected_spot_positive": matrix_counts["positive"],
        "spot_negative": assay["negative"],
        "expected_spot_negative": matrix_counts["negative"],
        "tested_false": assay["tested_false"],
        "productive_infection_measured": assay["productive_measured"],
        "unresolved_phage_ids": assay["unresolved_phage_ids"],
        "unresolved_host_ids": assay["unresolved_host_ids"],
        "duplicate_interaction_ids": assay["duplicate_interaction_ids"],
        "unsupported_matrix_values": 0,
        "blank_matrix_cells": matrix_counts["blank"],
    }
    ok = (
        checks["canonical_rows"] == checks["expected_canonical_rows"]
        and checks["spot_positive"] == checks["expected_spot_positive"]
        and checks["spot_negative"] == checks["expected_spot_negative"]
        and checks["tested_false"] == 0
        and checks["productive_infection_measured"] == 0
        and checks["unresolved_phage_ids"] == 0
        and checks["unresolved_host_ids"] == 0
        and checks["duplicate_interaction_ids"] == 0
        and checks["unsupported_matrix_values"] == 0
        and checks["blank_matrix_cells"] > 0
    )
    return ok, "; ".join(f"{key}={value}" for key, value in checks.items())


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    audit_rows: list[dict[str, str]] = []

    file_manifest = resolve(root, args.file_manifest)
    matrix = resolve(root, args.matrix)
    phage_archive = resolve(root, args.phage_archive)
    host_archive = resolve(root, args.host_archive)
    rbpbase = resolve(root, args.rbpbase)
    locibase = resolve(root, args.locibase)
    locibase_invitro = resolve(root, args.locibase_invitro)
    phage_export = resolve(root, args.phage_export)
    host_export = resolve(root, args.host_export)
    phage_map = resolve(root, args.phage_map)
    host_map = resolve(root, args.host_map)
    assay_export = resolve(root, args.assay_export)

    status, severity, summary, blocking = audit_file_manifest(root, file_manifest)
    add_row(audit_rows, "PHLDS001", "external_file_integrity", "identity_ready", status, severity, blocking, display(root, file_manifest), summary, "Acquire missing local files only when regenerating reviewed benchmark artifacts; do not download during CI.")

    matrix_available = matrix.exists()
    matrix_phages, matrix_hosts, matrix_counts = read_matrix(matrix)
    matrix_present = bool(matrix_phages and matrix_hosts)
    matrix_status = "pass" if matrix_present else "warn_matrix_not_available"
    add_row(audit_rows, "PHLDS002", "matrix_id_coverage", "assay_ready", matrix_status, "info" if matrix_present else "warning", False, display(root, matrix), "; ".join(f"{k}={v}" for k, v in matrix_counts.items()), "Keep blank matrix cells as untested; normalize only explicit 1/0 cells. Clean-checkout seed runs may rely on the reviewed assay export when the raw external matrix is untracked.")

    _phage_fields, phage_rows = read_tsv(phage_export, required=True)
    _host_fields, host_rows = read_tsv(host_export, required=True)
    _phage_map_fields, phage_map_rows = read_tsv(phage_map, required=True)
    _host_map_fields, host_map_rows = read_tsv(host_map, required=True)

    phage_exports = export_by_source(phage_rows)
    host_exports = export_by_source(host_rows)
    reviewed_phage_ids = reviewed_export_ids(phage_rows)
    reviewed_host_ids = reviewed_export_ids(host_rows)

    add_row(audit_rows, "PHLDS003", "source_entity_exports", "identity_ready", "pass" if reviewed_phage_ids and reviewed_host_ids else "blocked_no_reviewed_entities", "info" if reviewed_phage_ids and reviewed_host_ids else "warning", not (reviewed_phage_ids and reviewed_host_ids), f"{display(root, phage_export)};{display(root, host_export)}", f"phage_rows={len(phage_rows)}; reviewed_phages={len(reviewed_phage_ids)}; host_rows={len(host_rows)}; reviewed_hosts={len(reviewed_host_ids)}", "Reviewed source identity is sufficient for assay preservation; K/O/ST and RBP evidence are separate feature readiness layers.")

    phage_archive_status, phage_archive_severity, phage_archive_summary, phage_archive_blocking = archive_membership([row for row in phage_rows if note_value(row.get("notes", ""), "review_status").lower() in REVIEWED], phage_archive, "zip_member")
    add_row(audit_rows, "PHLDS004", "phage_archive_membership", "identity_ready", phage_archive_status, phage_archive_severity, phage_archive_blocking, display(root, phage_archive), phage_archive_summary, "Resolve missing phage archive members before reviewing additional phage identities.")

    host_archive_status, host_archive_severity, host_archive_summary, host_archive_blocking = archive_membership([row for row in host_rows if note_value(row.get("notes", ""), "review_status").lower() in REVIEWED], host_archive, "host_archive_member")
    add_row(audit_rows, "PHLDS005", "host_archive_membership", "identity_ready", host_archive_status, host_archive_severity, host_archive_blocking, display(root, host_archive), host_archive_summary, "Resolve missing host archive members before reviewing additional host identities.")

    phage_canonical_ids = {row.get("genome_id", "") for row in phage_rows if row.get("genome_id")}
    host_canonical_ids = {row.get("genome_id", "") for row in host_rows if row.get("genome_id")}
    phage_map_stats = map_stats(phage_map_rows, set(phage_exports), phage_canonical_ids)
    host_map_stats = map_stats(host_map_rows, set(host_exports), host_canonical_ids)
    phage_map_blocking = map_blocking(phage_map_stats)
    host_map_blocking = map_blocking(host_map_stats)
    map_status = "fail_structural_map" if (phage_map_blocking or host_map_blocking) else ("partial_reviewed_subset" if phage_map_stats["pending"] or host_map_stats["pending"] else "pass")
    add_row(audit_rows, "PHLDS006", "canonical_id_mapping", "identity_ready", map_status, "error" if (phage_map_blocking or host_map_blocking) else ("warning" if map_status == "partial_reviewed_subset" else "info"), phage_map_blocking or host_map_blocking, f"{display(root, phage_map)};{display(root, host_map)}", f"phage_map={phage_map_stats}; host_map={host_map_stats}", "Use deterministic source-to-canonical mappings for unambiguous rows; manual review is only needed for conflicting aliases or unresolved IDs.")

    rbpbase_ids = rbpbase_phages(rbpbase)
    locibase_ids = json_keys(locibase)
    locibase_invitro_ids = json_keys(locibase_invitro)
    feature_status = "pass_seed_metadata_available" if rbpbase_ids or locibase_ids or locibase_invitro_ids else "warn_no_optional_feature_metadata"
    add_row(audit_rows, "PHLDS007", "feature_metadata_availability", "feature_ready", feature_status, "info" if feature_status.startswith("pass") else "warning", False, f"{display(root, rbpbase)};{display(root, locibase)};{display(root, locibase_invitro)}", f"rbpbase_phages={len(rbpbase_ids)}; locibase_hosts={len(locibase_ids)}; locibase_invitro_hosts={len(locibase_invitro_ids)}; reviewed_phage_overlap={len(reviewed_phage_ids & rbpbase_ids)}; reviewed_host_locus_overlap={len(reviewed_host_ids & (locibase_ids | locibase_invitro_ids))}", "Treat RBPbase/Locibase as seed feature support only; they are not production domain/structural evidence or K/O typing.")

    assay = assay_stats(assay_export, phage_canonical_ids, host_canonical_ids)
    if matrix_available:
        reviewed_matrix_phages = reviewed_map_source_ids(phage_map_rows, set(phage_exports), phage_canonical_ids)
        reviewed_matrix_hosts = reviewed_map_source_ids(host_map_rows, set(host_exports), host_canonical_ids)
        _reviewed_matrix_phages, _reviewed_matrix_hosts, reviewed_matrix_counts = read_matrix(matrix, reviewed_matrix_phages, reviewed_matrix_hosts)
        parity_ok, parity_summary = assay_matrix_parity(assay, reviewed_matrix_counts)
    else:
        parity_ok = (
            assay["rows"] > 0
            and assay["tested_false"] == 0
            and assay["productive_measured"] == 0
            and assay["unresolved_phage_ids"] == 0
            and assay["unresolved_host_ids"] == 0
            and assay["duplicate_interaction_ids"] == 0
            and assay["positive"] > 0
            and assay["negative"] > 0
        )
        parity_summary = (
            f"canonical_rows={assay['rows']}; expected_canonical_rows=not_checked_matrix_unavailable; "
            f"spot_positive={assay['positive']}; expected_spot_positive=not_checked_matrix_unavailable; "
            f"spot_negative={assay['negative']}; expected_spot_negative=not_checked_matrix_unavailable; "
            f"tested_false={assay['tested_false']}; productive_infection_measured={assay['productive_measured']}; "
            f"unresolved_phage_ids={assay['unresolved_phage_ids']}; unresolved_host_ids={assay['unresolved_host_ids']}; "
            f"duplicate_interaction_ids={assay['duplicate_interaction_ids']}; unsupported_matrix_values=not_checked_matrix_unavailable; "
            "blank_matrix_cells=not_checked_matrix_unavailable"
        )
    assay_ready = assay["rows"] > 0 and parity_ok and not (phage_map_blocking or host_map_blocking)
    add_row(audit_rows, "PHLDS008", "assay_import_readiness", "assay_ready", "pass" if assay_ready else "blocked_no_importable_assays", "info" if assay_ready else "warning", not assay_ready, display(root, assay_export), "; ".join(f"{k}={v}" for k, v in assay.items()), "Import explicit tested positives and tested negatives; keep productive_infection_result=not_measured for this spot-test matrix.")

    parity_status = "pass" if parity_ok and matrix_available else ("pass_reviewed_export_only" if parity_ok else "fail_parity_mismatch")
    parity_severity = "info" if parity_ok and matrix_available else ("warning" if parity_ok else "error")
    add_row(audit_rows, "PHLDS009", "assay_matrix_export_parity", "assay_ready", parity_status, parity_severity, not parity_ok, f"{display(root, matrix)};{display(root, assay_export)}", parity_summary, "Blank matrix cells must remain untested and absent from the reviewed assay export; explicit 1/0 cells must match canonical assay rows when the raw matrix is available locally.")

    model_ready = assay_ready and assay["positive"] > 0 and assay["negative"] > 0
    add_row(audit_rows, "PHLDS010", "model_feature_readiness", "model_ready", "seed_spot_breadth_ready" if model_ready else "blocked_no_tested_panel", "warning" if model_ready else "error", not model_ready, display(root, assay_export), f"spot_positive={assay['positive']}; spot_negative={assay['negative']}; productive_measured={assay['productive_measured']}; feature_claim_boundary=seed_initial_interaction_only", "Use spot-test breadth only for H3 initial-interaction summaries; H4 remains blocked until productive-infection/plaque/EOP labels exist.")

    blocking_rows = [row for row in audit_rows if row["blocking_for_assay_import"] == "true"]
    report = [
        {"severity": "info", "item": "phagehostlearn_dataset_audit", "message": f"checks={len(audit_rows)}; blocking_for_assay_import={len(blocking_rows)}"}
    ]
    if blocking_rows:
        report.append({"severity": "warning", "item": "phagehostlearn_dataset_audit", "message": "Dataset still has assay-import blockers."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_dataset_audit", "message": "Dataset has a reviewed assay-importable subset; feature/model claims remain separately gated."})

    write_tsv(resolve(root, args.audit_output), AUDIT_COLUMNS, audit_rows)
    write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn dataset audit complete: checks={len(audit_rows)}; blocking={len(blocking_rows)}.")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except DatasetAuditError as exc:
        root = Path(args.root).resolve()
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "phagehostlearn_dataset_audit", "message": str(exc)}])
        print(f"PhageHostLearn dataset audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
