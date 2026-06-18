#!/usr/bin/env python3
"""Audit PhageHostLearn host source IDs against the local host-genome ZIP."""

from __future__ import annotations

import argparse
import csv
import re
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Iterable


AUDIT_COLUMNS = [
    "source_id",
    "genome_id",
    "host_strain",
    "archive_path",
    "archive_present",
    "member_present",
    "member_path",
    "member_size_bytes",
    "member_compressed_size_bytes",
    "status",
    "severity",
    "blocking_for_entity_review",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


class HostArchiveAuditError(Exception):
    """Raised for malformed host archive audit inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PhageHostLearn host source IDs against klebsiella_genomes.zip.")
    parser.add_argument("--host-export", default="data/metadata/source_exports/phagehostlearn_2024_hosts.tsv")
    parser.add_argument("--archive", default="data/metadata/external/phagehostlearn/klebsiella_genomes.zip")
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
        raise HostArchiveAuditError(f"Host export does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def note_value(notes: str, key: str) -> str:
    match = re.search(rf"(?:^|;\s*){re.escape(key)}=([^;]+)", notes)
    return match.group(1).strip() if match else ""


def source_id_for(row: dict[str, str]) -> str:
    return note_value(row.get("notes", ""), "source_id") or normalize(row.get("host_strain"))


def index_archive(path: Path) -> tuple[dict[str, zipfile.ZipInfo], set[str], int]:
    members: dict[str, zipfile.ZipInfo] = {}
    duplicates: set[str] = set()
    fasta_count = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename
            if not name.startswith("fasta_files/") or not name.endswith(".fasta"):
                continue
            if name.startswith("__MACOSX/"):
                continue
            fasta_count += 1
            source_id = Path(name).name.removesuffix(".fasta")
            if source_id in members:
                duplicates.add(source_id)
            else:
                members[source_id] = info
    return members, duplicates, fasta_count


def audit_row(row: dict[str, str], root: Path, archive_label: str, archive_present: bool, member: zipfile.ZipInfo | None, status: str, severity: str, blocking: str, notes: str) -> dict[str, str]:
    return {
        "source_id": source_id_for(row) or "NA",
        "genome_id": row.get("genome_id", "NA") or "NA",
        "host_strain": row.get("host_strain", "NA") or "NA",
        "archive_path": archive_label,
        "archive_present": str(archive_present).lower(),
        "member_present": str(member is not None).lower(),
        "member_path": member.filename if member else "NA",
        "member_size_bytes": str(member.file_size) if member else "NA",
        "member_compressed_size_bytes": str(member.compress_size) if member else "NA",
        "status": status,
        "severity": severity,
        "blocking_for_entity_review": blocking,
        "notes": notes,
    }


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    host_export = resolve(root, args.host_export)
    archive_path = resolve(root, args.archive)
    audit_output = resolve(root, args.audit_output)
    report_output = resolve(root, args.report_output)
    if audit_output.resolve() in {host_export.resolve(), archive_path.resolve(), report_output.resolve()}:
        raise HostArchiveAuditError("audit-output must not overwrite an input or report output")
    if report_output.resolve() in {host_export.resolve(), archive_path.resolve()}:
        raise HostArchiveAuditError("report-output must not overwrite an input")

    fields, host_rows = read_tsv(host_export)
    required = ["genome_id", "host_strain", "notes"]
    missing_columns = [column for column in required if column not in fields]
    if missing_columns:
        raise HostArchiveAuditError("Host export missing columns: " + ";".join(missing_columns))

    archive_label = display(root, archive_path)
    report: list[dict[str, str]] = []
    audit: list[dict[str, str]] = []
    errors = 0

    if not archive_path.exists():
        for row in host_rows:
            audit.append(audit_row(row, root, archive_label, False, None, "archive_missing", "warning", "true", "Host archive is not present locally; retrieve and verify klebsiella_genomes.zip before source-entity review."))
        report.append({"severity": "warning", "item": "host_archive", "message": f"archive_missing={archive_label}; host_rows={len(host_rows)}"})
        report.append({"severity": "info", "item": "claim_boundary", "message": "This audit supports host-source review only; it does not approve map rows or assay outcomes."})
        write_tsv_atomic(audit_output, AUDIT_COLUMNS, audit)
        write_tsv_atomic(report_output, REPORT_COLUMNS, report)
        print(f"PhageHostLearn host archive audit complete: rows={len(audit)}; errors=0.")
        return 0

    try:
        members, duplicate_members, fasta_count = index_archive(archive_path)
    except zipfile.BadZipFile as exc:
        raise HostArchiveAuditError(f"Host archive is not a readable ZIP: {archive_path}") from exc

    export_ids = [source_id_for(row) for row in host_rows]
    export_id_set = {source_id for source_id in export_ids if not is_missing(source_id)}
    member_id_set = set(members)
    extra_members = sorted(member_id_set - export_id_set)
    duplicate_export_ids = {source_id for source_id, count in Counter(export_ids).items() if not is_missing(source_id) and count > 1}

    for row in host_rows:
        source_id = source_id_for(row)
        if is_missing(source_id):
            errors += 1
            audit.append(audit_row(row, root, archive_label, True, None, "invalid_missing_source_id", "error", "true", "Host export row has no source_id in notes and no host_strain."))
        elif source_id in duplicate_export_ids:
            errors += 1
            audit.append(audit_row(row, root, archive_label, True, None, "invalid_duplicate_source_id", "error", "true", "Source ID appears more than once in the host export."))
        elif source_id in duplicate_members:
            errors += 1
            audit.append(audit_row(row, root, archive_label, True, members.get(source_id), "duplicate_archive_member", "error", "true", "More than one FASTA member has this source ID basename."))
        elif source_id in members:
            audit.append(audit_row(row, root, archive_label, True, members[source_id], "sequence_member_present", "info", "false", "Host source ID has a FASTA member in klebsiella_genomes.zip."))
        else:
            audit.append(audit_row(row, root, archive_label, True, None, "sequence_member_missing", "warning", "true", "Host source ID is present in the assay matrix/export but has no FASTA member in klebsiella_genomes.zip."))

    counts = Counter(row["status"] for row in audit)
    severities = Counter(row["severity"] for row in audit)
    report.append({"severity": "info", "item": "host_archive", "message": f"archive_present=true; host_rows={len(host_rows)}; fasta_members={fasta_count}; matched={counts.get('sequence_member_present', 0)}; missing={counts.get('sequence_member_missing', 0)}; extra_members={len(extra_members)}"})
    for status, count in sorted(counts.items()):
        severity = "error" if any(row["status"] == status and row["severity"] == "error" for row in audit) else "warning" if any(row["status"] == status and row["severity"] == "warning" for row in audit) else "info"
        report.append({"severity": severity, "item": status, "message": f"{count} row(s)."})
    if extra_members:
        report.append({"severity": "warning", "item": "archive_members_not_in_export", "message": ";".join(extra_members[:25]) + (";..." if len(extra_members) > 25 else "")})
    report.append({"severity": "info", "item": "claim_boundary", "message": "This audit supports host-source review only; it does not approve map rows or assay outcomes."})

    write_tsv_atomic(audit_output, AUDIT_COLUMNS, audit)
    write_tsv_atomic(report_output, REPORT_COLUMNS, report)
    print(f"PhageHostLearn host archive audit complete: rows={len(audit)}; errors={errors}.")
    return 1 if errors else 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except HostArchiveAuditError as exc:
        write_tsv_atomic(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "phagehostlearn_host_archive", "message": str(exc)}])
        print(f"PhageHostLearn host archive audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
