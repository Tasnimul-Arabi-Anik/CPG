#!/usr/bin/env python3
"""Create a review packet for accession-backed sequence fetch commands."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize sequence_fetch_manifest.tsv into a human-review packet. "
            "This script does not execute commands, does not download sequences, "
            "and does not modify data/raw."
        )
    )
    parser.add_argument("--manifest", required=True, help="Sequence fetch manifest TSV.")
    parser.add_argument("--packet-output", required=True, help="Markdown review packet output.")
    parser.add_argument("--report-output", required=True, help="TSV report output.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames or [], [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def count_by(rows: list[dict[str, str]], column: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get(column, "") or "NA"
        counts[key] = counts.get(key, 0) + 1
    return counts


def command_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("command_class") == "fetch_command"]


def packet_text(rows: list[dict[str, str]], manifest_path: Path) -> str:
    fetch_rows = command_rows(rows)
    class_counts = count_by(rows, "command_class")
    status_counts = count_by(rows, "acquisition_status")
    lines = [
        "# Sequence Fetch Review Packet",
        "",
        "This packet summarizes accession-backed sequence retrieval commands from the sequence fetch manifest.",
        "",
        "Important guardrails:",
        "",
        "- The workflow does not execute these commands.",
        "- This packet does not download sequences and does not modify `data/raw/`.",
        "- Review accessions, target paths, expected source, and provenance before running any command outside the workflow.",
        "- After acquisition, rerun sequence QC before using new FASTA files for dereplication, annotation, or model claims.",
        "",
        f"Manifest: `{manifest_path.as_posix()}`",
        f"Total manifest rows: {len(rows)}",
        f"Ready fetch commands: {len(fetch_rows)}",
        "",
        "## Command Classes",
        "",
        "| command_class | rows |",
        "| --- | ---: |",
    ]
    for key, value in sorted(class_counts.items()):
        lines.append(f"| `{escape_md(key)}` | {value} |")
    lines.extend(["", "## Acquisition Status", "", "| acquisition_status | rows |", "| --- | ---: |"])
    for key, value in sorted(status_counts.items()):
        lines.append(f"| `{escape_md(key)}` | {value} |")
    lines.extend(
        [
            "",
            "## Ready Fetch Commands",
            "",
            "| command_id | genome_id | accession | expected_sequence_path | command |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if not fetch_rows:
        lines.append("| NA | NA | NA | NA | No accession-backed commands are ready. |")
    for row in fetch_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{escape_md(row.get('command_id', ''))}`",
                    escape_md(row.get("genome_id", "")),
                    f"`{escape_md(row.get('accession', ''))}`",
                    f"`{escape_md(row.get('expected_sequence_path', ''))}`",
                    f"`{escape_md(row.get('command_text', ''))}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Post-Acquisition Checks",
            "",
            "After reviewed FASTA files are placed at the expected paths, run:",
            "",
            "```bash",
            "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_1_sequence_qc stage_2_dereplication stage_1_external_evidence_plan stage_7_models stage_9_validation stage_10_study_readiness stage_11_goal_completion_audit",
            "```",
            "",
            "Do not strengthen biological claims until `results/validation/claim_support_audit.tsv` allows the claim level.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    manifest = Path(args.manifest)
    report: list[dict[str, str]] = []
    fieldnames, rows = read_tsv(manifest)
    required = {"command_id", "genome_id", "accession", "command_class", "expected_sequence_path", "command_text"}
    missing = sorted(required - set(fieldnames))
    if not manifest.exists():
        report.append({"severity": "error", "item": "sequence_fetch_review_packet", "message": f"Manifest does not exist: {manifest}"})
    elif missing:
        report.append({"severity": "error", "item": "sequence_fetch_review_packet", "message": "Manifest missing columns: " + ";".join(missing)})
    else:
        fetch_rows = command_rows(rows)
        missing_accession = [row.get("command_id", "") for row in fetch_rows if is_missing(row.get("accession"))]
        missing_target = [row.get("command_id", "") for row in fetch_rows if is_missing(row.get("expected_sequence_path"))]
        report.append({"severity": "info", "item": "sequence_fetch_review_packet", "message": f"rows={len(rows)}; ready_fetch_commands={len(fetch_rows)}"})
        if missing_accession:
            report.append({"severity": "warning", "item": "missing_accession", "message": ";".join(missing_accession)})
        if missing_target:
            report.append({"severity": "warning", "item": "missing_expected_sequence_path", "message": ";".join(missing_target)})
        Path(args.packet_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.packet_output).write_text(packet_text(rows, manifest), encoding="utf-8")

    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row["severity"] == "error")
    if errors:
        Path(args.packet_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.packet_output).write_text("# Sequence Fetch Review Packet\n\nPacket generation failed; see report TSV.\n", encoding="utf-8")
    print(f"Sequence fetch review packet complete: {len(rows)} rows, {errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
