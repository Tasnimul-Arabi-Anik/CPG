#!/usr/bin/env python3
"""Render a collection packet for the highest-priority source exports."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "source_id",
    "recommended_rank",
    "packet_path",
    "target_database",
    "requires_network",
    "review_mode",
    "web_url",
    "starter_template_path",
    "starter_readme_path",
    "expected_export_path",
    "preflight_status",
    "required_for_hypotheses",
    "validation_command",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create per-source collection READMEs for priority reviewed exports.")
    parser.add_argument("--minimum-source-plan", required=True, help="Minimum source curation plan TSV.")
    parser.add_argument("--source-query-commands", required=True, help="Source query command TSV.")
    parser.add_argument("--starter-kit-manifest", required=True, help="Source export starter kit manifest TSV.")
    parser.add_argument("--preflight", required=True, help="Priority source export preflight TSV.")
    parser.add_argument("--output-dir", required=True, help="Output collection packet directory.")
    parser.add_argument("--manifest-output", required=True, help="Output collection packet manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--max-rank", type=int, default=2, help="Highest rank to include. Defaults to 2.")
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
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


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def by_source(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_id", ""): row for row in rows if row.get("source_id")}


def rank_value(row: dict[str, str]) -> int:
    try:
        return int(row.get("recommended_rank", "999"))
    except ValueError:
        return 999


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value).strip("_") or "source"


def write_packet(path: Path, source: dict[str, str], command: dict[str, str], starter: dict[str, str], preflight: dict[str, str]) -> None:
    content = [
        f"# {source.get('source_id', 'source')} priority collection packet",
        "",
        f"- Recommended rank: `{source.get('recommended_rank', '')}`",
        f"- Record layer: `{source.get('record_layer', '')}`",
        f"- Required for hypotheses: `{source.get('required_for_hypotheses', 'NA')}`",
        f"- Target database: `{command.get('target_database', source.get('target_database', ''))}`",
        f"- Requires network/manual review: `{command.get('requires_network', '')}`",
        f"- Review mode: `{command.get('review_mode', '')}`",
        f"- Web URL: `{command.get('web_url', 'NA') or 'NA'}`",
        f"- Starter template: `{starter.get('starter_template_path', source.get('starter_template_path', ''))}`",
        f"- Starter README: `{starter.get('starter_readme_path', source.get('starter_readme_path', ''))}`",
        f"- Expected reviewed export: `{source.get('expected_export_path', starter.get('expected_export_path', ''))}`",
        f"- Current preflight status: `{preflight.get('preflight_status', 'NA')}`",
        "",
        "## Query Or Collection Command",
        "",
        "```bash",
        command.get("command_text", "# No command text configured; use the query and starter template above."),
        "```",
        "",
        "## Output Contract",
        "",
        command.get("output_contract", "Reviewed TSV matching the starter template and identity fields."),
        "",
        "## Review Checklist",
        "",
        command.get("review_checklist", "Preserve identity columns, remove non-Klebsiella/non-phage contamination when applicable, and record provenance in notes."),
        "",
        "## Preflight Expectations",
        "",
        f"- Identity columns: `{preflight.get('identity_columns_required', source.get('identity_columns_required', ''))}`",
        f"- Recommended metadata checks: `{preflight.get('required_content_checks', 'NA')}`",
        f"- Current next action: `{preflight.get('next_action', source.get('recommended_action', ''))}`",
        "",
        "## Validation Command",
        "",
        "```bash",
        source.get("validation_command", "python scripts/run_workflow.py --config config/workflow.yaml"),
        "```",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(content), encoding="utf-8")


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    minimum_path = resolve(root, args.minimum_source_plan)
    commands_path = resolve(root, args.source_query_commands)
    starter_path = resolve(root, args.starter_kit_manifest)
    preflight_path = resolve(root, args.preflight)
    output_dir = resolve(root, args.output_dir)
    manifest_output = resolve(root, args.manifest_output)
    report_output = resolve(root, args.report_output)

    _, minimum_rows = read_tsv(minimum_path)
    _, command_rows = read_tsv(commands_path)
    _, starter_rows = read_tsv(starter_path)
    _, preflight_rows = read_tsv(preflight_path)
    command_map = by_source(command_rows)
    starter_map = by_source(starter_rows)
    preflight_map = by_source(preflight_rows)

    selected = [row for row in minimum_rows if rank_value(row) <= args.max_rank]
    selected = sorted(selected, key=lambda row: (rank_value(row), row.get("source_id", "")))
    manifest_rows: list[dict[str, str]] = []
    for row in selected:
        source_id = row.get("source_id", "")
        packet_path = output_dir / f"{safe_name(source_id)}.md"
        command = command_map.get(source_id, {})
        starter = starter_map.get(source_id, {})
        preflight = preflight_map.get(source_id, {})
        write_packet(packet_path, row, command, starter, preflight)
        manifest_rows.append({
            "source_id": source_id,
            "recommended_rank": row.get("recommended_rank", ""),
            "packet_path": display_path(root, packet_path),
            "target_database": command.get("target_database", ""),
            "requires_network": command.get("requires_network", ""),
            "review_mode": command.get("review_mode", ""),
            "web_url": command.get("web_url", ""),
            "starter_template_path": starter.get("starter_template_path", row.get("starter_template_path", "")),
            "starter_readme_path": starter.get("starter_readme_path", row.get("starter_readme_path", "")),
            "expected_export_path": row.get("expected_export_path", starter.get("expected_export_path", "")),
            "preflight_status": preflight.get("preflight_status", ""),
            "required_for_hypotheses": row.get("required_for_hypotheses", ""),
            "validation_command": row.get("validation_command", ""),
        })

    index = [
        "# Priority Source Collection Packet",
        "",
        "This packet collects the source-specific instructions needed to create the highest-priority reviewed source exports. It is a curation handoff, not biological evidence.",
        "",
        "| Rank | Source | Packet | Expected export | Preflight status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in manifest_rows:
        index.append(f"| `{row['recommended_rank']}` | `{row['source_id']}` | `{row['packet_path']}` | `{row['expected_export_path']}` | `{row['preflight_status']}` |")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")

    report_rows = [{"severity": "info", "item": "priority_source_collection_packet", "message": f"sources={len(manifest_rows)}; output_dir={display_path(root, output_dir)}; max_rank={args.max_rank}"}]
    if any(row.get("preflight_status") not in {"preflight_ready", "ready_with_warnings"} for row in manifest_rows):
        report_rows.append({"severity": "warning", "item": "priority_source_collection_packet", "message": "One or more priority source exports still need curation before preflight can pass."})
    write_tsv(manifest_output, MANIFEST_COLUMNS, manifest_rows)
    write_tsv(report_output, REPORT_COLUMNS, report_rows)
    print(f"Wrote priority source collection packet for {len(manifest_rows)} sources.")


if __name__ == "__main__":
    main()
