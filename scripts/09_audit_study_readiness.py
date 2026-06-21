#!/usr/bin/env python3
"""Audit study/manuscript readiness from current workflow outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


READINESS_COLUMNS = [
    "requirement_id",
    "area",
    "requirement",
    "evidence_path",
    "evidence_summary",
    "status",
    "blocking_for_manuscript",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


REQUIREMENTS = [
    (
        "R01",
        "dataset_curation",
        "At least one real or fixture sample row is present in the audited sample table.",
        "samples",
    ),
    (
        "R02",
        "source_curation",
        "At least one enabled source manifest is ready and no source-audit errors are present.",
        "sources",
    ),
    (
        "R03",
        "source_acquisition",
        "Source query/acquisition plans identify reviewed export handoffs, generated export templates, validated reviewed exports, and at least one source ready for import/build or already enabled for sample generation.",
        "source_acquisition",
    ),
    (
        "R04",
        "source_work_order_acceptance",
        "Reviewed source curation work orders are accepted, or sample-support requirements already pass for the audited dataset.",
        "source_work_order_acceptance",
    ),
    (
        "R05",
        "tooling",
        "Required workflow tools are available and planned missing tools are explicitly recorded.",
        "tools",
    ),
    (
        "R06",
        "sequence_acquisition",
        "Sequence acquisition plan and fetch manifest identify local FASTA-backed records, accession-backed commands, or actionable accession/path curation steps.",
        "sequence_acquisition",
    ),
    (
        "R07",
        "sequence_qc",
        "Local FASTA-backed records have sequence QC status recorded and passing FASTA rows are available for genome-level analysis.",
        "sequence_qc",
    ),
    (
        "R08",
        "external_evidence",
        "External evidence plan has schema-valid configured inputs or actionable tool/input handoffs and generated evidence templates for each major analysis layer.",
        "external_evidence",
    ),
    (
        "R09",
        "dereplication",
        "Phage-like records have species-like cluster and representative outputs.",
        "clusters",
    ),
    (
        "R10",
        "annotation_pangenome",
        "Phage annotation and pangenome tables contain data rows.",
        "annotations",
    ),
    (
        "R11",
        "rbp_depolymerase",
        "RBP/depolymerase candidate and module tables contain candidate evidence.",
        "rbp",
    ),
    (
        "R12",
        "host_features",
        "Host K/O/ST feature tables and phage-host links contain usable host metadata.",
        "host_features",
    ),
    (
        "R13",
        "defense_counterdefense",
        "Host defense, phage anti-defense, and compatibility tables contain usable rows.",
        "defense",
    ),
    (
        "R14",
        "sample_support",
        "H1-H6 meet configured minimum sample-support requirements before hypothesis interpretation.",
        "sample_support",
    ),
    (
        "R15",
        "hypothesis_tests",
        "H1-H6 have quantitative test rows with at least one ok or analysis-ready row per hypothesis.",
        "hypotheses",
    ),
    (
        "R16",
        "figures",
        "All planned figures have source data and draft SVGs.",
        "figures",
    ),
    (
        "R17",
        "documentation_claims",
        "Methods, limitations, figure plan, and claim ledger are present and validation-passing.",
        "docs",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit study/manuscript readiness from workflow outputs.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--results-dir", default="results", help="Audited results directory.")
    parser.add_argument("--samples", default="config/samples.tsv", help="Sample table used by the audited workflow.")
    parser.add_argument("--readiness-output", required=True, help="Output readiness matrix TSV.")
    parser.add_argument("--report-output", required=True, help="Output readiness summary report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


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


def status_row(
    requirement_id: str,
    area: str,
    requirement: str,
    evidence_path: Path,
    root: Path,
    evidence_summary: str,
    status: str,
    blocking: bool,
    next_action: str,
) -> dict[str, str]:
    return {
        "requirement_id": requirement_id,
        "area": area,
        "requirement": requirement,
        "evidence_path": display_path(root, evidence_path) if str(evidence_path) else "NA",
        "evidence_summary": evidence_summary,
        "status": status,
        "blocking_for_manuscript": str(blocking).lower(),
        "next_action": next_action,
    }


def count_rows(path: Path) -> int:
    _, rows = read_tsv(path)
    return len(rows)


def evaluate_requirement(requirement: tuple[str, str, str, str], root: Path, results_dir: Path, samples: Path) -> dict[str, str]:
    req_id, area, text, key = requirement

    if key == "samples":
        rows = count_rows(samples)
        status = "pass" if rows > 0 else "fail"
        return status_row(req_id, area, text, samples, root, f"sample_rows={rows}", status, rows == 0, "Populate source manifests and rebuild samples.tsv." if rows == 0 else "No action required.")

    if key == "sources":
        readiness = results_dir / "qc/source_catalog_readiness.tsv"
        report = results_dir / "qc/source_catalog_audit_report.tsv"
        _, readiness_rows = read_tsv(readiness)
        _, report_rows = read_tsv(report)
        ready_enabled = [row for row in readiness_rows if row.get("enabled") == "true" and row.get("ready_status") in {"ready_enabled", "ready_with_defaults"}]
        errors = [row for row in report_rows if row.get("severity") == "error"]
        placeholders = [row for row in readiness_rows if row.get("ready_status") == "planned_placeholder"]
        if errors:
            status = "fail"
            action = "Fix source catalog errors before building samples."
        elif ready_enabled:
            status = "pass"
            action = "No action required."
        else:
            status = "fail"
            action = "Populate and enable at least one curated source manifest."
        summary = f"ready_enabled={len(ready_enabled)}; placeholders={len(placeholders)}; errors={len(errors)}"
        return status_row(req_id, area, text, readiness, root, summary, status, status == "fail", action)

    if key == "source_acquisition":
        path = results_dir / "qc/source_acquisition_plan.tsv"
        query_path = results_dir / "qc/source_query_plan.tsv"
        template_path = results_dir / "qc/source_export_template_manifest.tsv"
        validation_path = results_dir / "qc/source_export_validation.tsv"
        _, rows = read_tsv(path)
        _, query_rows = read_tsv(query_path)
        _, template_rows = read_tsv(template_path)
        _, validation_rows = read_tsv(validation_path)
        ready = [row for row in rows if row.get("acquisition_status") in {"ready_for_sample_build", "manifest_populated_but_catalog_disabled", "local_export_ready_import_disabled", "local_export_ready_for_import"}]
        waiting = [row for row in rows if row.get("acquisition_status") == "waiting_for_local_export"]
        invalid_statuses = {"local_export_empty", "local_export_missing_identity", "local_export_filters_exclude_all", "import_output_mismatch", "catalog_enabled_but_manifest_empty", "required_manifest_missing"}
        invalid = [row for row in rows if row.get("acquisition_status") in invalid_statuses]
        blocking_invalid = [
            row
            for row in invalid
            if row.get("catalog_enabled") == "true"
            or row.get("catalog_required") == "true"
            or row.get("import_enabled") == "true"
        ]
        query_planned = [row for row in query_rows if row.get("query_status") == "planned_query_ready"]
        query_exports = [row for row in query_rows if row.get("query_status") == "local_export_present"]
        query_errors = [row for row in query_rows if row.get("query_status") == "config_error"]
        template_ready = [row for row in template_rows if row.get("template_status") == "template_ready"]
        template_errors = [row for row in template_rows if row.get("template_status") == "template_missing_identity_column"]
        export_ready = [row for row in validation_rows if row.get("validation_status") == "export_ready"]
        export_missing = [row for row in validation_rows if row.get("validation_status") == "export_missing"]
        export_validation_errors = [row for row in validation_rows if row.get("blocking_issue") == "true"]
        if blocking_invalid or query_errors or template_errors or export_validation_errors:
            status = "fail"
            action = "Fix invalid enabled/required source exports, manifests, or query/import path mismatches listed in qc plans."
        elif ready:
            status = "pass"
            action = "No action required."
        elif query_exports or export_ready:
            status = "fail"
            action = "Import validated reviewed exports and enable matching source catalog entries."
        elif query_planned:
            status = "fail"
            action = "Create reviewed local exports listed in source_query_plan.tsv, then rerun source import/build."
        else:
            status = "fail"
            action = "Place reviewed local source exports or populate source manifests, then rerun source import/build."
        summary = (
            f"sources={len(rows)}; ready_or_importable={len(ready)}; waiting_for_export={len(waiting)}; "
            f"invalid={len(invalid)}; blocking_invalid={len(blocking_invalid)}; query_rows={len(query_rows)}; planned_queries={len(query_planned)}; "
            f"query_exports={len(query_exports)}; query_errors={len(query_errors)}; "
            f"templates_ready={len(template_ready)}; template_errors={len(template_errors)}; "
            f"export_ready={len(export_ready)}; export_missing={len(export_missing)}; export_validation_errors={len(export_validation_errors)}"
        )
        return status_row(req_id, area, text, path, root, summary, status, status == "fail", action)

    if key == "source_work_order_acceptance":
        path = results_dir / "qc/source_work_order_acceptance.tsv"
        packet_manifest = results_dir / "qc/source_work_order_packet_manifest.tsv"
        sample_support = results_dir / "qc/sample_support_by_hypothesis.tsv"
        _, rows = read_tsv(path)
        _, packet_rows = read_tsv(packet_manifest)
        _, support_rows = read_tsv(sample_support)
        ready_support = [row for row in support_rows if row.get("support_status") == "ready_minimum_sample_support"]
        blocked_support = [row for row in support_rows if row.get("support_status") == "blocked_minimum_sample_support"]
        accepted = [row for row in rows if row.get("acceptance_status") == "accepted"]
        blocking = [row for row in rows if row.get("blocking_issue") == "true"]
        first_blocker = sorted(blocking, key=lambda row: row.get("work_order_id", ""))[0] if blocking else {}
        first_packet = "NA"
        if first_blocker:
            packet_by_work_order = {row.get("work_order_id", ""): row for row in packet_rows}
            first_packet = packet_by_work_order.get(first_blocker.get("work_order_id", ""), {}).get("packet_path", "NA")
        if len(ready_support) >= 6 and not blocked_support:
            status = "pass"
            is_blocking = False
            action = "No action required; H1-H6 sample-support requirements already pass for this audited dataset."
        elif blocking:
            status = "fail"
            is_blocking = True
            action = (
                f"Complete the first blocking source work-order packet ({first_packet}) and rerun source work-order acceptance."
                if first_packet != "NA"
                else "Complete blocking source work orders and rerun source work-order acceptance."
            )
        elif rows:
            status = "pass"
            is_blocking = False
            action = "No action required."
        else:
            status = "warn"
            is_blocking = False
            action = "Generate source curation work orders and acceptance checks if sample support remains blocked."
        summary = (
            f"work_orders={len(rows)}; accepted={len(accepted)}; blocking={len(blocking)}; "
            f"ready_hypotheses={len(ready_support)}; blocked_hypotheses={len(blocked_support)}; first_blocker={first_packet}"
        )
        return status_row(req_id, area, text, path, root, summary, status, is_blocking, action)

    if key == "tools":
        path = results_dir / "qc/tool_availability.tsv"
        _, rows = read_tsv(path)
        required_missing = [row for row in rows if row.get("required_for_current_workflow") == "true" and row.get("availability_status") != "available"]
        optional_missing = [row for row in rows if row.get("required_for_current_workflow") != "true" and row.get("availability_status") != "available"]
        status = "fail" if required_missing else ("warn" if optional_missing else "pass")
        action = "Install required workflow tools." if required_missing else ("Install planned production tools or provide their output TSVs before final analysis." if optional_missing else "No action required.")
        return status_row(req_id, area, text, path, root, f"required_missing={len(required_missing)}; optional_missing={len(optional_missing)}", status, bool(required_missing), action)

    if key == "sequence_acquisition":
        path = results_dir / "qc/sequence_acquisition_plan.tsv"
        fetch_manifest = results_dir / "qc/sequence_fetch_manifest.tsv"
        _, rows = read_tsv(path)
        _, fetch_rows = read_tsv(fetch_manifest)
        local = [row for row in rows if row.get("acquisition_status") == "local_sequence_available"]
        fetchable = [row for row in rows if row.get("acquisition_status") in {"accession_ready_for_fetch", "configured_path_missing_fetchable"}]
        metadata_only = [row for row in rows if row.get("acquisition_status") == "metadata_only_no_accession"]
        missing_path = [row for row in rows if row.get("acquisition_status") == "configured_path_missing_no_accession"]
        fetch_commands = [row for row in fetch_rows if row.get("command_class") == "fetch_command"]
        manual_curation = [row for row in fetch_rows if row.get("command_class") in {"manual_curation", "manual_review"}]
        already_local = [row for row in fetch_rows if row.get("command_class") == "already_local"]
        if local:
            status = "warn" if (fetchable or metadata_only or missing_path) else "pass"
            blocking = False
            action = "Acquire FASTA files or add accession/path metadata for remaining non-local records." if status == "warn" else "No action required."
        elif fetchable:
            status = "warn"
            blocking = True
            action = "Review and run accession-backed commands listed in sequence_fetch_manifest.tsv."
        elif rows:
            status = "fail"
            blocking = True
            action = "Add accession or raw_sequence_path metadata for records in sequence_acquisition_plan.tsv."
        else:
            status = "fail"
            blocking = True
            action = "Populate sample rows before sequence acquisition planning."
        summary = (
            f"records={len(rows)}; local={len(local)}; fetchable={len(fetchable)}; metadata_only={len(metadata_only)}; "
            f"missing_path_no_accession={len(missing_path)}; fetch_manifest_rows={len(fetch_rows)}; "
            f"fetch_commands={len(fetch_commands)}; manual_curation={len(manual_curation)}; already_local={len(already_local)}"
        )
        return status_row(req_id, area, text, path, root, summary, status, blocking, action)

    if key == "sequence_qc":
        path = results_dir / "qc/genome_sequence_qc.tsv"
        _, rows = read_tsv(path)
        passing = [row for row in rows if row.get("passes_sequence_qc") == "true"]
        no_sequence = [row for row in rows if row.get("sequence_qc_status") == "no_sequence_provided"]
        failures = [row for row in rows if row.get("sequence_qc_status") not in {"", "pass", "no_sequence_provided"}]
        if passing:
            status = "warn" if no_sequence else "pass"
            blocking = False
            action = "Add local FASTA/GenBank files for metadata-only records before production analyses." if no_sequence else "No action required."
        else:
            status = "fail"
            blocking = True
            action = "Add local genome files and rerun sequence QC."
        summary = f"qc_rows={len(rows)}; passing={len(passing)}; no_sequence={len(no_sequence)}; failures={len(failures)}"
        return status_row(req_id, area, text, path, root, summary, status, blocking, action)

    if key == "external_evidence":
        path = results_dir / "qc/external_evidence_plan.tsv"
        template_path = results_dir / "qc/external_evidence_template_manifest.tsv"
        _, rows = read_tsv(path)
        _, template_rows = read_tsv(template_path)
        ready = [row for row in rows if row.get("evidence_status") == "provided_input_ready"]
        runnable = [row for row in rows if row.get("evidence_status") == "ready_to_run_external_tool"]
        waiting_sequence = [row for row in rows if row.get("evidence_status") == "waiting_for_sequence_data"]
        invalid = [row for row in rows if row.get("evidence_status") in {"configured_input_missing", "configured_input_empty", "configured_input_schema_invalid"}]
        missing_tool = [row for row in rows if row.get("evidence_status") == "missing_tool_or_input"]
        manual = [row for row in rows if row.get("evidence_status") == "manual_evidence_required"]
        templates_ready = [row for row in template_rows if row.get("template_status") == "template_ready"]
        templates_configured = [row for row in template_rows if row.get("template_status") == "configured_input_ready"]
        template_missing = len(rows) - len(template_rows) if rows else 0
        if rows and len(ready) == len(rows):
            status = "pass"
            blocking = False
            action = "No action required."
        elif invalid or template_missing > 0:
            status = "fail"
            blocking = True
            action = "Fix configured external evidence TSV paths, row counts, required columns, or missing evidence templates."
        elif waiting_sequence:
            status = "fail"
            blocking = True
            action = "Acquire sequence-backed records before external evidence generation."
        elif runnable or missing_tool or manual:
            status = "warn"
            blocking = True
            action = "Run planned external tools or provide schema-valid precomputed evidence TSVs."
        else:
            status = "fail"
            blocking = True
            action = "Generate external evidence plan after sequence QC."
        summary = (
            f"evidence={len(rows)}; ready={len(ready)}; runnable={len(runnable)}; waiting_sequence={len(waiting_sequence)}; "
            f"invalid={len(invalid)}; missing_tool={len(missing_tool)}; manual={len(manual)}; "
            f"templates_ready={len(templates_ready)}; templates_configured={len(templates_configured)}; template_missing={template_missing}"
        )
        return status_row(req_id, area, text, path, root, summary, status, blocking, action)

    if key == "clusters":
        clusters = results_dir / "clusters/phage_clusters.tsv"
        reps = results_dir / "clusters/representatives.tsv"
        cluster_rows = count_rows(clusters)
        rep_rows = count_rows(reps)
        status = "pass" if cluster_rows > 0 and rep_rows > 0 else "fail"
        return status_row(req_id, area, text, clusters, root, f"cluster_rows={cluster_rows}; representative_rows={rep_rows}", status, status == "fail", "Populate phage-like genomes and rerun dereplication." if status == "fail" else "No action required.")

    if key == "annotations":
        annotations = results_dir / "annotations/phage_annotations.tsv"
        pangenome = results_dir / "annotations/pangenome_matrix.tsv"
        annotation_rows = count_rows(annotations)
        pangenome_rows = count_rows(pangenome)
        status = "pass" if annotation_rows > 0 and pangenome_rows > 0 else "fail"
        return status_row(req_id, area, text, annotations, root, f"annotation_rows={annotation_rows}; pangenome_rows={pangenome_rows}", status, status == "fail", "Provide Pharokka/PHROGs-style annotation input or run annotation tooling." if status == "fail" else "No action required.")

    if key == "rbp":
        candidates = results_dir / "rbp_depolymerase/candidates.tsv"
        modules = results_dir / "rbp_depolymerase/module_clusters.tsv"
        candidate_rows = count_rows(candidates)
        module_rows = count_rows(modules)
        status = "pass" if candidate_rows > 0 and module_rows > 0 else "fail"
        return status_row(req_id, area, text, candidates, root, f"candidate_rows={candidate_rows}; module_rows={module_rows}", status, status == "fail", "Generate annotation/domain/structural evidence and rerun RBP prioritization." if status == "fail" else "No action required.")

    if key == "host_features":
        hosts = results_dir / "host_features/host_metadata.tsv"
        links = results_dir / "host_features/phage_host_links.tsv"
        _, host_rows = read_tsv(hosts)
        _, link_rows = read_tsv(links)
        usable_links = [row for row in link_rows if not is_missing(row.get("K_type")) or not is_missing(row.get("O_type")) or not is_missing(row.get("ST"))]
        status = "pass" if host_rows and usable_links else "fail"
        return status_row(req_id, area, text, links, root, f"host_rows={len(host_rows)}; phage_host_links={len(link_rows)}; usable_links={len(usable_links)}", status, status == "fail", "Add host genomes or Kleborate/Kaptive outputs with K/O/ST metadata." if status == "fail" else "No action required.")

    if key == "defense":
        host_defense = results_dir / "defense_systems/host_defense_systems.tsv"
        phage_antidefense = results_dir / "defense_systems/phage_antidefense_candidates.tsv"
        compatibility = results_dir / "defense_systems/compatibility_features.tsv"
        _, host_defense_rows = read_tsv(host_defense)
        _, phage_antidefense_rows = read_tsv(phage_antidefense)
        compatibility_rows = count_rows(compatibility)
        host_rows = len(host_defense_rows)
        phage_rows = len(phage_antidefense_rows)
        inferred_phage_rows = [row for row in phage_antidefense_rows if row.get("evidence_type") == "annotation_keyword_inference"]
        explicit_phage_rows = [
            row
            for row in phage_antidefense_rows
            if not is_missing(row.get("evidence_type")) and row.get("evidence_type") != "annotation_keyword_inference"
        ]
        if compatibility_rows > 0 and host_rows > 0 and explicit_phage_rows:
            status = "pass"
            blocking = False
            action = "No action required."
        elif compatibility_rows > 0 and (host_rows > 0 or phage_rows > 0):
            status = "warn"
            blocking = True
            action = "Provide reviewed host defense and explicit phage anti-defense evidence, then rerun Stage 6."
        else:
            status = "fail"
            blocking = True
            action = "Provide PADLOC/DefenseFinder or reviewed phage anti-defense evidence and rerun Stage 6."
        summary = (
            f"host_defense_rows={host_rows}; phage_antidefense_rows={phage_rows}; "
            f"explicit_phage_antidefense_rows={len(explicit_phage_rows)}; inferred_phage_antidefense_rows={len(inferred_phage_rows)}; "
            f"compatibility_rows={compatibility_rows}"
        )
        return status_row(req_id, area, text, compatibility, root, summary, status, blocking, action)

    if key == "sample_support":
        path = results_dir / "qc/sample_support_by_hypothesis.tsv"
        summary_path = results_dir / "qc/sample_support_summary.tsv"
        _, rows = read_tsv(path)
        _, summary_rows = read_tsv(summary_path)
        ready_rows = [row for row in rows if row.get("support_status") == "ready_minimum_sample_support"]
        blocked_rows = [row for row in rows if row.get("support_status") == "blocked_minimum_sample_support"]
        missing = [row.get("hypothesis", "") for row in blocked_rows]
        failed_metrics = [row.get("metric", "") for row in summary_rows if row.get("status") == "fail"]
        status = "pass" if len(ready_rows) >= 6 and not blocked_rows else ("fail" if blocked_rows or not rows else "warn")
        blocking = status != "pass"
        action = "Populate/enable source exports until sample-support thresholds pass for H1-H6." if blocking else "No action required."
        summary = (
            f"ready_hypotheses={len(ready_rows)}; blocked_hypotheses={len(blocked_rows)}; "
            f"blocked={';'.join(missing) if missing else 'NA'}; failed_metrics={';'.join(failed_metrics) if failed_metrics else 'NA'}"
        )
        return status_row(req_id, area, text, path, root, summary, status, blocking, action)

    if key == "hypotheses":
        path = results_dir / "validation/hypothesis_coverage.tsv"
        _, rows = read_tsv(path)
        pass_rows = [row for row in rows if row.get("status") == "pass"]
        warn_rows = [row for row in rows if row.get("status") == "warn"]
        fail_rows = [row for row in rows if row.get("status") == "fail"]
        warn_hypotheses = {row.get("hypothesis", "") for row in warn_rows}
        h4_endpoint_limited = any(
            row.get("hypothesis") == "H4"
            and row.get("analysis_available") == "false"
            and row.get("data_adequate") == "false"
            and "blocked_no_productive_infection_labels" in row.get("notes", "")
            for row in warn_rows
        )
        only_nonblocking_h4 = warn_hypotheses <= {"H4"} and h4_endpoint_limited
        if not rows or fail_rows:
            status = "fail"
            blocking = True
            action = "Add data support until H1-H6 tests have ok or analysis-ready rows, or explicitly scope unsupported endpoints as future work."
        elif len(pass_rows) >= 5 and only_nonblocking_h4:
            status = "warn"
            blocking = False
            action = "No action required for the current dry-lab benchmark; H4 remains future work until productive-infection, plaque, or EOP outcomes are curated."
        elif len(pass_rows) >= 6 and not warn_rows:
            status = "pass"
            blocking = False
            action = "No action required."
        else:
            status = "warn"
            blocking = True
            action = "Add data support until H1-H6 tests have ok or analysis-ready rows, or explicitly scope unsupported endpoints as future work."
        summary = (
            f"pass={len(pass_rows)}; warn={len(warn_rows)}; fail={len(fail_rows)}; "
            f"nonblocking_endpoint_limited={';'.join(sorted(warn_hypotheses)) if only_nonblocking_h4 else 'NA'}"
        )
        return status_row(req_id, area, text, path, root, summary, status, blocking, action)

    if key == "figures":
        path = results_dir / "figures/figure_manifest.tsv"
        _, rows = read_tsv(path)
        complete = [row for row in rows if row.get("status") not in {"", "missing", "empty_schema_valid"}]
        empty = [row for row in rows if row.get("status") == "empty_schema_valid"]
        status = "pass" if len(complete) >= 6 and not empty else ("fail" if not rows else "warn")
        return status_row(req_id, area, text, path, root, f"figures={len(rows)}; nonempty_or_ready={len(complete)}; empty={len(empty)}", status, status == "fail", "Populate upstream analyses and regenerate figure sources." if status != "pass" else "No action required.")

    if key == "docs":
        path = results_dir / "validation/workflow_validation_report.tsv"
        _, rows = read_tsv(path)
        doc_pass = any(row.get("item") == "documentation" and row.get("status") == "pass" for row in rows)
        limitations_pass = any(row.get("item") == "limitations" and row.get("status") == "pass" for row in rows)
        claims_pass = any(row.get("item") == "claim_ledger" and row.get("status") == "pass" for row in rows)
        status = "pass" if doc_pass and limitations_pass and claims_pass else "fail"
        return status_row(req_id, area, text, path, root, f"documentation={doc_pass}; limitations={limitations_pass}; claim_ledger={claims_pass}", status, status == "fail", "Update required docs, limitations, and claim ledger." if status == "fail" else "No action required.")

    return status_row(req_id, area, text, Path(""), root, "unknown requirement key", "fail", True, "Fix readiness audit implementation.")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    results_dir = resolve(root, args.results_dir)
    samples = resolve(root, args.samples)
    readiness_rows = [evaluate_requirement(requirement, root, results_dir, samples) for requirement in REQUIREMENTS]
    fail_count = sum(1 for row in readiness_rows if row["status"] == "fail")
    warn_count = sum(1 for row in readiness_rows if row["status"] == "warn")
    pass_count = sum(1 for row in readiness_rows if row["status"] == "pass")
    blocking_count = sum(1 for row in readiness_rows if row["blocking_for_manuscript"] == "true")
    report = [
        {"severity": "info", "item": "study_readiness", "message": f"pass={pass_count}; warn={warn_count}; fail={fail_count}; blocking={blocking_count}"}
    ]
    if fail_count:
        report.append({"severity": "warning", "item": "study_readiness", "message": "Study is not manuscript-ready; see failing requirements."})
    elif blocking_count:
        report.append({"severity": "warning", "item": "study_readiness", "message": "Study is not manuscript-ready; see blocking warning requirements."})
    elif warn_count:
        report.append({"severity": "warning", "item": "study_readiness", "message": "Study has non-blocking readiness warnings."})
    else:
        report.append({"severity": "info", "item": "study_readiness", "message": "All audited readiness requirements passed."})
    write_tsv(Path(args.readiness_output), READINESS_COLUMNS, readiness_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Study readiness audit complete: {pass_count} pass, {warn_count} warn, {fail_count} fail.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
