#!/usr/bin/env python3
"""Create header-only templates for configured external evidence TSVs."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "evidence_id",
    "analysis_layer",
    "hypotheses_supported",
    "optional_input_key",
    "configured_input_path",
    "configured_input_exists",
    "configured_input_rows",
    "template_path",
    "required_columns_spec",
    "header_columns",
    "one_of_groups",
    "evidence_status",
    "template_status",
    "next_action",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


class EvidenceTemplateError(Exception):
    """Raised when external evidence templates cannot be generated."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create TSV templates for external evidence inputs.")
    parser.add_argument("--evidence-plan", required=True, help="External evidence plan TSV from plan_external_evidence.py.")
    parser.add_argument("--templates-dir", required=True, help="Directory for header-only template TSVs.")
    parser.add_argument("--manifest-output", required=True, help="Template manifest TSV output.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV output.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


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


def safe_filename(value: str, fallback: str) -> str:
    raw = value or fallback
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")
    return raw or fallback


def unique(items: Iterable[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def parse_required_columns(spec: str) -> tuple[list[str], list[str]]:
    headers: list[str] = []
    groups: list[str] = []
    for token in [part.strip() for part in spec.split(";") if part.strip()]:
        if token.startswith("one_of:"):
            group = [item.strip() for item in token[len("one_of:"):].split("|") if item.strip()]
            headers.extend(group)
            groups.append("|".join(group))
        else:
            headers.append(token)
    return unique(headers), groups


def write_template(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
        writer.writeheader()


def build_templates(root: Path, evidence_plan: Path, templates_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fieldnames, plan_rows = read_tsv(evidence_plan)
    if not evidence_plan.exists():
        raise EvidenceTemplateError(f"External evidence plan does not exist: {evidence_plan}")
    required = {"evidence_id", "optional_input_key", "configured_input_required_columns", "evidence_status"}
    missing = sorted(required - set(fieldnames))
    if missing:
        raise EvidenceTemplateError("External evidence plan is missing required columns: " + ";".join(missing))

    manifest: list[dict[str, str]] = []
    report: list[dict[str, str]] = []
    for index, row in enumerate(plan_rows, start=1):
        evidence_id = normalize(row.get("evidence_id")) or f"evidence_{index}"
        required_spec = normalize(row.get("configured_input_required_columns"))
        headers, groups = parse_required_columns(required_spec)
        if not headers:
            headers = ["record_id", "evidence_source", "notes"]
        if "evidence_source" not in headers:
            headers.append("evidence_source")
        if "notes" not in headers:
            headers.append("notes")
        template_path = templates_dir / (safe_filename(evidence_id, f"evidence_{index}") + ".tsv")
        write_template(template_path, headers)
        configured_exists = normalize(row.get("configured_input_exists")) == "true"
        configured_rows = normalize(row.get("configured_input_rows")) or "0"
        evidence_status = normalize(row.get("evidence_status"))
        if configured_exists and configured_rows != "0" and normalize(row.get("configured_input_schema_status")) == "pass":
            status = "configured_input_ready"
            action = "No template action required unless replacing this evidence input."
        else:
            status = "template_ready"
            action = "Populate evidence TSV with this header, then set the path in config/workflow.yaml."
        manifest.append(
            {
                "evidence_id": evidence_id,
                "analysis_layer": normalize(row.get("analysis_layer")),
                "hypotheses_supported": normalize(row.get("hypotheses_supported")),
                "optional_input_key": normalize(row.get("optional_input_key")),
                "configured_input_path": normalize(row.get("configured_input_path")),
                "configured_input_exists": normalize(row.get("configured_input_exists")),
                "configured_input_rows": configured_rows,
                "template_path": display_path(root, template_path),
                "required_columns_spec": required_spec,
                "header_columns": ";".join(headers),
                "one_of_groups": ";".join(groups),
                "evidence_status": evidence_status,
                "template_status": status,
                "next_action": action,
                "notes": normalize(row.get("notes")),
            }
        )

    ready = sum(1 for row in manifest if row["template_status"] == "template_ready")
    configured = sum(1 for row in manifest if row["template_status"] == "configured_input_ready")
    report.append({"severity": "info", "item": "external_evidence_templates", "message": f"Created {len(manifest)} external evidence template(s)."})
    if ready:
        report.append({"severity": "warning", "item": "template_ready", "message": f"{ready} evidence template(s) await production evidence TSVs."})
    if configured:
        report.append({"severity": "info", "item": "configured_input_ready", "message": f"{configured} evidence input(s) are already configured and schema-ready."})
    return manifest, report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        manifest, report = build_templates(root, root / args.evidence_plan if not Path(args.evidence_plan).is_absolute() else Path(args.evidence_plan), root / args.templates_dir if not Path(args.templates_dir).is_absolute() else Path(args.templates_dir))
        manifest_output = root / args.manifest_output if not Path(args.manifest_output).is_absolute() else Path(args.manifest_output)
        report_output = root / args.report_output if not Path(args.report_output).is_absolute() else Path(args.report_output)
        write_tsv(manifest_output, MANIFEST_COLUMNS, manifest)
        write_tsv(report_output, REPORT_COLUMNS, report)
        errors = sum(1 for row in report if row.get("severity") == "error")
        print(f"External evidence templates complete: {len(manifest)} templates, {errors} errors.")
        return 1 if errors else 0
    except EvidenceTemplateError as exc:
        manifest_output = Path(args.manifest_output)
        report_output = Path(args.report_output)
        write_tsv(manifest_output, MANIFEST_COLUMNS, [])
        write_tsv(report_output, REPORT_COLUMNS, [{"severity": "error", "item": "external_evidence_templates", "message": str(exc)}])
        print(f"External evidence templates failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
