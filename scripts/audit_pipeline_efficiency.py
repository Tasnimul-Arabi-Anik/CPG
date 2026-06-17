#!/usr/bin/env python3
"""Audit reviewer-facing pipeline scope and efficiency safeguards."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


AUDIT_COLUMNS = [
    "check_id",
    "area",
    "reviewer_question",
    "evidence_path",
    "evidence_summary",
    "status",
    "blocking_for_efficiency",
    "recommendation",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit scope and efficiency safeguards for reviewer-facing production design.")
    parser.add_argument("--workflow-config", required=True, help="Workflow config YAML.")
    parser.add_argument("--source-catalog", required=True, help="Source catalog YAML.")
    parser.add_argument("--source-imports", required=True, help="Source imports YAML.")
    parser.add_argument("--thresholds", required=True, help="Thresholds YAML.")
    parser.add_argument("--external-evidence-plan", required=True, help="External evidence plan TSV.")
    parser.add_argument("--sequence-acquisition-plan", required=True, help="Sequence acquisition plan TSV.")
    parser.add_argument("--output", required=True, help="Pipeline efficiency audit TSV.")
    parser.add_argument("--report-output", required=True, help="Pipeline efficiency audit report TSV.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit("PyYAML is required to read YAML configs.") from exc
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
        return reader.fieldnames or [], rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def nested_get(data: dict, *keys: str, default: object = "") -> object:
    current: object = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def add_check(
    rows: list[dict[str, str]],
    check_id: str,
    area: str,
    reviewer_question: str,
    evidence_path: str,
    evidence_summary: str,
    status: str,
    recommendation: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "area": area,
            "reviewer_question": reviewer_question,
            "evidence_path": evidence_path,
            "evidence_summary": evidence_summary,
            "status": status,
            "blocking_for_efficiency": "true" if status == "fail" else "false",
            "recommendation": recommendation,
        }
    )


def main() -> None:
    args = parse_args()
    workflow_path = Path(args.workflow_config)
    catalog_path = Path(args.source_catalog)
    imports_path = Path(args.source_imports)
    thresholds_path = Path(args.thresholds)
    evidence_path = Path(args.external_evidence_plan)
    sequence_path = Path(args.sequence_acquisition_plan)

    display_root = Path.cwd()
    workflow_display = display_path(workflow_path, display_root)
    catalog_display = display_path(catalog_path, display_root)
    imports_display = display_path(imports_path, display_root)
    thresholds_display = display_path(thresholds_path, display_root)
    evidence_display = display_path(evidence_path, display_root)
    sequence_display = display_path(sequence_path, display_root)

    workflow = load_yaml(workflow_path)
    catalog = load_yaml(catalog_path)
    imports_config = load_yaml(imports_path)
    thresholds = load_yaml(thresholds_path)
    evidence_fields, evidence_rows = read_tsv(evidence_path)
    sequence_fields, sequence_rows = read_tsv(sequence_path)

    sources = catalog.get("sources", []) if isinstance(catalog.get("sources", []), list) else []
    imports = imports_config.get("imports", []) if isinstance(imports_config.get("imports", []), list) else []
    rows: list[dict[str, str]] = []

    enabled_sources = [source for source in sources if bool_value(source.get("enabled", ""))]
    source_ids = {str(source.get("source_id", "")) for source in sources}
    enabled_source_ids = {str(source.get("source_id", "")) for source in enabled_sources}
    cultured_ids = {"inphared_klebsiella_phages", "ncbi_virus_klebsiella_phages", "literature_klebsiella_phages"}
    metagenomic_enabled = "metagenomic_discovery_contigs" in enabled_source_ids
    host_enabled = "klebsiella_host_genomes" in enabled_source_ids
    prophage_enabled = "klebsiella_prophages" in enabled_source_ids
    primary_enabled = bool(cultured_ids & enabled_source_ids)

    add_check(
        rows,
        "E01",
        "source_scope",
        "Does the atlas start from reviewed source layers instead of scraping indiscriminately?",
        catalog_display,
        f"sources={len(sources)}; enabled={len(enabled_sources)}; primary_cultured_enabled={primary_enabled}; host_enabled={host_enabled}; prophage_enabled={prophage_enabled}",
        "pass" if primary_enabled and {"klebsiella_host_genomes", "klebsiella_prophages"}.issubset(source_ids) else "warn",
        "Keep source expansion staged through reviewed exports and source manifests before large production runs.",
    )

    add_check(
        rows,
        "E02",
        "discovery_scope",
        "Are metagenomic discovery contigs kept separate from the primary atlas?",
        catalog_display,
        f"metagenomic_discovery_contigs_enabled={metagenomic_enabled}",
        "pass" if not metagenomic_enabled else "warn",
        "Keep discovery contigs disabled or clearly labeled unless the analysis explicitly targets the discovery layer.",
    )

    import_filters = [
        str(item.get("import_id", ""))
        for item in imports
        if str(item.get("record_type_default", "")) in {"phage", "prophage"} and bool_value(item.get("require_klebsiella", ""))
    ]
    add_check(
        rows,
        "E03",
        "import_filtering",
        "Do imports enforce Klebsiella/phage filters before sample generation?",
        imports_display,
        f"filtered_phage_like_imports={len(import_filters)}; import_ids={';'.join(import_filters) or 'NA'}",
        "pass" if import_filters else "fail",
        "Require Klebsiella and phage filters for public cultured-phage/prophage imports before enabling them.",
    )

    raw_directory = str(nested_get(workflow, "sequence_acquisition", "raw_directory", default=""))
    review_packet_enabled = bool_value(nested_get(workflow, "sequence_fetch_review_packet", "enabled", default=""))
    add_check(
        rows,
        "E04",
        "raw_data_boundary",
        "Does the workflow avoid uncontrolled raw-data writes during normal validation?",
        workflow_display,
        f"raw_directory={raw_directory or 'NA'}; sequence_fetch_review_packet_enabled={review_packet_enabled}",
        "pass" if raw_directory.startswith("data/raw") and review_packet_enabled else "warn",
        "Use review packets and command manifests for sequence acquisition; do not treat generated fetch commands as reviewed raw data.",
    )

    dereplication = thresholds.get("dereplication", {}) if isinstance(thresholds.get("dereplication", {}), dict) else {}
    identity = dereplication.get("species_like_identity_percent", "")
    coverage = dereplication.get("species_like_coverage_percent", "")
    representative_order = dereplication.get("representative_selection_order", [])
    add_check(
        rows,
        "E05",
        "dereplication",
        "Will redundant public phage genomes be collapsed before downstream counting and interpretation?",
        thresholds_display,
        f"species_like_identity_percent={identity}; species_like_coverage_percent={coverage}; representative_selection_rules={len(representative_order) if isinstance(representative_order, list) else 0}",
        "pass" if str(identity) and str(coverage) and isinstance(representative_order, list) and representative_order else "fail",
        "Keep dereplication thresholds and representative selection rules in config/thresholds.yaml.",
    )

    overlap_enabled = bool_value(nested_get(workflow, "source_overlap", "enabled", default=""))
    overlap_path = str(nested_get(workflow, "source_overlap", "overlaps", default=""))
    add_check(
        rows,
        "E06",
        "source_overlap",
        "Will duplicate records across INPHARED, NCBI, literature, and prophage sources be surfaced?",
        workflow_display,
        f"source_overlap_enabled={overlap_enabled}; overlap_output={overlap_path or 'NA'}",
        "pass" if overlap_enabled and overlap_path.startswith("results/") else "fail",
        "Run the source-overlap audit before interpreting atlas sizes or source enrichments.",
    )

    handoff_enabled = bool_value(nested_get(workflow, "production_evidence_handoff", "enabled", default=""))
    templates_enabled = bool_value(nested_get(workflow, "external_evidence_templates", "enabled", default=""))
    add_check(
        rows,
        "E07",
        "production_evidence",
        "Are bridge outputs separated from production-grade external tool evidence?",
        workflow_display,
        f"production_evidence_handoff_enabled={handoff_enabled}; external_evidence_templates_enabled={templates_enabled}; evidence_rows={len(evidence_rows)}",
        "pass" if handoff_enabled and templates_enabled and evidence_rows else "warn",
        "Keep bridge evidence labeled and replace it with reviewed TSVs from standard tools before strong biological claims.",
    )

    compute_heavy = {
        row.get("evidence_id", "")
        for row in evidence_rows
        if row.get("tool_status") in {"missing_tool", "missing_tool_or_input"} or row.get("evidence_status") in {"missing_tool_or_input", "manual_evidence_required"}
    }
    add_check(
        rows,
        "E08",
        "compute_strategy",
        "Are compute-heavy production tools externalized as reviewed evidence inputs instead of hidden inside lightweight validation?",
        evidence_display,
        f"external_evidence_fields={len(evidence_fields)}; planned_external_layers={len(evidence_rows)}; compute_heavy_pending={len(compute_heavy)}",
        "pass" if evidence_rows and "evidence_origin" in evidence_fields else "warn",
        "Run production tools on an appropriate workstation/HPC/container and configure reviewed output TSVs under config/workflow.yaml.",
    )

    fetchable = sum(1 for row in sequence_rows if row.get("retrieval_method") not in {"", "manual_curation_required"} and row.get("acquisition_status") != "local_sequence_available")
    local = sum(1 for row in sequence_rows if row.get("acquisition_status") == "local_sequence_available")
    add_check(
        rows,
        "E09",
        "sequence_staging",
        "Does the workflow stage sequence acquisition before genome-level analyses?",
        sequence_display,
        f"sequence_rows={len(sequence_rows)}; local_sequence_available={local}; fetchable_or_planned={fetchable}",
        "pass" if sequence_rows and "acquisition_status" in sequence_fields else "warn",
        "Acquire reviewed FASTA/GenBank files before production dereplication, standardized annotation, and structural evidence generation.",
    )

    statuses = [row["status"] for row in rows]
    report_status = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
    report = [
        {
            "severity": "error" if report_status == "fail" else ("warning" if report_status == "warn" else "info"),
            "item": "pipeline_efficiency",
            "message": f"checks={len(rows)}; pass={statuses.count('pass')}; warn={statuses.count('warn')}; fail={statuses.count('fail')}",
        }
    ]
    write_tsv(Path(args.output), AUDIT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)


if __name__ == "__main__":
    main()
