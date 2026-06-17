#!/usr/bin/env python3
"""Render source curation work orders as per-source Markdown packets."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "work_order_id",
    "source_id",
    "packet_path",
    "expected_export_path",
    "minimum_rows_to_add",
    "required_fields",
    "curation_priority",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Markdown packets for source curation work orders.")
    parser.add_argument("--work-orders", required=True, help="source_curation_work_order.tsv.")
    parser.add_argument("--starter-kit-manifest", required=True, help="source_export_starter_kit_manifest.tsv.")
    parser.add_argument("--dashboard", required=True, help="source_readiness_dashboard.tsv.")
    parser.add_argument("--output-dir", required=True, help="Output packet directory.")
    parser.add_argument("--manifest-output", required=True, help="Output packet manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative output paths.")
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


def by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key)}


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "source"


def rel_or_abs(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def bullet_list(values: list[str]) -> str:
    if not values:
        return "- NA"
    return "\n".join(f"- `{value}`" for value in values)


def field_checklist(required_fields: list[str], identity_columns: list[str]) -> str:
    lines = [
        "- [ ] Add one reviewed row per genome, contig, prophage, or host record represented by this source.",
        "- [ ] Keep the full export header unchanged and do not add undocumented columns.",
    ]
    for field in required_fields:
        lines.append(f"- [ ] Populate `{field}` with a non-missing reviewed value for each row needed by this work order.")
    if identity_columns:
        lines.append(f"- [ ] Populate at least one identity field per row: `{';'.join(identity_columns)}`.")
    lines.extend([
        "- [ ] Record provenance, snapshot date, DOI/PMID, accession source, or curation uncertainty in `notes` when available.",
        "- [ ] Leave unknown biological metadata as `NA`; do not infer K/O/ST, lifestyle, or host traits without evidence.",
        "- [ ] If `raw_sequence_path` is populated, point only to a reviewed local FASTA/GenBank path; do not create or overwrite raw files in this step.",
        "- [ ] Rerun the acceptance command below and confirm this work order no longer has `blocking_issue=true`.",
    ])
    return "\n".join(lines)


def export_header_code(columns: list[str]) -> str:
    if not columns:
        return "NA"
    return "\t".join(columns)


def markdown_packet(work: dict[str, str], starter: dict[str, str], dashboard: dict[str, str]) -> str:
    required_fields = split_values(work.get("required_fields", ""))
    blocked_metrics = split_values(work.get("blocked_metrics", ""))
    required_columns = split_values(starter.get("required_columns", ""))
    identity_columns = split_values(starter.get("identity_columns_required", ""))
    return f"""# {work.get('work_order_id', 'work_order')} {work.get('source_id', 'source')}

## Curation Target

- Source ID: `{work.get('source_id', 'NA')}`
- Record layer: `{work.get('record_layer', 'NA')}`
- Required for hypotheses: `{work.get('required_for_hypotheses', 'NA')}`
- Reviewed export path: `{work.get('expected_export_path', 'NA')}`
- Minimum reviewed rows to add: `{work.get('minimum_rows_to_add', '0')}`
- Current export rows: `{work.get('current_export_rows', '0')}`
- Current satisfying rows: `{work.get('current_satisfying_rows', '0')}`

## Required Fields For This Work Order

{bullet_list(required_fields)}

## Blocked Sample-Support Metrics

{bullet_list(blocked_metrics)}

## Full Export Header Expected For This Source

{bullet_list(required_columns)}

## Identity Columns

At least one identity value must be populated for each reviewed row. Preferred identity fields:

{bullet_list(identity_columns)}

## Reviewed Row Entry Checklist

{field_checklist(required_fields, identity_columns)}

## Export Header To Preserve

```tsv
{export_header_code(required_columns)}
```

## Provenance Boundary

- This packet identifies the minimum reviewed rows needed to unblock workflow gates; it does not authorize biological claims by itself.
- Reviewed export values should come from the named source database, manuscript, accession record, or local tool export listed below.
- Do not paste unreviewed search results into the export. If a value is uncertain, keep the source wording and document the uncertainty in `notes`.
- Do not modify files under `data/raw/` while completing this metadata work order.

## Source Context

- Target database: `{starter.get('target_database', 'NA')}`
- Query ID: `{starter.get('query_id', 'NA')}`
- Query string: `{starter.get('query_string', 'NA')}`
- Starter template: `{starter.get('starter_template_path', 'NA')}`
- Starter README: `{starter.get('starter_readme_path', 'NA')}`
- Dashboard priority: `{dashboard.get('curation_priority', work.get('curation_priority', 'NA'))}`

## Completion Check

{work.get('completion_check', 'NA')}

Run after curation:

```bash
{work.get('validation_command', 'NA')}
```

For a focused acceptance check after editing only reviewed exports:

```bash
python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_curation_work_order stage_0_source_work_order_packets stage_0_source_work_order_acceptance stage_0_source_post_acceptance stage_10_study_readiness stage_10_readiness_actions
```

## Notes

This packet is a curation handoff only. Do not treat empty templates or unreviewed rows as biological evidence. Keep raw sequence files under `data/raw/` unchanged unless a later explicit sequence-acquisition step is reviewed.
"""


def index_markdown(manifest_rows: list[dict[str, str]]) -> str:
    lines = ["# Source Curation Work-Order Packets", "", "These packets render the current source curation work orders into per-source checklists.", "", "| Work order | Source | Minimum rows | Packet |", "| --- | --- | ---: | --- |"]
    for row in manifest_rows:
        lines.append(f"| `{row['work_order_id']}` | `{row['source_id']}` | {row['minimum_rows_to_add']} | `{row['packet_path']}` |")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    _, work_rows = read_tsv(Path(args.work_orders))
    _, starter_rows = read_tsv(Path(args.starter_kit_manifest))
    _, dashboard_rows = read_tsv(Path(args.dashboard))
    starter_by_source = by_key(starter_rows, "source_id")
    dashboard_by_source = by_key(dashboard_rows, "source_id")

    manifest_rows: list[dict[str, str]] = []
    for work in work_rows:
        source_id = work.get("source_id", "")
        packet_path = output_dir / f"{work.get('work_order_id', 'WO')}_{slug(source_id)}.md"
        packet_path.write_text(markdown_packet(work, starter_by_source.get(source_id, {}), dashboard_by_source.get(source_id, {})), encoding="utf-8")
        manifest_rows.append({
            "work_order_id": work.get("work_order_id", ""),
            "source_id": source_id,
            "packet_path": rel_or_abs(root, packet_path),
            "expected_export_path": work.get("expected_export_path", ""),
            "minimum_rows_to_add": work.get("minimum_rows_to_add", ""),
            "required_fields": work.get("required_fields", ""),
            "curation_priority": work.get("curation_priority", ""),
        })

    index_path = output_dir / "README.md"
    index_path.write_text(index_markdown(manifest_rows), encoding="utf-8")
    write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, manifest_rows)
    report_rows = [
        {"severity": "info", "item": "source_work_order_packets", "message": f"packets={len(manifest_rows)}; index={rel_or_abs(root, index_path)}"}
    ]
    if not manifest_rows:
        report_rows.append({"severity": "warning", "item": "source_work_order_packets", "message": "No work orders were available to render."})
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote {len(manifest_rows)} source work-order packet(s).")


if __name__ == "__main__":
    main()
