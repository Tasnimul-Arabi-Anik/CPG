#!/usr/bin/env python3
"""Generate GitHub-ready issue bodies from source curation work orders."""

from __future__ import annotations

import argparse
import csv
import re
import shlex
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "work_order_id",
    "source_id",
    "issue_title",
    "issue_body_path",
    "labels",
    "expected_export_path",
    "required_for_hypotheses",
    "minimum_rows_to_add",
    "required_fields",
]
COMMAND_COLUMNS = ["work_order_id", "source_id", "issue_title", "issue_body_path", "labels", "gh_command"]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate GitHub issue bodies from source curation work orders.")
    parser.add_argument("--work-orders", required=True, help="source_curation_work_order.tsv.")
    parser.add_argument("--issue-dir", required=True, help="Directory for generated Markdown issue bodies.")
    parser.add_argument("--manifest-output", required=True, help="Output issue manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--commands-output", default="", help="Optional output TSV with gh issue create commands.")
    parser.add_argument("--shell-output", default="", help="Optional output shell script with gh issue create commands.")
    parser.add_argument("--max-issues", type=int, default=0, help="Optional maximum number of ranked work orders to render. 0 renders all.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
        return reader.fieldnames or [], rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_")
    return cleaned or "source_work_order"


def bullet_values(values: list[str]) -> str:
    if not values:
        return "- `NA`"
    return "\n".join(f"- `{value}`" for value in values)


def row_template(required_fields: list[str]) -> str:
    default_fields = [
        "accession",
        "genome_id",
        "host_species",
        "host_strain",
        "country",
        "year",
        "genome_length",
        "gc_percent",
        "K_type",
        "O_type",
        "ST",
        "raw_sequence_path",
        "notes",
    ]
    fields = []
    for field in [*required_fields, *default_fields]:
        if field not in fields:
            fields.append(field)
    return "\n".join(f"{field}:" for field in fields)


def issue_body(row: dict[str, str]) -> str:
    required_fields = split_values(row.get("required_fields", ""))
    hypotheses = row.get("required_for_hypotheses", "NA") or "NA"
    validation_command = row.get("validation_command", "python scripts/run_workflow.py --config config/workflow.yaml")
    return f"""## Purpose

Unblock reviewed source curation for the Klebsiella phage comparative genomics workflow.

## Work Order

- Work order ID: `{row.get('work_order_id', 'NA')}`
- Source ID: `{row.get('source_id', 'NA')}`
- Record layer: `{row.get('record_layer', 'NA')}`
- Required for hypotheses: `{hypotheses}`
- Reviewed export path: `{row.get('expected_export_path', 'NA')}`
- Minimum reviewed rows to add: `{row.get('minimum_rows_to_add', 'NA')}`
- Current export rows: `{row.get('current_export_rows', 'NA')}`
- Current satisfying rows: `{row.get('current_satisfying_rows', 'NA')}`

## Required Fields

{bullet_values(required_fields)}

## Reviewed Row Values

Paste the proposed TSV row or field/value list here. Unknown values should be `NA`.

```text
{row_template(required_fields)}
```

## Provenance Requirements

- Use reviewed database, accession, manuscript, or local export evidence only.
- Record database snapshot, accession source, DOI/PMID, curator notes, and uncertainty in `notes` when available.
- Do not paste unreviewed search results into the export.
- Do not infer K/O/ST, lifestyle, host traits, receptor specificity, anti-defense activity, or host range without evidence.
- `raw_sequence_path` should point only to a reviewed local FASTA/GenBank path, or remain `NA` until sequence acquisition is reviewed.
- This issue does not authorize biological claims; it only advances dataset curation.

## Blocked Metrics

`{row.get('blocked_metrics', 'NA')}`

## Validation Command

Run after curation:

```bash
{validation_command}
```

Focused acceptance check:

```bash
python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_curation_work_order stage_0_source_work_order_packets stage_0_source_work_order_acceptance stage_0_source_post_acceptance stage_10_study_readiness stage_10_readiness_actions
```

Inspect:

- `results/qc/source_work_order_acceptance.tsv`
- `results/qc/source_post_acceptance_plan.tsv`
- `results/validation/study_readiness.tsv`

## Acceptance Target

For `{row.get('work_order_id', 'NA')}`, `results/qc/source_work_order_acceptance.tsv` should report:

- `acceptance_status=accepted`
- `blocking_issue=false`

Raw sequence and provenance lint fields should be reviewed before downstream interpretation.
"""



def gh_issue_command(title: str, body_path: str, labels: str) -> str:
    command = ["gh", "issue", "create", "--title", title, "--body-file", body_path]
    for label in split_values(labels):
        command.extend(["--label", label])
    return " ".join(shlex.quote(part) for part in command)


def write_shell(path: Path, commands: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    lines.extend(commands)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

def main() -> None:
    args = parse_args()
    _, rows = read_tsv(Path(args.work_orders))
    if args.max_issues > 0:
        rows = rows[: args.max_issues]
    issue_dir = Path(args.issue_dir)
    issue_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []
    command_rows: list[dict[str, str]] = []
    shell_commands: list[str] = []
    for row in rows:
        work_order_id = row.get("work_order_id", "WO")
        source_id = row.get("source_id", "source")
        title = f"{work_order_id}: curate reviewed rows for {source_id}"
        body_path = issue_dir / f"{slug(work_order_id)}_{slug(source_id)}.md"
        body_path.write_text(issue_body(row), encoding="utf-8")
        body_display_path = display_path(body_path)
        labels = "source-curation;data-intake"
        command = gh_issue_command(title, body_display_path, labels)
        manifest_rows.append({
            "work_order_id": work_order_id,
            "source_id": source_id,
            "issue_title": title,
            "issue_body_path": body_display_path,
            "labels": labels,
            "expected_export_path": row.get("expected_export_path", ""),
            "required_for_hypotheses": row.get("required_for_hypotheses", ""),
            "minimum_rows_to_add": row.get("minimum_rows_to_add", ""),
            "required_fields": row.get("required_fields", ""),
        })
        command_rows.append({
            "work_order_id": work_order_id,
            "source_id": source_id,
            "issue_title": title,
            "issue_body_path": body_display_path,
            "labels": labels,
            "gh_command": command,
        })
        shell_commands.append(command)
    report_rows = [
        {"severity": "info", "item": "source_curation_issue_bodies", "message": f"work_orders={len(rows)}; issue_bodies={len(manifest_rows)}"}
    ]
    if not rows:
        report_rows.append({"severity": "warning", "item": "source_curation_issue_bodies", "message": "No work orders were available to render."})
    write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, manifest_rows)
    if args.commands_output:
        write_tsv(Path(args.commands_output), COMMAND_COLUMNS, command_rows)
    if args.shell_output:
        write_shell(Path(args.shell_output), shell_commands)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Rendered {len(manifest_rows)} source curation issue bodie(s).")


if __name__ == "__main__":
    main()
