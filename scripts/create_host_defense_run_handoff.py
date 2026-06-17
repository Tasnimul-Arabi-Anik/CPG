#!/usr/bin/env python3
"""Create a host-defense external-tool handoff from reviewed local host FASTA records."""

from __future__ import annotations

import argparse
import csv
import shlex
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "host_genome_id",
    "host_species",
    "host_strain",
    "accession",
    "raw_sequence_path",
    "raw_sequence_exists",
    "defensefinder_command",
    "padloc_command",
    "output_tsv_target",
    "run_status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create reviewer-facing DefenseFinder/PADLOC run commands for reviewed "
            "host genomes with local FASTA files. This does not run external tools."
        )
    )
    parser.add_argument("--host-metadata", required=True, help="Stage 5 host_metadata.tsv.")
    parser.add_argument("--sequence-plan", required=True, help="Stage 1 sequence_acquisition_plan.tsv.")
    parser.add_argument("--manifest-output", required=True, help="Output host defense run manifest TSV.")
    parser.add_argument("--commands-output", required=True, help="Output shell command file.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
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


def bool_text(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "y"}


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in value).strip("_") or "host"


def display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    report: list[dict[str, str]] = []
    host_fields, host_rows = read_tsv(Path(args.host_metadata))
    sequence_fields, sequence_rows = read_tsv(Path(args.sequence_plan))
    missing_host = [column for column in ["host_genome_id", "host_record_type"] if column not in host_fields]
    missing_sequence = [column for column in ["genome_id", "record_type", "raw_sequence_path", "raw_sequence_exists"] if column not in sequence_fields]
    if missing_host or missing_sequence:
        messages = []
        if missing_host:
            messages.append("host_metadata missing: " + ";".join(missing_host))
        if missing_sequence:
            messages.append("sequence_plan missing: " + ";".join(missing_sequence))
        write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, [])
        Path(args.commands_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.commands_output).write_text("", encoding="utf-8")
        write_tsv(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "host_defense_handoff", "message": " | ".join(messages)}])
        return 1

    sequence_by_id = {row.get("genome_id", ""): row for row in sequence_rows if row.get("record_type") == "host"}
    manifest: list[dict[str, str]] = []
    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated handoff commands. Review tool versions/databases before running.",
        "# Normalize outputs to data/metadata/external_evidence/host_defense_systems.tsv and configure inputs.host_defense_input.",
        "",
    ]
    for host in host_rows:
        if host.get("host_record_type") != "host_genome":
            continue
        host_id = host.get("host_genome_id", "")
        sequence = sequence_by_id.get(host_id, {})
        raw_path_text = sequence.get("raw_sequence_path", "") or sequence.get("resolved_sequence_path", "")
        raw_path = Path(raw_path_text)
        if raw_path_text and not raw_path.is_absolute():
            raw_path = root / raw_path
        exists = bool_text(sequence.get("raw_sequence_exists", "")) and raw_path.exists()
        run_name = safe_name(host_id)
        defensefinder_dir = Path("results/external/defensefinder") / run_name
        padloc_dir = Path("results/external/padloc") / run_name
        output_tsv = "data/metadata/external_evidence/host_defense_systems.tsv"
        if exists:
            fasta_display = display_path(root, raw_path)
            defensefinder_command = f"defense-finder run {shlex.quote(fasta_display)} -o {shlex.quote(defensefinder_dir.as_posix())}"
            padloc_command = f"padloc --fna {shlex.quote(fasta_display)} --outdir {shlex.quote(padloc_dir.as_posix())}"
            commands.extend(
                [
                    f"# Host: {host_id}",
                    defensefinder_command,
                    padloc_command,
                    "",
                ]
            )
            status = "ready_for_external_tool_run"
        else:
            defensefinder_command = ""
            padloc_command = ""
            status = "waiting_for_reviewed_local_fasta"
        manifest.append(
            {
                "host_genome_id": host_id,
                "host_species": host.get("host_species", ""),
                "host_strain": host.get("host_strain", ""),
                "accession": sequence.get("accession", ""),
                "raw_sequence_path": display_path(root, raw_path) if raw_path_text else "",
                "raw_sequence_exists": str(exists).lower(),
                "defensefinder_command": defensefinder_command,
                "padloc_command": padloc_command,
                "output_tsv_target": output_tsv,
                "run_status": status,
                "notes": "Run commands only; no host defense systems are inferred or accepted until reviewed tool output TSV is configured.",
            }
        )
    Path(args.commands_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.commands_output).write_text("\n".join(commands) + "\n", encoding="utf-8")
    write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, manifest)
    ready = sum(1 for row in manifest if row["run_status"] == "ready_for_external_tool_run")
    report.append(
        {
            "severity": "info",
            "item": "host_defense_handoff",
            "message": f"host_genomes={len(manifest)}; ready_for_external_tool_run={ready}",
        }
    )
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
