#!/usr/bin/env python3
"""Apply safe source import/catalog enablement changes from the source enablement plan."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = [
    "source_id",
    "enablement_status",
    "import_id",
    "import_enabled_before",
    "import_enabled_after",
    "catalog_enabled_before",
    "catalog_enabled_after",
    "action_status",
    "message",
]
READY_STATUSES = {"ready_for_enablement", "enabled_for_sample_build"}


class EnablementError(Exception):
    """Raised when source enablement inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely update source import/catalog YAML from source_enablement_plan.tsv.")
    parser.add_argument("--enablement-plan", required=True, help="Source enablement plan TSV.")
    parser.add_argument("--imports-config", required=True, help="Source imports YAML to inspect/update.")
    parser.add_argument("--catalog", required=True, help="Source catalog YAML to inspect/update.")
    parser.add_argument("--report-output", required=True, help="Output apply report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    parser.add_argument("--sources", nargs="*", default=[], help="Optional source_id subset to enable.")
    parser.add_argument("--enable-imports", action="store_true", help="Enable matching import entries when source rows are ready.")
    parser.add_argument("--enable-catalog", action="store_true", help="Enable matching catalog entries when manifests are populated or already enabled.")
    parser.add_argument("--apply", action="store_true", help="Write YAML changes. Without this flag, only a dry-run report is written.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise EnablementError(f"Required TSV does not exist: {path}")
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


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise EnablementError("PyYAML is required for source enablement updates.") from exc
    if not path.exists():
        raise EnablementError(f"YAML config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise EnablementError(f"YAML config must contain a mapping: {path}")
    return data


def dump_yaml(path: Path, data: dict) -> None:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise EnablementError("PyYAML is required for source enablement updates.") from exc
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False), encoding="utf-8")


def bool_text(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value or "false").strip().lower()


def int_value(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def backup(path: Path) -> Path:
    target = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, target)
    return target


def validate_plan(fields: list[str]) -> None:
    required = {
        "source_id",
        "enablement_status",
        "import_id",
        "import_enabled",
        "catalog_enabled",
        "manifest_row_count",
        "export_row_count",
    }
    missing = sorted(required - set(fields))
    if missing:
        raise EnablementError("Enablement plan is missing required columns: " + ";".join(missing))


def should_enable_catalog(row: dict[str, str]) -> bool:
    return row.get("enablement_status") == "enabled_for_sample_build" or int_value(row.get("manifest_row_count", "0")) > 0


def apply_enablement(args: argparse.Namespace) -> list[dict[str, str]]:
    root = Path(args.root).resolve()
    plan_path = resolve(root, args.enablement_plan)
    imports_path = resolve(root, args.imports_config)
    catalog_path = resolve(root, args.catalog)
    fields, plan_rows = read_tsv(plan_path)
    validate_plan(fields)

    selected = set(args.sources or [])
    imports_config = load_yaml(imports_path)
    catalog_config = load_yaml(catalog_path)
    import_entries = imports_config.get("imports", [])
    catalog_entries = catalog_config.get("sources", [])
    if not isinstance(import_entries, list) or not isinstance(catalog_entries, list):
        raise EnablementError("Expected imports_config.imports and catalog.sources to be lists.")
    imports_by_id = {str(entry.get("import_id", "")): entry for entry in import_entries if isinstance(entry, dict)}
    catalog_by_source = {str(entry.get("source_id", "")): entry for entry in catalog_entries if isinstance(entry, dict)}

    changed_imports = False
    changed_catalog = False
    report_rows: list[dict[str, str]] = []
    for row in plan_rows:
        source_id = row.get("source_id", "")
        if selected and source_id not in selected:
            continue
        status = row.get("enablement_status", "")
        import_id = row.get("import_id", source_id)
        import_entry = imports_by_id.get(import_id)
        catalog_entry = catalog_by_source.get(source_id)
        import_before = bool_text(import_entry.get("enabled") if import_entry else False)
        catalog_before = bool_text(catalog_entry.get("enabled") if catalog_entry else False)
        import_after = import_before
        catalog_after = catalog_before

        messages: list[str] = []
        action_status = "dry_run" if not args.apply else "unchanged"
        if status not in READY_STATUSES:
            messages.append(f"Skipped because enablement_status is {status}; populate and validate reviewed rows first.")
            action_status = "skipped_not_ready"
        else:
            if args.enable_imports:
                if import_entry is None:
                    messages.append("No matching import config entry found.")
                    action_status = "skipped_missing_import_entry"
                elif import_before != "true":
                    import_after = "true"
                    messages.append("Import entry can be enabled." if not args.apply else "Import entry enabled.")
                    if args.apply:
                        import_entry["enabled"] = True
                        changed_imports = True
                        action_status = "updated"
                else:
                    messages.append("Import entry already enabled.")
            if args.enable_catalog:
                if catalog_entry is None:
                    messages.append("No matching catalog source entry found.")
                    action_status = "skipped_missing_catalog_entry"
                elif not should_enable_catalog(row):
                    messages.append("Catalog source was not enabled because no populated manifest is recorded yet.")
                elif catalog_before != "true":
                    catalog_after = "true"
                    messages.append("Catalog source can be enabled." if not args.apply else "Catalog source enabled.")
                    if args.apply:
                        catalog_entry["enabled"] = True
                        changed_catalog = True
                        action_status = "updated"
                else:
                    messages.append("Catalog source already enabled.")
            if not args.enable_imports and not args.enable_catalog:
                messages.append("No config update flag was selected; pass --enable-imports and/or --enable-catalog.")
        report_rows.append({
            "source_id": source_id,
            "enablement_status": status,
            "import_id": import_id,
            "import_enabled_before": import_before,
            "import_enabled_after": import_after,
            "catalog_enabled_before": catalog_before,
            "catalog_enabled_after": catalog_after,
            "action_status": action_status,
            "message": " ".join(messages),
        })

    if args.apply:
        if changed_imports:
            backup(imports_path)
            dump_yaml(imports_path, imports_config)
        if changed_catalog:
            backup(catalog_path)
            dump_yaml(catalog_path, catalog_config)
    return report_rows


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        rows = apply_enablement(args)
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, rows)
        updated = sum(1 for row in rows if row.get("action_status") == "updated")
        print(f"Wrote source enablement apply report for {len(rows)} source(s); updated={updated}; apply={str(args.apply).lower()}.")
        return 0
    except EnablementError as exc:
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, [{
            "source_id": "NA",
            "enablement_status": "error",
            "import_id": "NA",
            "import_enabled_before": "NA",
            "import_enabled_after": "NA",
            "catalog_enabled_before": "NA",
            "catalog_enabled_after": "NA",
            "action_status": "error",
            "message": str(exc),
        }])
        print(f"Source enablement apply failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
