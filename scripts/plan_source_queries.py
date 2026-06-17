#!/usr/bin/env python3
"""Build an auditable query/export plan for public Klebsiella phage and host sources."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


QUERY_COLUMNS = [
    "query_id",
    "source_id",
    "record_layer",
    "target_database",
    "acquisition_mode",
    "query_string",
    "expected_export_path",
    "export_path_exists",
    "export_row_count",
    "expected_manifest_path",
    "manifest_exists",
    "manifest_row_count",
    "import_id",
    "import_configured",
    "import_input_path",
    "export_path_matches_import",
    "import_output_path",
    "import_output_matches_manifest",
    "expected_columns",
    "identity_columns_required",
    "review_priority",
    "query_status",
    "blocking_issue",
    "next_action",
    "suggested_command",
    "rationale",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
DEFAULT_IDENTITY_COLUMNS = ["genome_id", "accession", "raw_sequence_path"]


class QueryPlanError(Exception):
    """Raised for invalid query planning configuration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan source queries and reviewed export targets for the CPG workflow.")
    parser.add_argument("--queries-config", required=True, help="YAML source-query configuration.")
    parser.add_argument("--catalog", required=True, help="YAML source catalog used by the sample builder.")
    parser.add_argument("--imports-config", required=True, help="YAML source import configuration.")
    parser.add_argument("--plan-output", required=True, help="Output source query plan TSV.")
    parser.add_argument("--report-output", required=True, help="Output source query report TSV.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise QueryPlanError("PyYAML is required to read source query configuration.") from exc
    if not path.exists():
        raise QueryPlanError(f"Configuration does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise QueryPlanError(f"Configuration must contain a YAML mapping: {path}")
    return data


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def bool_value(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = normalize(value).lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def configured_list(value: object, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        parsed = [normalize(item) for item in value]
    elif value is None:
        parsed = []
    else:
        parsed = [part.strip() for part in normalize(value).replace(",", ";").split(";")]
    parsed = [item for item in parsed if item]
    return parsed or (fallback or [])


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def has_path(path: Path | str) -> bool:
    return str(Path(path)) not in {"", "."}


def display_path(root: Path, path: Path | str) -> str:
    path_obj = Path(path)
    if not has_path(path_obj):
        return ""
    try:
        return path_obj.relative_to(root).as_posix()
    except ValueError:
        return path_obj.as_posix()


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


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


def source_index(catalog: dict) -> dict[str, dict]:
    sources = catalog.get("sources", [])
    if not isinstance(sources, list):
        raise QueryPlanError("source catalog 'sources' must be a list")
    indexed = {}
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue
        source_id = normalize(source.get("source_id")) or f"source_{index}"
        indexed[source_id] = dict(source)
    return indexed


def imports_index(root: Path, imports_config: dict) -> dict[str, dict]:
    imports = imports_config.get("imports", [])
    if not isinstance(imports, list):
        raise QueryPlanError("source import config 'imports' must be a list")
    indexed = {}
    for index, spec in enumerate(imports, start=1):
        if not isinstance(spec, dict):
            continue
        import_id = normalize(spec.get("import_id")) or f"import_{index}"
        spec = dict(spec)
        spec["import_id"] = import_id
        indexed[import_id] = spec
        output_path = normalize(spec.get("output_path"))
        if output_path:
            indexed[display_path(root, resolve(root, output_path))] = spec
    return indexed


def matching_import(root: Path, source_id: str, source: dict, import_lookup: dict[str, dict]) -> dict:
    manifest_text = normalize(source.get("path"))
    if manifest_text:
        manifest_key = display_path(root, resolve(root, manifest_text))
        if manifest_key in import_lookup:
            return import_lookup[manifest_key]
    return import_lookup.get(source_id, {})


def layer_for(source_id: str, source: dict, query: dict) -> str:
    if not is_missing(normalize(query.get("record_layer"))):
        return normalize(query.get("record_layer"))
    record_type = normalize(source.get("record_type_default")).lower()
    text = f"{source_id} {normalize(source.get('source_label'))}".lower()
    if record_type == "host" or "host" in text:
        return "host_genomes"
    if record_type == "prophage" or "prophage" in text:
        return "prophages"
    if record_type == "metagenomic_viral_contig" or "metagenomic" in text:
        return "metagenomic_discovery"
    if "literature" in text:
        return "literature_curated_phages"
    return "cultured_phages"


def row_count(path: Path) -> int:
    _, rows = read_tsv(path)
    return len(rows)


def expected_export_path(root: Path, query: dict, import_spec: dict) -> Path:
    configured = normalize(query.get("expected_export_path"))
    if configured:
        return resolve(root, configured)
    input_path = normalize(import_spec.get("input_path")) if import_spec else ""
    return resolve(root, input_path) if input_path else Path("")


def status_and_action(
    source_present: bool,
    query_string: str,
    export_path: Path,
    export_exists: bool,
    export_rows: int,
    manifest_exists: bool,
    manifest_rows: int,
    catalog_enabled: bool,
    import_spec: dict,
    export_matches_import: bool,
    output_matches_manifest: bool,
) -> tuple[str, str, str, str]:
    if not source_present:
        return "config_error", "true", "Add this source_id to config/source_catalog.yaml or fix config/source_queries.yaml.", "Edit source configuration."
    if is_missing(query_string):
        return "config_error", "true", "Add a query_string or manual query description.", "Edit config/source_queries.yaml."
    if import_spec and has_path(export_path) and not export_matches_import:
        return "config_error", "true", "Align expected_export_path with the import input_path for this source.", "Edit config/source_queries.yaml or config/source_imports.yaml."
    if import_spec and not output_matches_manifest:
        return "config_error", "true", "Align import output_path with the source catalog manifest path.", "Edit config/source_imports.yaml."
    if catalog_enabled and manifest_rows > 0:
        return "source_already_enabled", "false", "No query action required before sample building.", "No action required."
    if export_exists and export_rows > 0:
        return "local_export_present", "false", "Review the export, enable import if needed, then build the source manifest.", "python scripts/import_source_manifests.py --config config/source_imports.yaml --report-output results/qc/source_import_report.tsv"
    if export_exists and export_rows == 0:
        return "local_export_empty", "true", "Regenerate the reviewed export with data rows.", f"Populate {display_path(Path.cwd(), export_path)}"
    if import_spec and has_path(export_path):
        return "planned_query_ready", "false", "Run/export the planned query and save the reviewed TSV to the expected export path.", f"Create {display_path(Path.cwd(), export_path)}"
    return "manual_query_no_import", "false", "Use the planned query to manually populate the source manifest or add a source import entry.", "Populate the source manifest or add an import entry."


def plan_queries(root: Path, query_config_path: Path, catalog_path: Path, imports_config_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    query_config = load_yaml(query_config_path)
    catalog = load_yaml(catalog_path)
    imports_config = load_yaml(imports_config_path)
    sources = source_index(catalog)
    imports = imports_index(root, imports_config)
    queries = query_config.get("queries", [])
    if not isinstance(queries, list):
        raise QueryPlanError("source query config 'queries' must be a list")

    rows: list[dict[str, str]] = []
    report: list[dict[str, str]] = []
    if not queries:
        add_report(report, "warning", "queries", "No source queries are configured.")

    for index, query in enumerate(queries, start=1):
        if not isinstance(query, dict):
            add_report(report, "error", f"query_{index}", "Query entry is not a mapping.")
            continue
        query_id = normalize(query.get("query_id")) or f"query_{index}"
        source_id = normalize(query.get("source_id"))
        source = sources.get(source_id, {})
        import_spec = matching_import(root, source_id, source, imports) if source else {}
        manifest_text = normalize(source.get("path")) if source else ""
        manifest_path = resolve(root, manifest_text) if manifest_text else Path("")
        export_path = expected_export_path(root, query, import_spec)
        import_input_text = normalize(import_spec.get("input_path")) if import_spec else ""
        import_input_path = resolve(root, import_input_text) if import_input_text else Path("")
        import_output_text = normalize(import_spec.get("output_path")) if import_spec else ""
        import_output_path = resolve(root, import_output_text) if import_output_text else Path("")
        export_exists = bool(has_path(export_path) and export_path.exists())
        manifest_exists = bool(has_path(manifest_path) and manifest_path.exists())
        export_rows = row_count(export_path) if export_exists else 0
        manifest_rows = row_count(manifest_path) if manifest_exists else 0
        query_string = normalize(query.get("query_string") or query.get("query"))
        catalog_enabled = bool_value(source.get("enabled"), False) if source else False
        export_matches_import = not import_spec or not has_path(export_path) or (display_path(root, export_path) == display_path(root, import_input_path))
        output_matches_manifest = not import_spec or not has_path(import_output_path) or not has_path(manifest_path) or (display_path(root, import_output_path) == display_path(root, manifest_path))
        status, blocking, action, command = status_and_action(
            bool(source),
            query_string,
            export_path,
            export_exists,
            export_rows,
            manifest_exists,
            manifest_rows,
            catalog_enabled,
            import_spec,
            export_matches_import,
            output_matches_manifest,
        )
        if query.get("suggested_command"):
            command = normalize(query.get("suggested_command"))
        rows.append(
            {
                "query_id": query_id,
                "source_id": source_id,
                "record_layer": layer_for(source_id, source, query),
                "target_database": normalize(query.get("target_database")) or "NA",
                "acquisition_mode": normalize(query.get("acquisition_mode")) or "reviewed_local_export",
                "query_string": query_string,
                "expected_export_path": display_path(root, export_path),
                "export_path_exists": str(export_exists).lower(),
                "export_row_count": str(export_rows),
                "expected_manifest_path": display_path(root, manifest_path),
                "manifest_exists": str(manifest_exists).lower(),
                "manifest_row_count": str(manifest_rows),
                "import_id": normalize(import_spec.get("import_id")) if import_spec else "",
                "import_configured": str(bool(import_spec)).lower(),
                "import_input_path": display_path(root, import_input_path),
                "export_path_matches_import": str(export_matches_import).lower(),
                "import_output_path": display_path(root, import_output_path),
                "import_output_matches_manifest": str(output_matches_manifest).lower(),
                "expected_columns": ";".join(configured_list(query.get("expected_columns"))),
                "identity_columns_required": ";".join(configured_list(query.get("identity_columns_required"), DEFAULT_IDENTITY_COLUMNS)),
                "review_priority": normalize(query.get("review_priority")) or "primary",
                "query_status": status,
                "blocking_issue": blocking,
                "next_action": action,
                "suggested_command": command,
                "rationale": normalize(query.get("rationale")),
                "notes": normalize(query.get("notes")),
            }
        )

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["query_status"]] = status_counts.get(row["query_status"], 0) + 1
    add_report(report, "info", "queries", f"Planned {len(rows)} source query/export handoff(s).")
    for status, count in sorted(status_counts.items()):
        severity = "error" if status == "config_error" else ("warning" if status in {"local_export_empty"} else "info")
        add_report(report, severity, status, f"{count} query plan row(s).")
    missing_exports = sum(1 for row in rows if row["query_status"] == "planned_query_ready")
    if missing_exports:
        add_report(report, "warning", "exports_needed", f"{missing_exports} planned query export(s) still need reviewed local TSVs.")
    return rows, report


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    query_config_path = resolve(root, args.queries_config)
    catalog_path = resolve(root, args.catalog)
    imports_config_path = resolve(root, args.imports_config)
    try:
        rows, report = plan_queries(root, query_config_path, catalog_path, imports_config_path)
        write_tsv(Path(args.plan_output), QUERY_COLUMNS, rows)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        errors = sum(1 for row in report if row.get("severity") == "error")
        warnings = sum(1 for row in report if row.get("severity") == "warning")
        print(f"Source query plan complete: {len(rows)} queries, {errors} errors, {warnings} warnings.")
        return 1 if errors else 0
    except QueryPlanError as exc:
        write_tsv(Path(args.plan_output), QUERY_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "config", "message": str(exc)}])
        print(f"Source query plan failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
