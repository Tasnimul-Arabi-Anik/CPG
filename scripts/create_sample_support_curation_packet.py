#!/usr/bin/env python3
"""Render curation packets from sample-support bridge and export preflight outputs."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "source_id",
    "packet_path",
    "recommended_rank",
    "expected_export_path",
    "blocked_metrics",
    "fields_to_populate",
    "required_for_hypotheses",
    "blocking_preflight_rows",
    "ready_preflight_rows",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create source curation packets for sample-support blockers.")
    parser.add_argument("--bridge", required=True, help="sample_support_source_bridge.tsv.")
    parser.add_argument("--preflight", required=True, help="sample_support_export_preflight.tsv.")
    parser.add_argument("--output-dir", required=True, help="Output packet directory.")
    parser.add_argument("--manifest-output", required=True, help="Output packet manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    values: list[str] = []
    for token in value.replace(",", ";").split(";"):
        token = token.strip()
        if token and token not in values:
            values.append(token)
    return values


def join(values: Iterable[str]) -> str:
    cleaned: list[str] = []
    for value in values:
        if not is_missing(value) and value not in cleaned:
            cleaned.append(value)
    return ";".join(cleaned) if cleaned else "NA"


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


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_") or "source"


def parse_rank(value: str) -> int:
    try:
        return int(float(value))
    except ValueError:
        return 999


def by_source_metric(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        out[(row.get("source_id", ""), row.get("metric", ""))] = row
    return out


def checkbox(done: bool, text: str) -> str:
    return f"- [{'x' if done else ' '}] {text}"


def packet_text(source_id: str, bridge_rows: list[dict[str, str]], preflight_by_metric: dict[tuple[str, str], dict[str, str]]) -> str:
    first = bridge_rows[0]
    export_path = first.get("expected_export_path", "NA")
    rank = first.get("recommended_rank", "NA")
    hypotheses = join(h for row in bridge_rows for h in split_values(row.get("required_for_hypotheses", "")))
    fields = join(field for row in bridge_rows for field in split_values(row.get("fields_to_populate", "")))
    lines = [
        f"# Sample-Support Curation Packet: {source_id}",
        "",
        f"- Recommended rank: `{rank}`",
        f"- Expected reviewed export: `{export_path}`",
        f"- Required for hypotheses: `{hypotheses}`",
        f"- Metric-critical fields: `{fields}`",
        "",
        "## Why This Source Matters",
        "",
        "The rows below come from `sample_support_source_bridge.tsv` and `sample_support_export_preflight.tsv`. They explain which sample-support metrics this source can repair before H1-H6 interpretation.",
        "",
        "| Metric | Status | Satisfying rows | Fields to populate | Rationale |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in bridge_rows:
        metric = row.get("metric", "")
        preflight = preflight_by_metric.get((source_id, metric), {})
        lines.append(
            "| "
            + " | ".join([
                f"`{metric}`",
                f"`{preflight.get('preflight_status', 'NA')}`",
                f"`{preflight.get('satisfying_row_count', 'NA')}`",
                f"`{row.get('fields_to_populate', 'NA')}`",
                row.get("support_rationale", "NA").replace("|", "/"),
            ])
            + " |"
        )
    lines.extend([
        "",
        "## Checklist",
        "",
        checkbox(False, f"Create or update reviewed export `{export_path}`."),
        checkbox(False, "Populate at least one identity field per row, such as genome_id, accession, or raw_sequence_path when present in the template."),
        checkbox(False, "Populate metric-critical host fields such as host_species, K_type, O_type, and ST where required by the metrics above."),
        checkbox(False, "Rerun source validation and sample-support preflight."),
        "",
        "## Rerun Commands",
        "",
        "```bash",
        "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_curation_tasks stage_0_samples stage_0_sample_support stage_0_sample_support_sources stage_0_sample_support_export_preflight",
        "```",
        "",
        "For a full downstream refresh after source curation:",
        "",
        "```bash",
        "python scripts/run_workflow.py --config config/workflow.yaml",
        "```",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    _, bridge_rows = read_tsv(resolve(root, args.bridge))
    _, preflight_rows = read_tsv(resolve(root, args.preflight))
    preflight_by_metric = by_source_metric(preflight_rows)
    output_dir = resolve(root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in bridge_rows:
        grouped[row.get("source_id", "")].append(row)

    manifest_rows: list[dict[str, str]] = []
    for source_id, rows in sorted(grouped.items(), key=lambda item: (parse_rank(item[1][0].get("recommended_rank", "999")), item[0])):
        packet_path = output_dir / f"{slug(source_id)}.md"
        packet_path.write_text(packet_text(source_id, rows, preflight_by_metric), encoding="utf-8")
        preflight_for_source = [row for row in preflight_rows if row.get("source_id") == source_id]
        blocking = [row for row in preflight_for_source if row.get("blocking_issue") == "true"]
        ready = [row for row in preflight_for_source if row.get("preflight_status") == "metric_support_ready"]
        manifest_rows.append({
            "source_id": source_id,
            "packet_path": display_path(root, packet_path),
            "recommended_rank": rows[0].get("recommended_rank", ""),
            "expected_export_path": rows[0].get("expected_export_path", ""),
            "blocked_metrics": join(row.get("metric", "") for row in blocking),
            "fields_to_populate": join(field for row in rows for field in split_values(row.get("fields_to_populate", ""))),
            "required_for_hypotheses": join(h for row in rows for h in split_values(row.get("required_for_hypotheses", ""))),
            "blocking_preflight_rows": str(len(blocking)),
            "ready_preflight_rows": str(len(ready)),
            "next_action": "Populate reviewed export and rerun sample-support preflight." if blocking else "No sample-support export preflight action required.",
        })

    index_lines = [
        "# Sample-Support Curation Packet",
        "",
        "This packet is generated from sample-support bridge and preflight outputs. It is a reviewed-export handoff, not biological evidence.",
        "",
        "| Rank | Source | Blocked metrics | Export | Packet |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in manifest_rows:
        index_lines.append(f"| `{row['recommended_rank']}` | `{row['source_id']}` | `{row['blocked_metrics']}` | `{row['expected_export_path']}` | [{Path(row['packet_path']).name}]({Path(row['packet_path']).name}) |")
    (output_dir / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    report_rows = [
        {"severity": "info", "item": "sample_support_curation_packet", "message": f"sources={len(manifest_rows)}; output_dir={display_path(root, output_dir)}"}
    ]
    if any(row.get("blocking_preflight_rows") != "0" for row in manifest_rows):
        report_rows.append({"severity": "warning", "item": "sample_support_curation_packet", "message": "One or more source packets still have blocking sample-support preflight rows."})

    write_tsv(resolve(root, args.manifest_output), MANIFEST_COLUMNS, manifest_rows)
    write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote sample-support curation packets for {len(manifest_rows)} sources.")


if __name__ == "__main__":
    main()
