#!/usr/bin/env python3
"""Create a reviewed sequence-fetch manifest and non-executing command script."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "command_id",
    "genome_id",
    "record_type",
    "accession",
    "source",
    "acquisition_status",
    "retrieval_method",
    "raw_sequence_path",
    "resolved_sequence_path",
    "expected_sequence_path",
    "raw_sequence_exists",
    "command_class",
    "command_text",
    "requires_network",
    "requires_manual_review",
    "ready_to_run",
    "next_action",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
FETCHABLE_STATUSES = {"accession_ready_for_fetch", "configured_path_missing_fetchable"}
MANUAL_STATUSES = {"metadata_only_no_accession", "configured_path_missing_no_accession"}


class SequenceFetchError(Exception):
    """Raised when sequence fetch manifest creation cannot proceed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create reviewable sequence fetch commands from sequence_acquisition_plan.tsv.")
    parser.add_argument("--sequence-plan", required=True, help="Sequence acquisition plan TSV.")
    parser.add_argument("--manifest-output", required=True, help="Sequence fetch manifest TSV output.")
    parser.add_argument("--commands-output", required=True, help="Review-only shell command script output.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV output.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


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
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def command_class(row: dict[str, str]) -> tuple[str, str, bool, bool, bool]:
    status = row.get("acquisition_status", "")
    command = row.get("suggested_command", "")
    if status == "local_sequence_available":
        return "already_local", "No action required; local sequence path exists.", False, False, False
    if status in FETCHABLE_STATUSES and command:
        return "fetch_command", "Review accession, target path, and tool availability before running command.", True, True, True
    if status in MANUAL_STATUSES:
        return "manual_curation", command or "Add accession or raw_sequence_path to the source manifest.", False, True, False
    if status == "excluded_manifest_record":
        return "excluded", "No action; manifest validation excluded this record.", False, False, False
    if row.get("acquisition_needed") == "true":
        return "manual_review", command or "Review sequence acquisition plan row.", False, True, False
    return "not_needed", "No sequence acquisition action required.", False, False, False


def build_manifest(sequence_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for index, row in enumerate(sequence_rows, start=1):
        klass, action, requires_network, requires_manual, ready = command_class(row)
        command = row.get("suggested_command", "") if klass == "fetch_command" else ""
        output.append(
            {
                "command_id": f"seq_fetch_{index:05d}",
                "genome_id": row.get("genome_id", ""),
                "record_type": row.get("record_type", ""),
                "accession": row.get("accession", ""),
                "source": row.get("source", ""),
                "acquisition_status": row.get("acquisition_status", ""),
                "retrieval_method": row.get("retrieval_method", ""),
                "raw_sequence_path": row.get("raw_sequence_path", ""),
                "resolved_sequence_path": row.get("resolved_sequence_path", ""),
                "expected_sequence_path": row.get("expected_sequence_path", ""),
                "raw_sequence_exists": row.get("raw_sequence_exists", ""),
                "command_class": klass,
                "command_text": command,
                "requires_network": str(requires_network).lower(),
                "requires_manual_review": str(requires_manual).lower(),
                "ready_to_run": str(ready).lower(),
                "next_action": action,
                "notes": row.get("notes", ""),
            }
        )
    return output


def write_commands(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Review-only sequence retrieval commands generated from sequence_acquisition_plan.tsv.",
        "# The workflow does not execute this script automatically.",
        "# Confirm accessions, output paths, tool availability, and data provenance before running.",
        "",
    ]
    fetch_rows = [row for row in rows if row.get("command_class") == "fetch_command"]
    if not fetch_rows:
        lines.append("# No accession-backed sequence fetch commands are ready in the current plan.")
    for row in fetch_rows:
        lines.extend(
            [
                f"# {row['command_id']} | genome_id={row['genome_id']} | accession={row['accession']} | method={row['retrieval_method']}",
                row.get("command_text", ""),
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_report(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    report: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    for row in rows:
        klass = row.get("command_class", "")
        counts[klass] = counts.get(klass, 0) + 1
    report.append({"severity": "info", "item": "sequence_fetch_manifest", "message": f"Prepared {len(rows)} sequence fetch manifest row(s)."})
    for klass, count in sorted(counts.items()):
        if klass == "fetch_command":
            severity = "warning"
        elif klass in {"manual_curation", "manual_review"}:
            severity = "warning"
        else:
            severity = "info"
        report.append({"severity": severity, "item": klass, "message": f"{count} row(s)."})
    return report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    sequence_plan = Path(args.sequence_plan)
    sequence_plan = sequence_plan if sequence_plan.is_absolute() else root / sequence_plan
    fieldnames, sequence_rows = read_tsv(sequence_plan)
    if not sequence_plan.exists():
        write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "sequence_fetch_manifest", "message": f"Sequence acquisition plan does not exist: {sequence_plan}"}])
        print(f"Sequence fetch manifest failed: missing plan {sequence_plan}")
        return 1
    required = {"genome_id", "acquisition_status", "suggested_command"}
    missing = sorted(required - set(fieldnames))
    if missing:
        write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "sequence_fetch_manifest", "message": "Sequence acquisition plan missing columns: " + ";".join(missing)}])
        print("Sequence fetch manifest failed: missing required columns")
        return 1
    manifest_rows = build_manifest(sequence_rows)
    manifest_output = Path(args.manifest_output)
    commands_output = Path(args.commands_output)
    report_output = Path(args.report_output)
    write_tsv(manifest_output, MANIFEST_COLUMNS, manifest_rows)
    write_commands(commands_output, manifest_rows)
    write_tsv(report_output, REPORT_COLUMNS, build_report(manifest_rows))
    print(f"Sequence fetch manifest complete: {len(manifest_rows)} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
