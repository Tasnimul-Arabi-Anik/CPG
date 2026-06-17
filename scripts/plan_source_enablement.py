#!/usr/bin/env python3
"""Plan import/catalog enablement after reviewed source exports are populated."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


PLAN_COLUMNS = [
    "source_id",
    "recommended_rank",
    "record_layer",
    "required_for_hypotheses",
    "export_path",
    "export_status",
    "export_row_count",
    "export_validation_status",
    "import_id",
    "import_enabled",
    "import_output_path",
    "catalog_enabled",
    "manifest_path",
    "manifest_row_count",
    "enablement_status",
    "config_actions_required",
    "validation_command",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan source import/catalog enablement after reviewed exports are available.")
    parser.add_argument("--source-acquisition-plan", required=True, help="Source acquisition plan TSV.")
    parser.add_argument("--source-export-validation", required=True, help="Source export validation TSV.")
    parser.add_argument("--minimum-source-plan", required=True, help="Minimum source curation plan TSV.")
    parser.add_argument("--imports-config", required=True, help="Source imports YAML config.")
    parser.add_argument("--catalog", required=True, help="Source catalog YAML config.")
    parser.add_argument("--plan-output", required=True, help="Output source enablement plan TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
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


def bool_text(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "false"
    return str(value).strip().lower()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit("PyYAML is required for source enablement planning.") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"YAML config must contain a mapping: {path}")
    return data


def rows_by(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key, "")}


def status_for(export: dict[str, str], acquisition: dict[str, str], import_enabled: str, catalog_enabled: str) -> tuple[str, str, str]:
    export_exists = export.get("export_exists") == "true" or acquisition.get("import_input_exists") == "true"
    export_rows = int(export.get("export_row_count") or acquisition.get("import_input_row_count") or "0")
    validation_status = export.get("validation_status", "")
    blocking = export.get("blocking_issue") == "true"
    manifest_rows = int(acquisition.get("manifest_row_count") or "0")

    if not export_exists:
        return (
            "waiting_for_reviewed_export",
            "none",
            "Create/populate the reviewed export TSV, then rerun source export validation.",
        )
    if export_rows == 0:
        return (
            "export_empty",
            "none",
            "Add at least one reviewed row with an accepted identity column before enabling import.",
        )
    if blocking or validation_status not in {"valid", "valid_with_warnings", "export_ready", "ready"}:
        return (
            "export_needs_validation_fix",
            "none",
            "Fix export validation errors before enabling import/catalog entries.",
        )
    actions: list[str] = []
    if import_enabled != "true":
        actions.append("set import enabled true in config/source_imports.yaml")
    if manifest_rows == 0:
        actions.append("rerun stage_0_source_imports to create a populated source manifest")
    if catalog_enabled != "true":
        actions.append("set source enabled true in config/source_catalog.yaml after manifest review")
    if actions:
        return (
            "ready_for_enablement",
            ";".join(actions),
            "Enable the import, rerun imports/acquisition/audit, review the manifest, then enable the catalog source.",
        )
    return (
        "enabled_for_sample_build",
        "none",
        "No enablement action required; rerun sample builder and downstream manifest stages.",
    )


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    acquisition_path = resolve(root, args.source_acquisition_plan)
    validation_path = resolve(root, args.source_export_validation)
    minimum_path = resolve(root, args.minimum_source_plan)
    imports_path = resolve(root, args.imports_config)
    catalog_path = resolve(root, args.catalog)
    plan_output = resolve(root, args.plan_output)
    report_output = resolve(root, args.report_output)

    _, acquisition_rows = read_tsv(acquisition_path)
    _, validation_rows = read_tsv(validation_path)
    _, minimum_rows = read_tsv(minimum_path)
    acquisition_by_source = rows_by(acquisition_rows, "source_id")
    validation_by_source = rows_by(validation_rows, "source_id")
    minimum_by_source = rows_by(minimum_rows, "source_id")

    imports_config = load_yaml(imports_path)
    catalog_config = load_yaml(catalog_path)
    imports_by_id = {str(row.get("import_id", "")): row for row in imports_config.get("imports", []) if isinstance(row, dict)}
    catalog_by_source = {str(row.get("source_id", "")): row for row in catalog_config.get("sources", []) if isinstance(row, dict)}

    source_ids = sorted(set(acquisition_by_source) | set(validation_by_source) | set(minimum_by_source) | set(catalog_by_source))
    def rank(source_id: str) -> tuple[int, str]:
        value = minimum_by_source.get(source_id, {}).get("recommended_rank", "999")
        try:
            return int(value), source_id
        except ValueError:
            return 999, source_id

    plan_rows: list[dict[str, str]] = []
    for source_id in sorted(source_ids, key=rank):
        acquisition = acquisition_by_source.get(source_id, {})
        validation = validation_by_source.get(source_id, {})
        minimum = minimum_by_source.get(source_id, {})
        import_id = acquisition.get("import_id", source_id)
        import_cfg = imports_by_id.get(import_id, {})
        catalog_cfg = catalog_by_source.get(source_id, {})
        import_enabled = acquisition.get("import_enabled") or bool_text(import_cfg.get("enabled"))
        catalog_enabled = acquisition.get("catalog_enabled") or bool_text(catalog_cfg.get("enabled"))
        status, actions, next_action = status_for(validation, acquisition, import_enabled, catalog_enabled)
        plan_rows.append({
            "source_id": source_id,
            "recommended_rank": minimum.get("recommended_rank", "999"),
            "record_layer": minimum.get("record_layer", acquisition.get("record_layer", "")),
            "required_for_hypotheses": minimum.get("required_for_hypotheses", "NA"),
            "export_path": validation.get("expected_export_path", acquisition.get("import_input_path", "")),
            "export_status": "exists" if validation.get("export_exists") == "true" or acquisition.get("import_input_exists") == "true" else "missing",
            "export_row_count": validation.get("export_row_count", acquisition.get("import_input_row_count", "0")),
            "export_validation_status": validation.get("validation_status", "NA"),
            "import_id": import_id,
            "import_enabled": import_enabled,
            "import_output_path": acquisition.get("import_output_path", import_cfg.get("output_path", "")),
            "catalog_enabled": catalog_enabled,
            "manifest_path": acquisition.get("manifest_path", catalog_cfg.get("path", "")),
            "manifest_row_count": acquisition.get("manifest_row_count", "0"),
            "enablement_status": status,
            "config_actions_required": actions,
            "validation_command": minimum.get("validation_command", "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_curation_tasks stage_0_hypothesis_source_unlocks stage_0_samples stage_1_manifest"),
            "next_action": next_action,
        })

    status_counts: dict[str, int] = {}
    for row in plan_rows:
        status_counts[row["enablement_status"]] = status_counts.get(row["enablement_status"], 0) + 1
    ready_count = status_counts.get("enabled_for_sample_build", 0)
    report_rows = [
        {"severity": "info", "item": "source_enablement", "message": f"sources={len(plan_rows)}; enabled_for_sample_build={ready_count}; status_counts=" + ";".join(f"{key}:{value}" for key, value in sorted(status_counts.items()))},
    ]
    if ready_count == 0:
        report_rows.append({"severity": "warning", "item": "source_enablement", "message": "No source is enabled for sample building yet."})
    write_tsv(plan_output, PLAN_COLUMNS, plan_rows)
    write_tsv(report_output, REPORT_COLUMNS, report_rows)
    print(f"Wrote source enablement plan for {len(plan_rows)} sources.")


if __name__ == "__main__":
    main()
