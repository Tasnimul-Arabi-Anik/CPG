#!/usr/bin/env python3
"""Create human-readable reviewed-export curation packets from source task rows."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "source_id",
    "packet_path",
    "expected_export_path",
    "template_path",
    "manifest_path",
    "priority",
    "curation_status",
    "blocking_for_real_study",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Markdown curation packets from source_curation_tasks.tsv.")
    parser.add_argument("--tasks", required=True, help="Source curation tasks TSV.")
    parser.add_argument("--output-dir", required=True, help="Directory for README.md and per-source Markdown packets.")
    parser.add_argument("--manifest-output", required=True, help="Packet manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Packet report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "source"


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def split_semicolon(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def bullet_list(values: list[str]) -> str:
    if not values:
        return "- NA"
    return "\n".join(f"- `{value}`" for value in values)


def checkbox(done: bool, text: str) -> str:
    return f"- [{'x' if done else ' '}] {text}"


def packet_text(row: dict[str, str]) -> str:
    export_ready = row.get("export_status") == "export_ready"
    import_enabled = row.get("import_enabled") == "true"
    catalog_enabled = row.get("catalog_enabled") == "true"
    ready = row.get("curation_status") == "ready_for_sample_build"
    required_columns = split_semicolon(row.get("required_export_columns", ""))
    identity_columns = split_semicolon(row.get("identity_columns_required", ""))
    lines = [
        f"# Source Curation Packet: {row.get('source_id', 'source')}",
        "",
        "## Purpose",
        "",
        f"Record layer: `{row.get('record_layer', 'NA')}`",
        f"Priority: `{row.get('priority', 'NA')}`",
        f"Target database/source: `{row.get('target_database', 'NA')}`",
        "",
        "## Local Files",
        "",
        f"- Reviewed export to populate: `{row.get('expected_export_path', 'NA')}`",
        f"- Generated template: `{row.get('template_path', 'NA')}`",
        f"- Normalized manifest: `{row.get('manifest_path', 'NA')}`",
        "",
        "## Query Or Curation Definition",
        "",
        row.get("query_string", "NA") or "NA",
        "",
        "## Required Export Columns",
        "",
        bullet_list(required_columns),
        "",
        "## Identity Columns",
        "",
        "At least the configured identity fields must be populated enough for import and downstream deduplication.",
        "",
        bullet_list(identity_columns),
        "",
        "## Checklist",
        "",
        checkbox(export_ready, f"Create or update reviewed export `{row.get('expected_export_path', 'NA')}`."),
        checkbox(export_ready, "Export validation passes with required columns and identity fields."),
        checkbox(import_enabled, f"Enable matching import `{row.get('import_id', 'NA')}` in `config/source_imports.yaml` when the export is reviewed."),
        checkbox(catalog_enabled, f"Enable source `{row.get('source_id', 'NA')}` in `config/source_catalog.yaml` after normalized manifest review."),
        checkbox(ready, "Source readiness reports ready for sample building."),
        "",
        "## Current Status",
        "",
        f"- Export status: `{row.get('export_status', 'NA')}`",
        f"- Manifest status: `{row.get('manifest_status', 'NA')}`",
        f"- Curation status: `{row.get('curation_status', 'NA')}`",
        f"- Blocking real study: `{row.get('blocking_for_real_study', 'NA')}`",
        "",
        "## Next Action",
        "",
        row.get("next_action", "NA") or "NA",
        "",
        "## Command Hint",
        "",
        "```bash",
        row.get("command_hint", "NA") or "NA",
        "```",
        "",
        "## Notes",
        "",
        row.get("notes", "NA") or "NA",
        "",
    ]
    return "\n".join(lines)


def index_text(rows: list[dict[str, str]], manifest_rows: list[dict[str, str]]) -> str:
    ready = sum(1 for row in rows if row.get("curation_status") == "ready_for_sample_build")
    blocking = sum(1 for row in rows if row.get("blocking_for_real_study") == "true")
    lines = [
        "# Source Curation Packet",
        "",
        "This folder is generated from `results/qc/source_curation_tasks.tsv`. It is a reviewed-export handoff for moving the real study from planned sources to populated sample rows.",
        "",
        "## Summary",
        "",
        f"- Sources: {len(rows)}",
        f"- Ready for sample build: {ready}",
        f"- Blocking real study: {blocking}",
        "",
        "## Source Packets",
        "",
        "| Source | Priority | Status | Blocking | Packet | Export |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    by_source = {row["source_id"]: row for row in manifest_rows}
    for row in rows:
        source_id = row.get("source_id", "")
        manifest = by_source.get(source_id, {})
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{source_id}`",
                    f"`{row.get('priority', '')}`",
                    f"`{row.get('curation_status', '')}`",
                    f"`{row.get('blocking_for_real_study', '')}`",
                    f"[{Path(manifest.get('packet_path', '')).name}]({Path(manifest.get('packet_path', '')).name})" if manifest.get("packet_path") else "NA",
                    f"`{row.get('expected_export_path', '')}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Standard Rerun",
            "",
            "After adding or reviewing exports, rerun:",
            "",
            "```bash",
            "python scripts/run_workflow.py --config config/workflow.yaml",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    _, rows = read_tsv(Path(args.tasks))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for row in rows:
        source_id = row.get("source_id", "")
        packet_path = output_dir / f"{slug(source_id)}.md"
        packet_path.write_text(packet_text(row), encoding="utf-8")
        manifest_rows.append(
            {
                "source_id": source_id,
                "packet_path": display_path(packet_path),
                "expected_export_path": row.get("expected_export_path", ""),
                "template_path": row.get("template_path", ""),
                "manifest_path": row.get("manifest_path", ""),
                "priority": row.get("priority", ""),
                "curation_status": row.get("curation_status", ""),
                "blocking_for_real_study": row.get("blocking_for_real_study", ""),
                "next_action": row.get("next_action", ""),
            }
        )

    index_path = output_dir / "README.md"
    index_path.write_text(index_text(rows, manifest_rows), encoding="utf-8")
    ready = sum(1 for row in rows if row.get("curation_status") == "ready_for_sample_build")
    blocking = sum(1 for row in rows if row.get("blocking_for_real_study") == "true")
    report = [
        {
            "severity": "info",
            "item": "source_curation_packet",
            "message": f"sources={len(rows)}; ready={ready}; blocking={blocking}; output_dir={display_path(output_dir)}",
        }
    ]
    if blocking:
        report.append(
            {
                "severity": "warning",
                "item": "source_curation_packet",
                "message": "One or more source packets are blocking real study sample generation.",
            }
        )
    write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, manifest_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote {len(manifest_rows)} source curation packets to {output_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
