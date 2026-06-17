#!/usr/bin/env python3
"""Rank source exports and hypothesis source sets for minimum real-data curation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


SOURCE_COLUMNS = [
    "source_id",
    "recommended_rank",
    "record_layer",
    "review_priority",
    "curation_status",
    "required_for_hypotheses",
    "optional_for_hypotheses",
    "required_hypothesis_count",
    "optional_hypothesis_count",
    "starter_readme_path",
    "starter_template_path",
    "expected_export_path",
    "identity_columns_required",
    "validation_command",
    "recommended_action",
    "rationale",
]
HYPOTHESIS_COLUMNS = [
    "hypothesis",
    "minimum_required_sources",
    "missing_required_sources",
    "ready_required_sources",
    "optional_sources",
    "minimum_source_count",
    "starter_readmes",
    "expected_export_paths",
    "minimum_unlock_status",
    "next_action",
    "analysis_outputs_unlocked",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
PRIORITY_ORDER = {"primary": 0, "primary_manual": 1, "optional_discovery": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan the minimum reviewed source exports needed to begin real H1-H6 tests.")
    parser.add_argument("--hypothesis-source-unlocks", required=True, help="Hypothesis source unlock plan TSV.")
    parser.add_argument("--starter-kit-manifest", required=True, help="Source export starter kit manifest TSV.")
    parser.add_argument("--source-plan-output", required=True, help="Output ranked source curation TSV.")
    parser.add_argument("--hypothesis-plan-output", required=True, help="Output per-hypothesis minimum source set TSV.")
    parser.add_argument("--report-output", required=True, help="Output summary report TSV.")
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


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


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


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


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    hypothesis_path = resolve(root, args.hypothesis_source_unlocks)
    starter_path = resolve(root, args.starter_kit_manifest)
    source_output = resolve(root, args.source_plan_output)
    hypothesis_output = resolve(root, args.hypothesis_plan_output)
    report_output = resolve(root, args.report_output)

    _, hypothesis_rows = read_tsv(hypothesis_path)
    _, starter_rows = read_tsv(starter_path)
    starter_by_source = {row.get("source_id", ""): row for row in starter_rows}

    required_for: dict[str, list[str]] = {}
    optional_for: dict[str, list[str]] = {}
    hypothesis_plan_rows: list[dict[str, str]] = []
    for row in hypothesis_rows:
        hypothesis = row.get("hypothesis", "")
        required = split_values(row.get("required_source_ids", ""))
        optional = split_values(row.get("optional_source_ids", ""))
        ready = split_values(row.get("ready_required_sources", ""))
        missing = split_values(row.get("blocking_required_sources", ""))
        for source in required:
            required_for.setdefault(source, []).append(hypothesis)
        for source in optional:
            optional_for.setdefault(source, []).append(hypothesis)
        starter_readmes = [starter_by_source.get(source, {}).get("starter_readme_path", "") for source in required]
        export_paths = [starter_by_source.get(source, {}).get("expected_export_path", "") for source in required]
        hypothesis_plan_rows.append({
            "hypothesis": hypothesis,
            "minimum_required_sources": join(required),
            "missing_required_sources": join(missing),
            "ready_required_sources": join(ready),
            "optional_sources": join(optional),
            "minimum_source_count": str(len(required)),
            "starter_readmes": join(starter_readmes),
            "expected_export_paths": join(export_paths),
            "minimum_unlock_status": row.get("minimum_unlock_status", ""),
            "next_action": row.get("next_action", ""),
            "analysis_outputs_unlocked": row.get("analysis_outputs_unlocked", ""),
        })

    source_ids = sorted(set(starter_by_source) | set(required_for) | set(optional_for))
    def sort_key(source_id: str) -> tuple[int, int, int, str]:
        starter = starter_by_source.get(source_id, {})
        return (
            -len(required_for.get(source_id, [])),
            PRIORITY_ORDER.get(starter.get("review_priority", ""), 9),
            -len(optional_for.get(source_id, [])),
            source_id,
        )

    ranked_sources = sorted(source_ids, key=sort_key)
    source_plan_rows: list[dict[str, str]] = []
    for rank, source_id in enumerate(ranked_sources, start=1):
        starter = starter_by_source.get(source_id, {})
        req_h = required_for.get(source_id, [])
        opt_h = optional_for.get(source_id, [])
        if req_h:
            action = f"Populate and validate reviewed export for {source_id}; required by {join(req_h)}."
        else:
            action = f"Populate only after required sources are underway; optional for {join(opt_h)}."
        rationale = (
            f"Required for {len(req_h)} hypothesis minimum source set(s) and optional for {len(opt_h)}. "
            "Higher ranks unblock the largest number of H1-H6 real-data tests."
        )
        source_plan_rows.append({
            "source_id": source_id,
            "recommended_rank": str(rank),
            "record_layer": starter.get("record_layer", ""),
            "review_priority": starter.get("review_priority", ""),
            "curation_status": starter.get("curation_status", ""),
            "required_for_hypotheses": join(req_h),
            "optional_for_hypotheses": join(opt_h),
            "required_hypothesis_count": str(len(req_h)),
            "optional_hypothesis_count": str(len(opt_h)),
            "starter_readme_path": starter.get("starter_readme_path", ""),
            "starter_template_path": starter.get("starter_template_path", ""),
            "expected_export_path": starter.get("expected_export_path", ""),
            "identity_columns_required": starter.get("identity_columns_required", ""),
            "validation_command": starter.get("validation_command", ""),
            "recommended_action": action,
            "rationale": rationale,
        })

    required_sources = [row for row in source_plan_rows if row["required_hypothesis_count"] != "0"]
    blocked_hypotheses = [row for row in hypothesis_plan_rows if row["minimum_unlock_status"] != "ready_minimum_sources"]
    report_rows = [
        {"severity": "info", "item": "minimum_source_curation", "message": f"sources={len(source_plan_rows)}; required_sources={len(required_sources)}; hypotheses={len(hypothesis_plan_rows)}; blocked_hypotheses={len(blocked_hypotheses)}"},
    ]
    if blocked_hypotheses:
        report_rows.append({"severity": "warning", "item": "minimum_source_curation", "message": "One or more hypotheses still lack the reviewed source exports required for real-data tests."})
    else:
        report_rows.append({"severity": "info", "item": "minimum_source_curation", "message": "All hypotheses have their minimum required source exports ready."})

    write_tsv(source_output, SOURCE_COLUMNS, source_plan_rows)
    write_tsv(hypothesis_output, HYPOTHESIS_COLUMNS, hypothesis_plan_rows)
    write_tsv(report_output, REPORT_COLUMNS, report_rows)
    print(f"Wrote minimum source curation plan for {len(source_plan_rows)} sources and {len(hypothesis_plan_rows)} hypotheses.")


if __name__ == "__main__":
    main()
