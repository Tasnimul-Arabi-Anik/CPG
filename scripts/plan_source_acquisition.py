#!/usr/bin/env python3
"""Plan local source acquisition and source-manifest enablement steps."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


PLAN_COLUMNS = [
    "source_id",
    "record_layer",
    "catalog_enabled",
    "catalog_required",
    "manifest_path",
    "manifest_exists",
    "manifest_row_count",
    "import_id",
    "import_configured",
    "import_enabled",
    "import_input_path",
    "import_input_exists",
    "import_input_row_count",
    "import_input_recognized_columns",
    "import_input_identity_columns",
    "import_input_filter_pass_count",
    "import_input_filter_skip_count",
    "import_output_path",
    "import_output_matches_manifest",
    "acquisition_status",
    "priority",
    "next_action",
    "suggested_command",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
SAMPLE_COLUMNS = [
    "record_type",
    "genome_id",
    "accession",
    "source",
    "isolation_host",
    "host_species",
    "host_strain",
    "country",
    "year",
    "phage_lifestyle",
    "genome_length",
    "gc_percent",
    "K_type",
    "O_type",
    "ST",
    "AMR_markers",
    "virulence_markers",
    "raw_sequence_path",
    "notes",
]
COLUMN_ALIASES = {
    "record_type": ["record_type", "type", "entry_type"],
    "genome_id": ["genome_id", "genome", "id", "sample", "sample_id", "assembly", "assembly_id"],
    "accession": ["accession", "accessions", "public_accession", "nucleotide_accession", "genbank_accession", "refseq_accession", "sequence_accession", "accn", "id"],
    "source": ["source", "database", "source_database", "data_source"],
    "isolation_host": ["isolation_host", "isolation host", "host", "reported_host", "isolate_host"],
    "host_species": ["host_species", "host species", "species", "bacterial_species", "organism", "host_organism"],
    "host_strain": ["host_strain", "host strain", "strain", "isolate", "isolate_name"],
    "country": ["country", "location", "region", "geo_location", "geographic_location"],
    "year": ["year", "isolation_year", "collection_year", "publication_year", "date", "collection_date"],
    "phage_lifestyle": ["phage_lifestyle", "lifestyle", "predicted_lifestyle"],
    "genome_length": ["genome_length", "length", "length_bp", "genome_size", "genome_size_bp", "size", "sequence_length"],
    "gc_percent": ["gc_percent", "gc", "gc_content", "gc_percentage", "gc%"],
    "K_type": ["K_type", "k_type", "capsule_type", "k_locus", "K_locus"],
    "O_type": ["O_type", "o_type", "o_antigen", "o_locus", "O_locus"],
    "ST": ["ST", "st", "mlst", "sequence_type"],
    "AMR_markers": ["AMR_markers", "amr_markers", "amr_genes", "resistance_genes"],
    "virulence_markers": ["virulence_markers", "virulence_genes", "virulence_loci"],
    "raw_sequence_path": ["raw_sequence_path", "sequence_path", "fasta", "fasta_path", "genbank_path", "file", "filepath"],
    "notes": ["notes", "note", "comment", "comments", "description", "title", "definition"],
}
DEFAULT_IDENTITY_COLUMNS_ANY = ["genome_id", "accession", "raw_sequence_path"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
PHAGE_TERMS = ("phage", "bacteriophage", "virus", "caudoviricetes", "uroviricota")
KLEBSIELLA_TERM = "klebsiella"


class PlanError(Exception):
    """Raised for invalid source planning configuration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan source-manifest acquisition and enablement steps.")
    parser.add_argument("--catalog", required=True, help="YAML source catalog used by the sample builder.")
    parser.add_argument("--imports-config", required=True, help="YAML source import configuration.")
    parser.add_argument("--plan-output", required=True, help="Output source acquisition plan TSV.")
    parser.add_argument("--report-output", required=True, help="Output source acquisition summary report TSV.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise PlanError("PyYAML is required to read source planning configuration.") from exc
    if not path.exists():
        raise PlanError(f"Configuration does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PlanError(f"Configuration must be a YAML mapping: {path}")
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


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path | str) -> str:
    path_obj = Path(path)
    if not str(path_obj):
        return ""
    try:
        return path_obj.relative_to(root).as_posix()
    except ValueError:
        return path_obj.as_posix()


def delimiter_for(path: Path, configured: str) -> str:
    value = configured.strip().lower()
    if value == "tab":
        return "\t"
    if value == "comma":
        return ","
    if value and value != "auto":
        return configured
    if path.suffix.lower() == ".csv":
        return ","
    return "\t"


def read_table(path: Path, delimiter: str = "\t") -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
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


def recognized_columns(fieldnames: list[str]) -> list[str]:
    by_normalized = {normalize_header(name) for name in fieldnames}
    recognized = []
    for canonical, aliases in COLUMN_ALIASES.items():
        if any(normalize_header(alias) in by_normalized for alias in aliases):
            recognized.append(canonical)
    return recognized


def configured_list(value: object, fallback: list[str]) -> list[str]:
    if value is None:
        return fallback
    if isinstance(value, list):
        parsed = [normalize(item) for item in value]
    else:
        parsed = [item.strip() for item in re.split(r"[;,]", normalize(value))]
    parsed = [item for item in parsed if item]
    return parsed or fallback


def identity_columns_any(catalog: dict, source: dict) -> list[str]:
    value = source.get("identity_columns_any", catalog.get("identity_columns_any"))
    candidates = configured_list(value, DEFAULT_IDENTITY_COLUMNS_ANY)
    return [column for column in candidates if column in SAMPLE_COLUMNS] or DEFAULT_IDENTITY_COLUMNS_ANY


def text_blob(raw: dict[str, str]) -> str:
    return " ".join(value.lower() for value in raw.values() if value)


def row_matches_filters(raw: dict[str, str], spec: dict) -> bool:
    text = text_blob(raw)
    if bool_value(spec.get("require_klebsiella", False), False) and KLEBSIELLA_TERM not in text:
        return False
    if bool_value(spec.get("require_phage_keyword", False), False) and not any(term in text for term in PHAGE_TERMS):
        return False
    include_regex = normalize(spec.get("include_regex"))
    if include_regex and re.search(include_regex, text, flags=re.IGNORECASE) is None:
        return False
    exclude_regex = normalize(spec.get("exclude_regex"))
    if exclude_regex and re.search(exclude_regex, text, flags=re.IGNORECASE):
        return False
    return True


def inspect_export(root: Path, import_spec: dict, catalog: dict, source: dict) -> dict[str, str]:
    input_text = normalize(import_spec.get("input_path")) if import_spec else ""
    if not input_text:
        return {
            "exists": "false",
            "row_count": "0",
            "recognized_columns": "",
            "identity_columns": "",
            "filter_pass_count": "0",
            "filter_skip_count": "0",
        }
    input_path = resolve(root, input_text)
    if not input_path.exists():
        return {
            "exists": "false",
            "row_count": "0",
            "recognized_columns": "",
            "identity_columns": "",
            "filter_pass_count": "0",
            "filter_skip_count": "0",
        }
    delimiter = delimiter_for(input_path, normalize(import_spec.get("delimiter", "auto")))
    fieldnames, rows = read_table(input_path, delimiter)
    recognized = recognized_columns(fieldnames)
    identity_candidates = identity_columns_any(catalog, source)
    identity_present = [column for column in identity_candidates if column in recognized]
    pass_count = sum(1 for row in rows if row_matches_filters(row, import_spec))
    skip_count = len(rows) - pass_count
    return {
        "exists": "true",
        "row_count": str(len(rows)),
        "recognized_columns": ";".join(recognized),
        "identity_columns": ";".join(identity_present),
        "filter_pass_count": str(pass_count),
        "filter_skip_count": str(skip_count),
    }


def layer_for(source_id: str, source: dict) -> str:
    record_type = normalize(source.get("record_type_default")).lower()
    text = f"{source_id} {normalize(source.get('source_label'))}".lower()
    if record_type == "host" or "host" in text:
        return "host_genomes"
    if record_type == "prophage" or "prophage" in text:
        return "prophages"
    if "metagenomic" in text or record_type == "metagenomic_viral_contig":
        return "metagenomic_discovery"
    if "literature" in text:
        return "literature_curated_phages"
    return "cultured_phages"


def priority_for(layer: str, required: bool) -> str:
    if required:
        return "required"
    if layer in {"cultured_phages", "prophages", "host_genomes"}:
        return "primary"
    if layer == "literature_curated_phages":
        return "primary_manual"
    return "optional_discovery"


def imports_by_output(root: Path, imports_config: dict) -> dict[str, dict]:
    output: dict[str, dict] = {}
    imports = imports_config.get("imports", [])
    if not isinstance(imports, list):
        raise PlanError("source import config 'imports' must be a list")
    for index, spec in enumerate(imports, start=1):
        if not isinstance(spec, dict):
            continue
        import_id = normalize(spec.get("import_id")) or f"import_{index}"
        spec = dict(spec)
        spec["import_id"] = import_id
        output_text = normalize(spec.get("output_path"))
        if output_text:
            output[display_path(root, resolve(root, output_text))] = spec
        output[import_id] = spec
    return output


def matching_import(root: Path, source_id: str, manifest_path: Path, import_index: dict[str, dict]) -> dict:
    manifest_key = display_path(root, manifest_path)
    if manifest_key in import_index:
        return import_index[manifest_key]
    if source_id in import_index:
        return import_index[source_id]
    return {}


def command_import(imports_config_path: Path, root: Path) -> str:
    return f"python scripts/import_source_manifests.py --config {display_path(root, imports_config_path)} --report-output results/qc/source_import_report.tsv"


def command_build() -> str:
    return "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_audit stage_0_samples stage_1_manifest stage_1_sequence_qc"


def classify(
    root: Path,
    manifest_path: Path,
    manifest_rows: int,
    manifest_exists: bool,
    catalog_enabled: bool,
    catalog_required: bool,
    import_spec: dict,
    imports_config_path: Path,
    export_summary: dict[str, str],
    output_matches: bool,
) -> tuple[str, str, str]:
    import_configured = bool(import_spec)
    import_enabled = bool_value(import_spec.get("enabled"), False) if import_configured else False
    input_text = normalize(import_spec.get("input_path")) if import_configured else ""
    input_exists = export_summary.get("exists") == "true"
    input_rows = int(export_summary.get("row_count") or "0")
    identity_columns = export_summary.get("identity_columns", "")
    filter_pass = int(export_summary.get("filter_pass_count") or "0")

    if catalog_enabled and manifest_rows > 0:
        return "ready_for_sample_build", "No action required before sample build.", command_build()
    if manifest_rows > 0 and not catalog_enabled:
        return "manifest_populated_but_catalog_disabled", "Review rows, then set this source to enabled: true in config/source_catalog.yaml.", command_build()
    if catalog_enabled and manifest_rows == 0:
        return "catalog_enabled_but_manifest_empty", "Populate the enabled source manifest before using it for production analysis.", "Populate " + display_path(root, manifest_path)
    if import_configured and input_exists and not output_matches:
        return "import_output_mismatch", "Fix import output_path so it writes to the source catalog manifest path.", "Edit config/source_imports.yaml"
    if import_configured and input_exists and input_rows == 0:
        return "local_export_empty", "Add data rows to the local export before enabling import.", "Populate " + input_text
    if import_configured and input_exists and not identity_columns:
        return "local_export_missing_identity", "Add at least one identity column recognized by the importer: genome_id, accession, or raw_sequence_path.", "Edit " + input_text
    if import_configured and input_exists and filter_pass == 0:
        return "local_export_filters_exclude_all", "Review import filters or source rows; no rows currently pass the configured filters.", "Edit " + input_text
    if import_configured and input_exists and not import_enabled:
        return "local_export_ready_import_disabled", "Review the local export, then set this import to enabled: true in the source import config.", command_import(imports_config_path, root)
    if import_configured and input_exists and import_enabled:
        return "local_export_ready_for_import", "Run source import, review the source manifest, then enable the matching catalog source.", command_import(imports_config_path, root)
    if import_configured and not input_exists:
        return "waiting_for_local_export", "Place a reviewed metadata export at the configured input path or update input_path.", "Create " + input_text
    if manifest_exists:
        return "manifest_template_empty", "Add curated rows to the source manifest or configure an import for this source.", "Populate " + display_path(root, manifest_path)
    if catalog_required:
        return "required_manifest_missing", "Create the required source manifest before running production analyses.", "Create " + display_path(root, manifest_path)
    return "optional_manifest_missing", "Create/populate this manifest when the source becomes part of the study.", "Create " + display_path(root, manifest_path)


def plan_sources(root: Path, catalog_path: Path, imports_config_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    catalog = load_yaml(catalog_path)
    imports_config = load_yaml(imports_config_path)
    sources = catalog.get("sources", [])
    if not isinstance(sources, list):
        raise PlanError("source catalog 'sources' must be a list")
    import_index = imports_by_output(root, imports_config)
    plan: list[dict[str, str]] = []
    report: list[dict[str, str]] = []

    if not sources:
        add_report(report, "warning", "sources", "No sources are configured in the source catalog.")

    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            add_report(report, "error", f"source_{index}", "Source entry is not a mapping.")
            continue
        source_id = normalize(source.get("source_id")) or f"source_{index}"
        manifest_text = normalize(source.get("path"))
        manifest_path = resolve(root, manifest_text) if manifest_text else Path("")
        manifest_exists = bool(manifest_text and manifest_path.exists())
        _, manifest_rows_data = read_table(manifest_path, "\t") if manifest_exists else ([], [])
        manifest_rows = len(manifest_rows_data)
        catalog_enabled = bool_value(source.get("enabled"), True)
        catalog_required = bool_value(source.get("required"), False)
        layer = layer_for(source_id, source)
        import_spec = matching_import(root, source_id, manifest_path, import_index) if manifest_text else {}
        import_id = normalize(import_spec.get("import_id")) if import_spec else ""
        import_enabled = bool_value(import_spec.get("enabled"), False) if import_spec else False
        import_input_text = normalize(import_spec.get("input_path")) if import_spec else ""
        import_output_text = normalize(import_spec.get("output_path")) if import_spec else ""
        import_input_path = resolve(root, import_input_text) if import_input_text else Path("")
        import_output_path = resolve(root, import_output_text) if import_output_text else Path("")
        export_summary = inspect_export(root, import_spec, catalog, source)
        output_matches = bool(import_output_text and manifest_text and display_path(root, import_output_path) == display_path(root, manifest_path))
        status, next_action, command = classify(
            root,
            manifest_path,
            manifest_rows,
            manifest_exists,
            catalog_enabled,
            catalog_required,
            import_spec,
            imports_config_path,
            export_summary,
            output_matches,
        )
        plan.append(
            {
                "source_id": source_id,
                "record_layer": layer,
                "catalog_enabled": str(catalog_enabled).lower(),
                "catalog_required": str(catalog_required).lower(),
                "manifest_path": display_path(root, manifest_path) if manifest_text else "",
                "manifest_exists": str(manifest_exists).lower(),
                "manifest_row_count": str(manifest_rows),
                "import_id": import_id,
                "import_configured": str(bool(import_spec)).lower(),
                "import_enabled": str(import_enabled).lower(),
                "import_input_path": display_path(root, import_input_path) if import_input_text else "",
                "import_input_exists": export_summary["exists"],
                "import_input_row_count": export_summary["row_count"],
                "import_input_recognized_columns": export_summary["recognized_columns"],
                "import_input_identity_columns": export_summary["identity_columns"],
                "import_input_filter_pass_count": export_summary["filter_pass_count"],
                "import_input_filter_skip_count": export_summary["filter_skip_count"],
                "import_output_path": display_path(root, import_output_path) if import_output_text else "",
                "import_output_matches_manifest": str(output_matches).lower(),
                "acquisition_status": status,
                "priority": priority_for(layer, catalog_required),
                "next_action": next_action,
                "suggested_command": command,
                "notes": normalize(source.get("notes")),
            }
        )

    status_counts: dict[str, int] = {}
    for row in plan:
        status_counts[row["acquisition_status"]] = status_counts.get(row["acquisition_status"], 0) + 1
    add_report(report, "info", "sources", f"Planned acquisition for {len(plan)} configured sources.")
    for status, count in sorted(status_counts.items()):
        severity = "info" if status == "ready_for_sample_build" else "warning"
        add_report(report, severity, status, f"{count} source(s).")
    ready = sum(1 for row in plan if row["acquisition_status"] == "ready_for_sample_build")
    if ready == 0:
        add_report(report, "warning", "production_data", "No configured source is currently ready for production sample building.")
    return plan, report


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    catalog_path = resolve(root, args.catalog)
    imports_config_path = resolve(root, args.imports_config)
    try:
        plan, report = plan_sources(root, catalog_path, imports_config_path)
        write_tsv(Path(args.plan_output), PLAN_COLUMNS, plan)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        warnings = sum(1 for row in report if row.get("severity") == "warning")
        errors = sum(1 for row in report if row.get("severity") == "error")
        print(f"Source acquisition plan complete: {len(plan)} sources, {errors} errors, {warnings} warnings.")
        return 1 if errors else 0
    except PlanError as exc:
        report = [{"severity": "error", "item": "config", "message": str(exc)}]
        write_tsv(Path(args.plan_output), PLAN_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        print(f"Source acquisition plan failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
