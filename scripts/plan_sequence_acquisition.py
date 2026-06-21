#!/usr/bin/env python3
"""Plan local genome sequence acquisition from the Stage 1 manifest."""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from pathlib import Path
from typing import Iterable


PLAN_COLUMNS = [
    "genome_id",
    "record_type",
    "accession",
    "source",
    "validation_status",
    "raw_sequence_path",
    "resolved_sequence_path",
    "raw_sequence_exists",
    "expected_sequence_path",
    "acquisition_needed",
    "acquisition_status",
    "retrieval_method",
    "suggested_command",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


class SequencePlanError(Exception):
    """Raised for invalid sequence acquisition planning inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan local sequence acquisition from a Stage 1 manifest.")
    parser.add_argument("--manifest", required=True, help="Stage 1 phage_genome_manifest.tsv.")
    parser.add_argument("--raw-directory", default="data/raw/genomes", help="Directory for expected downloaded FASTA files.")
    parser.add_argument("--plan-output", required=True, help="Output sequence acquisition plan TSV.")
    parser.add_argument("--report-output", required=True, help="Output sequence acquisition report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise SequencePlanError(f"Manifest does not exist: {path}")
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


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def split_archive_locator(value: str) -> tuple[str, str] | None:
    if "::" not in value:
        return None
    archive_path, member = value.split("::", 1)
    archive_path = archive_path.strip()
    member = member.strip()
    if not archive_path or not member:
        return None
    return archive_path, member


def safe_archive_member(member: str) -> bool:
    member_path = Path(member)
    return not member_path.is_absolute() and ".." not in member_path.parts


def raw_sequence_availability(root: Path, raw_path: str) -> tuple[bool, str, str]:
    locator = split_archive_locator(raw_path)
    if locator:
        archive_text, member = locator
        archive_path = resolve_path(root, archive_text)
        display = f"{display_path(root, archive_path)}::{member}"
        if not safe_archive_member(member):
            return False, display, "unsafe_archive_member"
        if not archive_path.exists():
            return False, display, "archive_missing"
        try:
            with zipfile.ZipFile(archive_path) as archive:
                if member in archive.namelist():
                    return True, display, "archive_member_available"
        except zipfile.BadZipFile:
            return False, display, "invalid_archive"
        return False, display, "archive_member_missing"
    resolved = resolve_path(root, raw_path)
    return resolved.exists(), display_path(root, resolved), "local_path_available" if resolved.exists() else "local_path_missing"


def display_path(root: Path, path: Path | str) -> str:
    path_obj = Path(path)
    if not str(path_obj):
        return ""
    try:
        return path_obj.relative_to(root).as_posix()
    except ValueError:
        return path_obj.as_posix()


def safe_name(value: str, fallback: str) -> str:
    text = value if not is_missing(value) else fallback
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return text or "genome"


def split_accessions(value: str) -> list[str]:
    if is_missing(value):
        return []
    parts = [part.strip() for part in re.split(r"[;,\s]+", value) if part.strip()]
    return [part for part in parts if part not in MISSING]


def accession_kind(accession: str) -> str:
    upper = accession.upper()
    if upper.startswith(("GCA_", "GCF_")):
        return "assembly"
    if upper.startswith(("SAMN", "SAME", "SAMD", "SAMR")):
        return "biosample"
    if upper.startswith(("SRR", "ERR", "DRR")):
        return "reads"
    return "nuccore"


def expected_path(root: Path, raw_dir: Path, row: dict[str, str], accession: str) -> Path:
    genome_id = row.get("genome_id", "")
    name = safe_name(genome_id, accession)
    return raw_dir / f"{name}.fna"


def command_for(accession: str, target: Path, root: Path) -> tuple[str, str]:
    kind = accession_kind(accession)
    target_text = display_path(root, target)
    if kind == "assembly":
        zip_path = target.with_suffix(".zip")
        return (
            "ncbi_datasets_genome",
            f"datasets download genome accession {accession} --include genome --filename {display_path(root, zip_path)}",
        )
    if kind == "reads":
        return (
            "sra_prefetch_fasterq",
            f"prefetch {accession} --output-directory data/raw/sra && fasterq-dump data/raw/sra/{accession} --outdir data/raw/sra/{accession}",
        )
    if kind == "biosample":
        return (
            "metadata_link_required",
            "Resolve BioSample to assembly or nucleotide accession before FASTA retrieval.",
        )
    return (
        "ncbi_edirect_nuccore",
        f"efetch -db nuccore -id {accession} -format fasta > {target_text}",
    )


def plan_one(row: dict[str, str], root: Path, raw_dir: Path) -> dict[str, str]:
    genome_id = row.get("genome_id", "")
    record_type = row.get("record_type", "")
    accession = row.get("accession", "")
    source = row.get("source", "")
    raw_path = row.get("raw_sequence_path", "")
    validation_status = row.get("validation_status", "")
    notes = row.get("notes", "")

    has_raw_path = not is_missing(raw_path)
    raw_exists, resolved_text, availability_status = raw_sequence_availability(root, raw_path) if has_raw_path else (False, "", "no_raw_sequence_path")
    resolved = resolve_path(root, raw_path.split("::", 1)[0]) if has_raw_path else Path("")
    accessions = split_accessions(accession)
    primary_accession = accessions[0] if accessions else ""
    expected = expected_path(root, raw_dir, row, primary_accession) if primary_accession else Path("")

    if validation_status == "exclude":
        status = "excluded_manifest_record"
        needed = "false"
        method = "none"
        command = ""
        next_notes = "Manifest validation excluded this record."
    elif raw_exists:
        status = "local_sequence_available"
        needed = "false"
        method = "none"
        command = ""
        next_notes = "Reviewed ZIP archive member exists." if availability_status == "archive_member_available" else "Local raw_sequence_path exists."
    elif not is_missing(raw_path) and not raw_exists and primary_accession:
        status = "configured_path_missing_fetchable"
        needed = "true"
        method, command = command_for(primary_accession, resolved, root)
        next_notes = "raw_sequence_path is set but missing; fetch or place the sequence at that path."
    elif not is_missing(raw_path) and not raw_exists:
        status = "configured_path_missing_no_accession"
        needed = "true"
        method = "manual_sequence_file"
        command = "Place reviewed FASTA at " + display_path(root, resolved)
        next_notes = "raw_sequence_path is set but missing and no accession is available."
    elif primary_accession:
        status = "accession_ready_for_fetch"
        needed = "true"
        method, command = command_for(primary_accession, expected, root)
        next_notes = "No raw_sequence_path is set; use accession to retrieve or place FASTA at expected path."
    else:
        status = "metadata_only_no_accession"
        needed = "true"
        method = "manual_accession_or_sequence_required"
        command = "Add accession or raw_sequence_path to the source manifest."
        next_notes = "Record cannot be sequence-backed until accession or raw_sequence_path is curated."

    return {
        "genome_id": genome_id,
        "record_type": record_type,
        "accession": accession,
        "source": source,
        "validation_status": validation_status,
        "raw_sequence_path": raw_path,
        "resolved_sequence_path": resolved_text if has_raw_path else "",
        "raw_sequence_exists": str(raw_exists).lower(),
        "expected_sequence_path": display_path(root, expected) if primary_accession else "",
        "acquisition_needed": needed,
        "acquisition_status": status,
        "retrieval_method": method,
        "suggested_command": command,
        "notes": next_notes if is_missing(notes) else notes + "; " + next_notes,
    }


def plan_sequences(manifest: Path, root: Path, raw_directory: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fieldnames, rows = read_tsv(manifest)
    report: list[dict[str, str]] = []
    if "genome_id" not in fieldnames:
        raise SequencePlanError("Manifest is missing required column: genome_id")
    raw_dir = raw_directory if raw_directory.is_absolute() else root / raw_directory
    plan = [plan_one(row, root, raw_dir) for row in rows]
    if not rows:
        add_report(report, "info", "manifest", "No manifest rows found; sequence acquisition plan contains headers only.")
    status_counts: dict[str, int] = {}
    for row in plan:
        status = row["acquisition_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    add_report(report, "info", "records", f"Planned sequence acquisition for {len(plan)} manifest records.")
    for status, count in sorted(status_counts.items()):
        severity = "info" if status == "local_sequence_available" else "warning"
        add_report(report, severity, status, f"{count} record(s).")
    missing = sum(1 for row in plan if row["acquisition_needed"] == "true")
    if missing:
        add_report(report, "warning", "sequence_acquisition_needed", f"{missing} record(s) need accession curation or local sequence files before production sequence QC.")
    return plan, report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        plan, report = plan_sequences(Path(args.manifest), root, Path(args.raw_directory))
        write_tsv(Path(args.plan_output), PLAN_COLUMNS, plan)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        warnings = sum(1 for row in report if row.get("severity") == "warning")
        errors = sum(1 for row in report if row.get("severity") == "error")
        print(f"Sequence acquisition plan complete: {len(plan)} records, {errors} errors, {warnings} warnings.")
        return 1 if errors else 0
    except (SequencePlanError, FileNotFoundError) as exc:
        report = [{"severity": "error", "item": "sequence_acquisition", "message": str(exc)}]
        write_tsv(Path(args.plan_output), PLAN_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        print(f"Sequence acquisition plan failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
