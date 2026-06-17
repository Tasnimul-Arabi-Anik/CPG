#!/usr/bin/env python3
"""Run the implemented workflow stages from a YAML path configuration."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = [
    "stage",
    "status",
    "return_code",
    "command",
    "log_path",
    "expected_outputs",
    "missing_outputs",
    "message",
]

STAGE_ORDER = [
    "stage_0_tool_audit",
    "stage_0_source_queries",
    "stage_0_source_export_templates",
    "stage_0_source_export_dictionary",
    "stage_0_source_query_commands",
    "stage_0_source_export_validation",
    "stage_0_source_imports",
    "stage_0_source_plan",
    "stage_0_source_audit",
    "stage_0_source_curation_tasks",
    "stage_0_source_export_starter_kit",
    "stage_0_hypothesis_source_unlocks",
    "stage_0_minimum_source_curation",
    "stage_0_priority_source_preflight",
    "stage_0_priority_source_collection_packet",
    "stage_0_source_enablement",
    "stage_0_source_enablement_apply",
    "stage_0_source_curation_packet",
    "stage_0_samples",
    "stage_0_source_overlap_audit",
    "stage_0_sample_support",
    "stage_0_sample_support_sources",
    "stage_0_sample_support_export_preflight",
    "stage_0_source_readiness_dashboard",
    "stage_0_source_curation_work_order",
    "stage_0_source_work_order_packets",
    "stage_0_source_curation_issue_bodies",
    "stage_0_source_work_order_acceptance",
    "stage_0_source_post_acceptance",
    "stage_0_sample_support_curation_packet",
    "stage_1_manifest",
    "stage_1_sequence_acquisition",
    "stage_1_sequence_fetch_manifest",
    "stage_1_sequence_fetch_review_packet",
    "stage_1_sequence_qc",
    "stage_1_external_evidence_plan",
    "stage_1_external_evidence_templates",
    "stage_1_external_evidence_run_packets",
    "stage_1_external_evidence_acceptance",
    "stage_1_external_evidence_unlocks",
    "stage_1_production_evidence_handoff",
    "stage_1_pipeline_efficiency_audit",
    "stage_2_dereplication",
    "stage_3_annotations",
    "stage_3_external_evidence_proteins",
    "stage_3_phage_antidefense_handoff",
    "stage_4_rbp_depolymerase",
    "stage_5_host_features",
    "stage_5_host_defense_handoff",
    "stage_6_defense_counterdefense",
    "stage_7_models",
    "stage_8_figures",
    "stage_9_source_export_validation_self_test",
    "stage_9_external_evidence_acceptance_self_test",
    "stage_9_validation",
    "stage_10_study_readiness",
    "stage_10_readiness_actions",
    "stage_11_hypothesis_traceability",
    "stage_11_claim_support_audit",
    "stage_11_goal_completion_audit",
]


@dataclass
class Stage:
    name: str
    command: list[str]
    log_path: Path
    expected_outputs: list[Path]


class WorkflowError(Exception):
    """Raised when workflow configuration or execution fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Klebsiella phage CPG workflow stages from config/workflow.yaml.")
    parser.add_argument("--config", default="config/workflow.yaml", help="Workflow YAML path configuration.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=STAGE_ORDER,
        default=[],
        help="Optional subset of stages to run in dependency order.",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise WorkflowError("PyYAML is required to read workflow configuration.") from exc
    if not path.exists():
        raise WorkflowError(f"Workflow config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise WorkflowError(f"Workflow config must contain a YAML mapping: {path}")
    return data


def nested_get(data: dict, path: tuple[str, ...], default: str = "") -> str:
    current: object = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return "" if current is None else str(current)


def resolve(root: Path, value: str) -> Path:
    if not value:
        return Path("")
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel_or_abs(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def configured_path(config: dict, root: Path, keys: tuple[str, ...], default: str) -> Path:
    return resolve(root, nested_get(config, keys, default))


def optional_input(config: dict, root: Path, keys: tuple[str, ...]) -> Path | None:
    value = nested_get(config, keys, "")
    if not value.strip():
        return None
    path = resolve(root, value)
    if not path.exists():
        raise WorkflowError(f"Configured optional input does not exist: {rel_or_abs(root, path)}")
    return path


def add_optional(command: list[str], option: str, path: Path | None) -> None:
    if path is not None:
        command.extend([option, path.as_posix()])


def command_text(command: Iterable[str]) -> str:
    return " ".join(command)


def ensure_parent_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        if str(path):
            path.parent.mkdir(parents=True, exist_ok=True)


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def build_stages(config: dict, root: Path) -> tuple[list[Stage], Path]:
    python = nested_get(config, ("execution", "python"), sys.executable) or sys.executable
    logs_dir = configured_path(config, root, ("logs", "directory"), "logs")
    run_report = configured_path(
        config,
        root,
        ("outputs", "validation", "run_report"),
        "results/validation/workflow_run_report.tsv",
    )

    script = lambda name: (root / "scripts" / name).as_posix()
    inp = lambda key, default: configured_path(config, root, ("inputs", key), default)
    out = lambda section, key, default: configured_path(config, root, ("outputs", section, key), default)

    configured_samples = inp("samples", "config/samples.tsv")
    thresholds = inp("thresholds", "config/thresholds.yaml")
    tools_config = inp("tools", "config/tools.yaml")
    tool_audit_enabled = nested_get(config, ("tool_audit", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    tool_availability = configured_path(config, root, ("tool_audit", "availability"), "results/qc/tool_availability.tsv")
    tool_audit_report = configured_path(config, root, ("tool_audit", "report"), "results/qc/tool_audit_report.tsv")
    source_queries_enabled = nested_get(config, ("source_queries", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    source_queries_config = configured_path(config, root, ("source_queries", "config"), "config/source_queries.yaml")
    source_queries_catalog = configured_path(config, root, ("source_queries", "catalog"), "config/source_catalog.yaml")
    source_queries_imports_config = configured_path(config, root, ("source_queries", "imports_config"), "config/source_imports.yaml")
    source_query_plan = configured_path(config, root, ("source_queries", "plan"), "results/qc/source_query_plan.tsv")
    source_query_report = configured_path(config, root, ("source_queries", "report"), "results/qc/source_query_report.tsv")
    source_query_commands_enabled = nested_get(config, ("source_query_commands", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_query_commands = configured_path(config, root, ("source_query_commands", "commands"), "results/qc/source_query_commands.tsv")
    source_query_commands_shell = configured_path(config, root, ("source_query_commands", "shell"), "results/qc/source_query_commands.sh")
    source_query_commands_report = configured_path(config, root, ("source_query_commands", "report"), "results/qc/source_query_commands_report.tsv")
    source_export_templates_enabled = nested_get(config, ("source_export_templates", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    source_export_templates_dir = configured_path(config, root, ("source_export_templates", "templates_dir"), "results/qc/source_export_templates")
    source_export_template_manifest = configured_path(config, root, ("source_export_templates", "manifest"), "results/qc/source_export_template_manifest.tsv")
    source_export_template_report = configured_path(config, root, ("source_export_templates", "report"), "results/qc/source_export_template_report.tsv")
    source_export_dictionary_enabled = nested_get(config, ("source_export_dictionary", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_export_dictionary = configured_path(config, root, ("source_export_dictionary", "dictionary"), "results/qc/source_export_column_dictionary.tsv")
    source_export_dictionary_report = configured_path(config, root, ("source_export_dictionary", "report"), "results/qc/source_export_column_dictionary_report.tsv")
    source_export_validation_enabled = nested_get(config, ("source_export_validation", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    source_export_validation = configured_path(config, root, ("source_export_validation", "validation"), "results/qc/source_export_validation.tsv")
    source_export_validation_report = configured_path(config, root, ("source_export_validation", "report"), "results/qc/source_export_validation_report.tsv")
    source_imports_enabled = nested_get(config, ("source_imports", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    source_imports_config = configured_path(config, root, ("source_imports", "config"), "config/source_imports.yaml")
    source_imports_report = configured_path(config, root, ("source_imports", "report"), "results/qc/source_import_report.tsv")
    source_plan_enabled = nested_get(config, ("source_plan", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_plan_catalog = configured_path(config, root, ("source_plan", "catalog"), "config/source_catalog.yaml")
    source_plan_imports_config = configured_path(config, root, ("source_plan", "imports_config"), source_imports_config.as_posix())
    source_acquisition_plan = configured_path(config, root, ("source_plan", "plan"), "results/qc/source_acquisition_plan.tsv")
    source_acquisition_report = configured_path(config, root, ("source_plan", "report"), "results/qc/source_acquisition_report.tsv")
    sample_builder_enabled = nested_get(config, ("sample_builder", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    sample_builder_catalog = configured_path(config, root, ("sample_builder", "catalog"), "config/source_catalog.yaml")
    sample_builder_output = configured_path(config, root, ("sample_builder", "output_samples"), configured_samples.as_posix())
    sample_builder_report = configured_path(config, root, ("sample_builder", "report"), "results/qc/sample_source_report.tsv")
    sequence_acquisition_enabled = nested_get(config, ("sequence_acquisition", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    sequence_raw_directory = configured_path(config, root, ("sequence_acquisition", "raw_directory"), "data/raw/genomes")
    sequence_fetch_manifest_enabled = nested_get(config, ("sequence_fetch_manifest", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    sequence_fetch_manifest = configured_path(config, root, ("sequence_fetch_manifest", "manifest"), "results/qc/sequence_fetch_manifest.tsv")
    sequence_fetch_commands = configured_path(config, root, ("sequence_fetch_manifest", "commands"), "results/qc/sequence_fetch_commands.sh")
    sequence_fetch_report = configured_path(config, root, ("sequence_fetch_manifest", "report"), "results/qc/sequence_fetch_report.tsv")
    sequence_fetch_review_packet_enabled = nested_get(config, ("sequence_fetch_review_packet", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    sequence_fetch_review_packet = configured_path(config, root, ("sequence_fetch_review_packet", "packet"), "results/qc/sequence_fetch_review_packet.md")
    sequence_fetch_review_report = configured_path(config, root, ("sequence_fetch_review_packet", "report"), "results/qc/sequence_fetch_review_packet_report.tsv")
    external_evidence_enabled = nested_get(config, ("external_evidence", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    external_evidence_templates_enabled = nested_get(config, ("external_evidence_templates", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    external_evidence_templates_dir = configured_path(config, root, ("external_evidence_templates", "templates_dir"), "results/qc/external_evidence_templates")
    external_evidence_template_manifest = configured_path(config, root, ("external_evidence_templates", "manifest"), "results/qc/external_evidence_template_manifest.tsv")
    external_evidence_template_report = configured_path(config, root, ("external_evidence_templates", "report"), "results/qc/external_evidence_template_report.tsv")
    external_evidence_run_packets_enabled = nested_get(config, ("external_evidence_run_packets", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    external_evidence_run_packets_dir = configured_path(config, root, ("external_evidence_run_packets", "directory"), "results/qc/external_evidence_run_packets")
    external_evidence_run_packets_manifest = configured_path(config, root, ("external_evidence_run_packets", "manifest"), "results/qc/external_evidence_run_packet_manifest.tsv")
    external_evidence_run_packets_report = configured_path(config, root, ("external_evidence_run_packets", "report"), "results/qc/external_evidence_run_packet_report.tsv")
    external_evidence_proteins_enabled = nested_get(config, ("external_evidence_proteins", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    external_evidence_all_proteins = configured_path(config, root, ("external_evidence_proteins", "all_proteins"), "results/qc/external_evidence_proteins/phage_proteins.faa")
    external_evidence_candidate_proteins = configured_path(config, root, ("external_evidence_proteins", "candidate_proteins"), "results/qc/external_evidence_proteins/rbp_depolymerase_candidate_proteins.faa")
    external_evidence_protein_manifest = configured_path(config, root, ("external_evidence_proteins", "manifest"), "results/qc/external_evidence_proteins/protein_export_manifest.tsv")
    external_evidence_protein_report = configured_path(config, root, ("external_evidence_proteins", "report"), "results/qc/external_evidence_proteins/protein_export_report.tsv")
    phage_antidefense_handoff_enabled = nested_get(config, ("phage_antidefense_handoff", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    phage_antidefense_handoff_manifest = configured_path(config, root, ("phage_antidefense_handoff", "manifest"), "results/qc/phage_antidefense_screening_handoff.tsv")
    phage_antidefense_handoff_commands = configured_path(config, root, ("phage_antidefense_handoff", "commands"), "results/qc/phage_antidefense_screening_commands.sh")
    phage_antidefense_handoff_report = configured_path(config, root, ("phage_antidefense_handoff", "report"), "results/qc/phage_antidefense_screening_handoff_report.tsv")
    external_evidence_acceptance_enabled = nested_get(config, ("external_evidence_acceptance", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    external_evidence_acceptance = configured_path(config, root, ("external_evidence_acceptance", "acceptance"), "results/qc/external_evidence_acceptance.tsv")
    external_evidence_acceptance_report = configured_path(config, root, ("external_evidence_acceptance", "report"), "results/qc/external_evidence_acceptance_report.tsv")
    external_evidence_unlocks_enabled = nested_get(config, ("external_evidence_unlocks", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    external_evidence_unlock_plan = configured_path(config, root, ("external_evidence_unlocks", "plan"), "results/qc/external_evidence_unlock_plan.tsv")
    external_evidence_unlock_matrix = configured_path(config, root, ("external_evidence_unlocks", "matrix"), "results/qc/external_evidence_unlock_matrix.tsv")
    external_evidence_unlock_report = configured_path(config, root, ("external_evidence_unlocks", "report"), "results/qc/external_evidence_unlock_report.tsv")
    production_evidence_handoff_enabled = nested_get(config, ("production_evidence_handoff", "enabled"), "false").strip().lower() in {"true", "1", "yes", "on"}
    production_evidence_handoff = configured_path(config, root, ("production_evidence_handoff", "handoff"), "results/qc/production_evidence_handoff.md")
    production_evidence_handoff_report = configured_path(config, root, ("production_evidence_handoff", "report"), "results/qc/production_evidence_handoff_report.tsv")
    pipeline_efficiency_enabled = nested_get(config, ("pipeline_efficiency", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    pipeline_efficiency_workflow_config = configured_path(config, root, ("outputs", "validation", "workflow_config"), "config/workflow.yaml")
    pipeline_efficiency_audit = configured_path(config, root, ("pipeline_efficiency", "audit"), "results/validation/pipeline_efficiency_audit.tsv")
    pipeline_efficiency_report = configured_path(config, root, ("pipeline_efficiency", "report"), "results/validation/pipeline_efficiency_report.tsv")
    source_audit_enabled = nested_get(config, ("source_audit", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_audit_catalog = configured_path(config, root, ("source_audit", "catalog"), sample_builder_catalog.as_posix())
    source_audit_readiness = configured_path(config, root, ("source_audit", "readiness"), "results/qc/source_catalog_readiness.tsv")
    source_audit_report = configured_path(config, root, ("source_audit", "report"), "results/qc/source_catalog_audit_report.tsv")
    source_curation_tasks_enabled = nested_get(config, ("source_curation_tasks", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_curation_tasks = configured_path(config, root, ("source_curation_tasks", "tasks"), "results/qc/source_curation_tasks.tsv")
    source_curation_tasks_report = configured_path(config, root, ("source_curation_tasks", "report"), "results/qc/source_curation_tasks_report.tsv")
    source_export_starter_kit_enabled = nested_get(config, ("source_export_starter_kit", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_export_starter_kit_dir = configured_path(config, root, ("source_export_starter_kit", "directory"), "results/qc/source_export_starter_kit")
    source_export_starter_kit_manifest = configured_path(config, root, ("source_export_starter_kit", "manifest"), "results/qc/source_export_starter_kit_manifest.tsv")
    source_export_starter_kit_report = configured_path(config, root, ("source_export_starter_kit", "report"), "results/qc/source_export_starter_kit_report.tsv")
    source_export_starter_kit_index = source_export_starter_kit_dir / "README.md"
    hypothesis_source_unlocks_enabled = nested_get(config, ("hypothesis_source_unlocks", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    hypothesis_source_unlock_plan = configured_path(config, root, ("hypothesis_source_unlocks", "plan"), "results/qc/hypothesis_source_unlock_plan.tsv")
    hypothesis_source_unlock_matrix = configured_path(config, root, ("hypothesis_source_unlocks", "matrix"), "results/qc/hypothesis_source_unlock_matrix.tsv")
    hypothesis_source_unlock_report = configured_path(config, root, ("hypothesis_source_unlocks", "report"), "results/qc/hypothesis_source_unlock_report.tsv")
    minimum_source_curation_enabled = nested_get(config, ("minimum_source_curation", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    minimum_source_curation_source_plan = configured_path(config, root, ("minimum_source_curation", "source_plan"), "results/qc/minimum_source_curation_plan.tsv")
    minimum_source_curation_hypothesis_plan = configured_path(config, root, ("minimum_source_curation", "hypothesis_plan"), "results/qc/minimum_hypothesis_source_plan.tsv")
    minimum_source_curation_report = configured_path(config, root, ("minimum_source_curation", "report"), "results/qc/minimum_source_curation_report.tsv")
    priority_source_preflight_enabled = nested_get(config, ("priority_source_preflight", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    priority_source_preflight_max_rank = nested_get(config, ("priority_source_preflight", "max_rank"), "2") or "2"
    priority_source_preflight_summary = configured_path(config, root, ("priority_source_preflight", "summary"), "results/qc/priority_source_export_preflight.tsv")
    priority_source_preflight_issues = configured_path(config, root, ("priority_source_preflight", "issues"), "results/qc/priority_source_export_preflight_issues.tsv")
    priority_source_preflight_report = configured_path(config, root, ("priority_source_preflight", "report"), "results/qc/priority_source_export_preflight_report.tsv")
    priority_source_collection_packet_enabled = nested_get(config, ("priority_source_collection_packet", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    priority_source_collection_packet_dir = configured_path(config, root, ("priority_source_collection_packet", "directory"), "results/qc/priority_source_collection_packet")
    priority_source_collection_packet_manifest = configured_path(config, root, ("priority_source_collection_packet", "manifest"), "results/qc/priority_source_collection_packet_manifest.tsv")
    priority_source_collection_packet_report = configured_path(config, root, ("priority_source_collection_packet", "report"), "results/qc/priority_source_collection_packet_report.tsv")
    priority_source_collection_packet_index = priority_source_collection_packet_dir / "README.md"
    source_enablement_enabled = nested_get(config, ("source_enablement", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_enablement_plan = configured_path(config, root, ("source_enablement", "plan"), "results/qc/source_enablement_plan.tsv")
    source_enablement_report = configured_path(config, root, ("source_enablement", "report"), "results/qc/source_enablement_report.tsv")
    source_enablement_apply_enabled = nested_get(config, ("source_enablement_apply", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_enablement_apply_report = configured_path(config, root, ("source_enablement_apply", "report"), "results/qc/source_enablement_apply_report.tsv")
    source_enablement_apply_imports = nested_get(config, ("source_enablement_apply", "enable_imports"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_enablement_apply_catalog = nested_get(config, ("source_enablement_apply", "enable_catalog"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_curation_packet_enabled = nested_get(config, ("source_curation_packet", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_curation_packet_dir = configured_path(config, root, ("source_curation_packet", "directory"), "results/qc/source_curation_packet")
    source_curation_packet_manifest = configured_path(config, root, ("source_curation_packet", "manifest"), "results/qc/source_curation_packet_manifest.tsv")
    source_curation_packet_report = configured_path(config, root, ("source_curation_packet", "report"), "results/qc/source_curation_packet_report.tsv")
    source_curation_packet_index = source_curation_packet_dir / "README.md"
    samples = sample_builder_output if sample_builder_enabled else configured_samples
    source_overlap_enabled = nested_get(config, ("source_overlap", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_overlap_groups = configured_path(config, root, ("source_overlap", "overlaps"), "results/qc/source_overlap_groups.tsv")
    source_overlap_summary = configured_path(config, root, ("source_overlap", "summary"), "results/qc/source_overlap_summary.tsv")
    source_overlap_report = configured_path(config, root, ("source_overlap", "report"), "results/qc/source_overlap_report.tsv")
    sample_support_enabled = nested_get(config, ("sample_support", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    sample_support_hypotheses = configured_path(config, root, ("sample_support", "hypotheses"), "results/qc/sample_support_by_hypothesis.tsv")
    sample_support_summary = configured_path(config, root, ("sample_support", "summary"), "results/qc/sample_support_summary.tsv")
    sample_support_report = configured_path(config, root, ("sample_support", "report"), "results/qc/sample_support_report.tsv")
    sample_support_sources_enabled = nested_get(config, ("sample_support_sources", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    sample_support_source_bridge = configured_path(config, root, ("sample_support_sources", "bridge"), "results/qc/sample_support_source_bridge.tsv")
    sample_support_source_bridge_report = configured_path(config, root, ("sample_support_sources", "report"), "results/qc/sample_support_source_bridge_report.tsv")
    sample_support_export_preflight_enabled = nested_get(config, ("sample_support_export_preflight", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    sample_support_export_preflight = configured_path(config, root, ("sample_support_export_preflight", "preflight"), "results/qc/sample_support_export_preflight.tsv")
    sample_support_export_preflight_report = configured_path(config, root, ("sample_support_export_preflight", "report"), "results/qc/sample_support_export_preflight_report.tsv")
    source_readiness_dashboard_enabled = nested_get(config, ("source_readiness_dashboard", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_readiness_dashboard = configured_path(config, root, ("source_readiness_dashboard", "dashboard"), "results/qc/source_readiness_dashboard.tsv")
    source_readiness_dashboard_report = configured_path(config, root, ("source_readiness_dashboard", "report"), "results/qc/source_readiness_dashboard_report.tsv")
    source_curation_work_order_enabled = nested_get(config, ("source_curation_work_order", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_curation_work_order = configured_path(config, root, ("source_curation_work_order", "work_order"), "results/qc/source_curation_work_order.tsv")
    source_curation_work_order_report = configured_path(config, root, ("source_curation_work_order", "report"), "results/qc/source_curation_work_order_report.tsv")
    source_work_order_packets_enabled = nested_get(config, ("source_work_order_packets", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_work_order_packets_dir = configured_path(config, root, ("source_work_order_packets", "directory"), "results/qc/source_work_order_packets")
    source_work_order_packets_manifest = configured_path(config, root, ("source_work_order_packets", "manifest"), "results/qc/source_work_order_packet_manifest.tsv")
    source_work_order_packets_report = configured_path(config, root, ("source_work_order_packets", "report"), "results/qc/source_work_order_packet_report.tsv")
    source_work_order_packets_index = source_work_order_packets_dir / "README.md"
    source_curation_issue_bodies_enabled = nested_get(config, ("source_curation_issue_bodies", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_curation_issue_dir = configured_path(config, root, ("source_curation_issue_bodies", "directory"), "results/qc/github_issue_bodies")
    source_curation_issue_manifest = configured_path(config, root, ("source_curation_issue_bodies", "manifest"), "results/qc/source_curation_issue_manifest.tsv")
    source_curation_issue_commands = configured_path(config, root, ("source_curation_issue_bodies", "commands"), "results/qc/source_curation_issue_commands.tsv")
    source_curation_issue_shell = configured_path(config, root, ("source_curation_issue_bodies", "shell"), "results/qc/source_curation_issue_commands.sh")
    source_curation_issue_report = configured_path(config, root, ("source_curation_issue_bodies", "report"), "results/qc/source_curation_issue_report.tsv")
    source_work_order_acceptance_enabled = nested_get(config, ("source_work_order_acceptance", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_work_order_acceptance = configured_path(config, root, ("source_work_order_acceptance", "acceptance"), "results/qc/source_work_order_acceptance.tsv")
    source_work_order_acceptance_report = configured_path(config, root, ("source_work_order_acceptance", "report"), "results/qc/source_work_order_acceptance_report.tsv")
    source_post_acceptance_enabled = nested_get(config, ("source_post_acceptance", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    source_post_acceptance_plan = configured_path(config, root, ("source_post_acceptance", "plan"), "results/qc/source_post_acceptance_plan.tsv")
    source_post_acceptance_report = configured_path(config, root, ("source_post_acceptance", "report"), "results/qc/source_post_acceptance_report.tsv")
    sample_support_curation_packet_enabled = nested_get(config, ("sample_support_curation_packet", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    sample_support_curation_packet_dir = configured_path(config, root, ("sample_support_curation_packet", "directory"), "results/qc/sample_support_curation_packet")
    sample_support_curation_packet_manifest = configured_path(config, root, ("sample_support_curation_packet", "manifest"), "results/qc/sample_support_curation_packet_manifest.tsv")
    sample_support_curation_packet_report = configured_path(config, root, ("sample_support_curation_packet", "report"), "results/qc/sample_support_curation_packet_report.tsv")
    sample_support_curation_packet_index = sample_support_curation_packet_dir / "README.md"

    manifest = out("qc", "manifest", "results/qc/phage_genome_manifest.tsv")
    manifest_report = out("qc", "manifest_report", "results/qc/manifest_validation_report.tsv")
    excluded = out("qc", "excluded", "results/qc/excluded_genomes.tsv")
    sequence_acquisition_plan = out("qc", "sequence_acquisition_plan", "results/qc/sequence_acquisition_plan.tsv")
    sequence_acquisition_report = out("qc", "sequence_acquisition_report", "results/qc/sequence_acquisition_report.tsv")
    sequence_qc = out("qc", "sequence_qc", "results/qc/genome_sequence_qc.tsv")
    sequence_qc_report = out("qc", "sequence_qc_report", "results/qc/genome_sequence_qc_report.tsv")
    external_evidence_plan = out("qc", "external_evidence_plan", "results/qc/external_evidence_plan.tsv")
    external_evidence_report = out("qc", "external_evidence_report", "results/qc/external_evidence_report.tsv")

    ani = out("clusters", "ani", "results/clusters/phage_ani.tsv")
    clusters = out("clusters", "clusters", "results/clusters/phage_clusters.tsv")
    representatives = out("clusters", "representatives", "results/clusters/representatives.tsv")
    derep_report = out("clusters", "report", "results/clusters/dereplication_report.tsv")

    annotations = out("annotations", "annotations", "results/annotations/phage_annotations.tsv")
    gene_clusters = out("annotations", "gene_clusters", "results/annotations/gene_clusters.tsv")
    pangenome = out("annotations", "pangenome", "results/annotations/pangenome_matrix.tsv")
    annotation_report = out("annotations", "report", "results/annotations/annotation_report.tsv")

    rbp_candidates = out("rbp_depolymerase", "candidates", "results/rbp_depolymerase/candidates.tsv")
    domain_architectures = out("rbp_depolymerase", "domain_architectures", "results/rbp_depolymerase/domain_architectures.tsv")
    module_clusters = out("rbp_depolymerase", "module_clusters", "results/rbp_depolymerase/module_clusters.tsv")
    novel_candidates = out("rbp_depolymerase", "novel_candidates", "results/rbp_depolymerase/novel_candidates.tsv")
    rbp_report = out("rbp_depolymerase", "report", "results/rbp_depolymerase/rbp_depolymerase_report.tsv")

    host_metadata = out("host_features", "host_metadata", "results/host_features/host_metadata.tsv")
    kaptive = out("host_features", "kaptive", "results/host_features/kaptive_results.tsv")
    kleborate = out("host_features", "kleborate", "results/host_features/kleborate_results.tsv")
    phage_host_links = out("host_features", "phage_host_links", "results/host_features/phage_host_links.tsv")
    host_report = out("host_features", "report", "results/host_features/host_feature_report.tsv")
    host_defense_handoff_enabled = nested_get(config, ("host_defense_handoff", "enabled"), "true").strip().lower() in {"true", "1", "yes", "on"}
    host_defense_handoff_manifest = configured_path(config, root, ("host_defense_handoff", "manifest"), "results/qc/host_defense_run_handoff.tsv")
    host_defense_handoff_commands = configured_path(config, root, ("host_defense_handoff", "commands"), "results/qc/host_defense_run_commands.sh")
    host_defense_handoff_report = configured_path(config, root, ("host_defense_handoff", "report"), "results/qc/host_defense_run_handoff_report.tsv")

    host_defense = out("defense_systems", "host_defense", "results/defense_systems/host_defense_systems.tsv")
    phage_antidefense = out("defense_systems", "phage_antidefense", "results/defense_systems/phage_antidefense_candidates.tsv")
    compatibility = out("defense_systems", "compatibility", "results/defense_systems/compatibility_features.tsv")
    defense_report = out("defense_systems", "report", "results/defense_systems/defense_counterdefense_report.tsv")

    model_comparison = out("models", "model_comparison", "results/models/model_comparison.tsv")
    feature_importance = out("models", "feature_importance", "results/models/feature_importance.tsv")
    prediction_errors = out("models", "prediction_errors", "results/models/prediction_errors.tsv")
    hypothesis_summary = out("models", "hypothesis_summary", "results/models/hypothesis_summary.tsv")
    model_report = out("models", "report", "results/models/model_report.tsv")

    figure_dir = out("figures", "directory", "results/figures")
    figure_manifest = out("figures", "manifest", "results/figures/figure_manifest.tsv")
    figure_report = out("figures", "report", "results/figures/figure_generation_report.tsv")
    figure_outputs = [
        figure_dir / "figure_1_dataset_atlas_source.tsv",
        figure_dir / "figure_1_dataset_atlas.svg",
        figure_dir / "figure_2_phage_pangenome_source.tsv",
        figure_dir / "figure_2_phage_pangenome.svg",
        figure_dir / "figure_3_rbp_module_network_source.tsv",
        figure_dir / "figure_3_rbp_module_network.svg",
        figure_dir / "figure_4_k_o_association_source.tsv",
        figure_dir / "figure_4_k_o_association.svg",
        figure_dir / "figure_5_defense_counterdefense_source.tsv",
        figure_dir / "figure_5_defense_counterdefense.svg",
        figure_dir / "figure_6_novelty_prioritization_source.tsv",
        figure_dir / "figure_6_novelty_prioritization.svg",
        figure_manifest,
        figure_report,
    ]

    validation_results_dir = nested_get(config, ("outputs", "validation", "results_dir"), "results") or "results"
    validation_samples = nested_get(config, ("outputs", "validation", "samples"), nested_get(config, ("inputs", "samples"), "config/samples.tsv"))
    validation_workflow_config = nested_get(config, ("outputs", "validation", "workflow_config"), "config/workflow.yaml") or "config/workflow.yaml"
    validation_schema = out("validation", "schema", "results/validation/schema_validation.tsv")
    validation_hypotheses = out("validation", "hypotheses", "results/validation/hypothesis_coverage.tsv")
    validation_inventory = out("validation", "inventory", "results/validation/output_inventory.tsv")
    validation_report = out("validation", "report", "results/validation/workflow_validation_report.tsv")
    source_export_validation_self_test = out("validation", "source_export_validation_self_test", "results/validation/source_export_validation_self_test.tsv")
    source_export_validation_self_test_report = out("validation", "source_export_validation_self_test_report", "results/validation/source_export_validation_self_test_report.tsv")
    external_evidence_acceptance_self_test = out("validation", "external_evidence_acceptance_self_test", "results/validation/external_evidence_acceptance_self_test.tsv")
    external_evidence_acceptance_self_test_report = out("validation", "external_evidence_acceptance_self_test_report", "results/validation/external_evidence_acceptance_self_test_report.tsv")
    study_readiness = out("validation", "study_readiness", "results/validation/study_readiness.tsv")
    study_readiness_report = out("validation", "study_readiness_report", "results/validation/study_readiness_report.tsv")
    readiness_action_plan = out("validation", "readiness_action_plan", "results/validation/readiness_action_plan.tsv")
    readiness_action_report = out("validation", "readiness_action_report", "results/validation/readiness_action_report.tsv")
    hypothesis_traceability = out("validation", "hypothesis_traceability", "results/validation/hypothesis_traceability.tsv")
    hypothesis_traceability_report = out("validation", "hypothesis_traceability_report", "results/validation/hypothesis_traceability_report.tsv")
    claim_support_audit = out("validation", "claim_support_audit", "results/validation/claim_support_audit.tsv")
    claim_support_report = out("validation", "claim_support_report", "results/validation/claim_support_report.tsv")
    goal_completion_audit = out("validation", "goal_completion_audit", "results/validation/goal_completion_audit.tsv")
    goal_completion_report = out("validation", "goal_completion_report", "results/validation/goal_completion_report.tsv")

    stages = []
    if tool_audit_enabled:
        stages.append(
            Stage(
                "stage_0_tool_audit",
                [
                    python,
                    script("audit_tool_availability.py"),
                    "--tools-config",
                    tools_config.as_posix(),
                    "--availability-output",
                    tool_availability.as_posix(),
                    "--report-output",
                    tool_audit_report.as_posix(),
                ],
                logs_dir / "00_audit_tool_availability.log",
                [tool_availability, tool_audit_report],
            )
        )

    if source_queries_enabled:
        stages.append(
            Stage(
                "stage_0_source_queries",
                [
                    python,
                    script("plan_source_queries.py"),
                    "--queries-config",
                    source_queries_config.as_posix(),
                    "--catalog",
                    source_queries_catalog.as_posix(),
                    "--imports-config",
                    source_queries_imports_config.as_posix(),
                    "--plan-output",
                    source_query_plan.as_posix(),
                    "--report-output",
                    source_query_report.as_posix(),
                ],
                logs_dir / "00_plan_source_queries.log",
                [source_query_plan, source_query_report],
            )
        )

    if source_export_templates_enabled:
        stages.append(
            Stage(
                "stage_0_source_export_templates",
                [
                    python,
                    script("create_source_export_templates.py"),
                    "--query-plan",
                    source_query_plan.as_posix(),
                    "--templates-dir",
                    source_export_templates_dir.as_posix(),
                    "--manifest-output",
                    source_export_template_manifest.as_posix(),
                    "--report-output",
                    source_export_template_report.as_posix(),
                ],
                logs_dir / "00_create_source_export_templates.log",
                [source_export_template_manifest, source_export_template_report],
            )
        )

    if source_export_dictionary_enabled:
        stages.append(
            Stage(
                "stage_0_source_export_dictionary",
                [
                    python,
                    script("create_source_export_dictionary.py"),
                    "--template-manifest",
                    source_export_template_manifest.as_posix(),
                    "--dictionary-output",
                    source_export_dictionary.as_posix(),
                    "--report-output",
                    source_export_dictionary_report.as_posix(),
                ],
                logs_dir / "00_create_source_export_dictionary.log",
                [source_export_dictionary, source_export_dictionary_report],
            )
        )

    if source_query_commands_enabled:
        stages.append(
            Stage(
                "stage_0_source_query_commands",
                [
                    python,
                    script("create_source_query_commands.py"),
                    "--source-query-plan",
                    source_query_plan.as_posix(),
                    "--template-manifest",
                    source_export_template_manifest.as_posix(),
                    "--commands-output",
                    source_query_commands.as_posix(),
                    "--shell-output",
                    source_query_commands_shell.as_posix(),
                    "--report-output",
                    source_query_commands_report.as_posix(),
                ],
                logs_dir / "00_create_source_query_commands.log",
                [source_query_commands, source_query_commands_shell, source_query_commands_report],
            )
        )

    if source_export_validation_enabled:
        stages.append(
            Stage(
                "stage_0_source_export_validation",
                [
                    python,
                    script("validate_source_exports.py"),
                    "--query-plan",
                    source_query_plan.as_posix(),
                    "--template-manifest",
                    source_export_template_manifest.as_posix(),
                    "--validation-output",
                    source_export_validation.as_posix(),
                    "--report-output",
                    source_export_validation_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_validate_source_exports.log",
                [source_export_validation, source_export_validation_report],
            )
        )

    if source_imports_enabled:
        stages.append(
            Stage(
                "stage_0_source_imports",
                [
                    python,
                    script("import_source_manifests.py"),
                    "--config",
                    source_imports_config.as_posix(),
                    "--report-output",
                    source_imports_report.as_posix(),
                ],
                logs_dir / "00_import_source_manifests.log",
                [source_imports_report],
            )
        )

    if source_plan_enabled:
        stages.append(
            Stage(
                "stage_0_source_plan",
                [
                    python,
                    script("plan_source_acquisition.py"),
                    "--catalog",
                    source_plan_catalog.as_posix(),
                    "--imports-config",
                    source_plan_imports_config.as_posix(),
                    "--plan-output",
                    source_acquisition_plan.as_posix(),
                    "--report-output",
                    source_acquisition_report.as_posix(),
                ],
                logs_dir / "00_plan_source_acquisition.log",
                [source_acquisition_plan, source_acquisition_report],
            )
        )

    if source_audit_enabled:
        stages.append(
            Stage(
                "stage_0_source_audit",
                [
                    python,
                    script("audit_source_catalog.py"),
                    "--catalog",
                    source_audit_catalog.as_posix(),
                    "--readiness-output",
                    source_audit_readiness.as_posix(),
                    "--report-output",
                    source_audit_report.as_posix(),
                ],
                logs_dir / "00_audit_source_catalog.log",
                [source_audit_readiness, source_audit_report],
            )
        )

    if source_curation_tasks_enabled:
        stages.append(
            Stage(
                "stage_0_source_curation_tasks",
                [
                    python,
                    script("summarize_source_curation_tasks.py"),
                    "--source-query-plan",
                    source_query_plan.as_posix(),
                    "--template-manifest",
                    source_export_template_manifest.as_posix(),
                    "--export-validation",
                    source_export_validation.as_posix(),
                    "--source-acquisition-plan",
                    source_acquisition_plan.as_posix(),
                    "--source-readiness",
                    source_audit_readiness.as_posix(),
                    "--tasks-output",
                    source_curation_tasks.as_posix(),
                    "--report-output",
                    source_curation_tasks_report.as_posix(),
                ],
                logs_dir / "00_summarize_source_curation_tasks.log",
                [source_curation_tasks, source_curation_tasks_report],
            )
        )

    if source_export_starter_kit_enabled:
        stages.append(
            Stage(
                "stage_0_source_export_starter_kit",
                [
                    python,
                    script("create_source_export_starter_kit.py"),
                    "--source-curation-tasks",
                    source_curation_tasks.as_posix(),
                    "--template-manifest",
                    source_export_template_manifest.as_posix(),
                    "--column-dictionary",
                    source_export_dictionary.as_posix(),
                    "--output-dir",
                    source_export_starter_kit_dir.as_posix(),
                    "--manifest-output",
                    source_export_starter_kit_manifest.as_posix(),
                    "--report-output",
                    source_export_starter_kit_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_create_source_export_starter_kit.log",
                [source_export_starter_kit_index, source_export_starter_kit_manifest, source_export_starter_kit_report],
            )
        )

    if hypothesis_source_unlocks_enabled:
        stages.append(
            Stage(
                "stage_0_hypothesis_source_unlocks",
                [
                    python,
                    script("plan_hypothesis_source_unlocks.py"),
                    "--source-curation-tasks",
                    source_curation_tasks.as_posix(),
                    "--plan-output",
                    hypothesis_source_unlock_plan.as_posix(),
                    "--matrix-output",
                    hypothesis_source_unlock_matrix.as_posix(),
                    "--report-output",
                    hypothesis_source_unlock_report.as_posix(),
                ],
                logs_dir / "00_plan_hypothesis_source_unlocks.log",
                [hypothesis_source_unlock_plan, hypothesis_source_unlock_matrix, hypothesis_source_unlock_report],
            )
        )

    if minimum_source_curation_enabled:
        stages.append(
            Stage(
                "stage_0_minimum_source_curation",
                [
                    python,
                    script("plan_minimum_source_curation.py"),
                    "--hypothesis-source-unlocks",
                    hypothesis_source_unlock_plan.as_posix(),
                    "--starter-kit-manifest",
                    source_export_starter_kit_manifest.as_posix(),
                    "--source-plan-output",
                    minimum_source_curation_source_plan.as_posix(),
                    "--hypothesis-plan-output",
                    minimum_source_curation_hypothesis_plan.as_posix(),
                    "--report-output",
                    minimum_source_curation_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_plan_minimum_source_curation.log",
                [minimum_source_curation_source_plan, minimum_source_curation_hypothesis_plan, minimum_source_curation_report],
            )
        )

    if priority_source_preflight_enabled:
        stages.append(
            Stage(
                "stage_0_priority_source_preflight",
                [
                    python,
                    script("preflight_priority_source_exports.py"),
                    "--minimum-source-plan",
                    minimum_source_curation_source_plan.as_posix(),
                    "--max-rank",
                    priority_source_preflight_max_rank,
                    "--preflight-output",
                    priority_source_preflight_summary.as_posix(),
                    "--issue-output",
                    priority_source_preflight_issues.as_posix(),
                    "--report-output",
                    priority_source_preflight_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_preflight_priority_source_exports.log",
                [priority_source_preflight_summary, priority_source_preflight_issues, priority_source_preflight_report],
            )
        )

    if priority_source_collection_packet_enabled:
        stages.append(
            Stage(
                "stage_0_priority_source_collection_packet",
                [
                    python,
                    script("create_priority_source_collection_packet.py"),
                    "--minimum-source-plan",
                    minimum_source_curation_source_plan.as_posix(),
                    "--source-query-commands",
                    source_query_commands.as_posix(),
                    "--starter-kit-manifest",
                    source_export_starter_kit_manifest.as_posix(),
                    "--preflight",
                    priority_source_preflight_summary.as_posix(),
                    "--output-dir",
                    priority_source_collection_packet_dir.as_posix(),
                    "--manifest-output",
                    priority_source_collection_packet_manifest.as_posix(),
                    "--report-output",
                    priority_source_collection_packet_report.as_posix(),
                    "--max-rank",
                    priority_source_preflight_max_rank,
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_create_priority_source_collection_packet.log",
                [priority_source_collection_packet_index, priority_source_collection_packet_manifest, priority_source_collection_packet_report],
            )
        )

    if source_enablement_enabled:
        stages.append(
            Stage(
                "stage_0_source_enablement",
                [
                    python,
                    script("plan_source_enablement.py"),
                    "--source-acquisition-plan",
                    source_acquisition_plan.as_posix(),
                    "--source-export-validation",
                    source_export_validation.as_posix(),
                    "--minimum-source-plan",
                    minimum_source_curation_source_plan.as_posix(),
                    "--imports-config",
                    source_imports_config.as_posix(),
                    "--catalog",
                    sample_builder_catalog.as_posix(),
                    "--plan-output",
                    source_enablement_plan.as_posix(),
                    "--report-output",
                    source_enablement_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_plan_source_enablement.log",
                [source_enablement_plan, source_enablement_report],
            )
        )

    if source_enablement_apply_enabled:
        command = [
            python,
            script("apply_source_enablement.py"),
            "--enablement-plan",
            source_enablement_plan.as_posix(),
            "--imports-config",
            source_imports_config.as_posix(),
            "--catalog",
            sample_builder_catalog.as_posix(),
            "--report-output",
            source_enablement_apply_report.as_posix(),
            "--root",
            root.as_posix(),
        ]
        if source_enablement_apply_imports:
            command.append("--enable-imports")
        if source_enablement_apply_catalog:
            command.append("--enable-catalog")
        stages.append(
            Stage(
                "stage_0_source_enablement_apply",
                command,
                logs_dir / "00_apply_source_enablement_dry_run.log",
                [source_enablement_apply_report],
            )
        )

    if source_curation_packet_enabled:
        stages.append(
            Stage(
                "stage_0_source_curation_packet",
                [
                    python,
                    script("create_source_curation_packet.py"),
                    "--tasks",
                    source_curation_tasks.as_posix(),
                    "--output-dir",
                    source_curation_packet_dir.as_posix(),
                    "--manifest-output",
                    source_curation_packet_manifest.as_posix(),
                    "--report-output",
                    source_curation_packet_report.as_posix(),
                ],
                logs_dir / "00_create_source_curation_packet.log",
                [source_curation_packet_index, source_curation_packet_manifest, source_curation_packet_report],
            )
        )

    if sample_builder_enabled:
        stages.append(
            Stage(
                "stage_0_samples",
                [
                    python,
                    script("build_samples_from_sources.py"),
                    "--catalog",
                    sample_builder_catalog.as_posix(),
                    "--output-samples",
                    sample_builder_output.as_posix(),
                    "--report-output",
                    sample_builder_report.as_posix(),
                ],
                logs_dir / "00_build_samples_from_sources.log",
                [sample_builder_output, sample_builder_report],
            )
        )

    if source_overlap_enabled:
        stages.append(
            Stage(
                "stage_0_source_overlap_audit",
                [
                    python,
                    script("audit_source_overlaps.py"),
                    "--samples",
                    samples.as_posix(),
                    "--overlap-output",
                    source_overlap_groups.as_posix(),
                    "--source-summary-output",
                    source_overlap_summary.as_posix(),
                    "--report-output",
                    source_overlap_report.as_posix(),
                ],
                logs_dir / "00_audit_source_overlaps.log",
                [source_overlap_groups, source_overlap_summary, source_overlap_report],
            )
        )

    if sample_support_enabled:
        stages.append(
            Stage(
                "stage_0_sample_support",
                [
                    python,
                    script("audit_sample_support.py"),
                    "--samples",
                    samples.as_posix(),
                    "--thresholds",
                    thresholds.as_posix(),
                    "--hypothesis-output",
                    sample_support_hypotheses.as_posix(),
                    "--summary-output",
                    sample_support_summary.as_posix(),
                    "--report-output",
                    sample_support_report.as_posix(),
                ],
                logs_dir / "00_audit_sample_support.log",
                [sample_support_hypotheses, sample_support_summary, sample_support_report],
            )
        )

    if sample_support_sources_enabled:
        stages.append(
            Stage(
                "stage_0_sample_support_sources",
                [
                    python,
                    script("plan_sample_support_sources.py"),
                    "--sample-support-summary",
                    sample_support_summary.as_posix(),
                    "--minimum-source-plan",
                    minimum_source_curation_source_plan.as_posix(),
                    "--column-dictionary",
                    source_export_dictionary.as_posix(),
                    "--bridge-output",
                    sample_support_source_bridge.as_posix(),
                    "--report-output",
                    sample_support_source_bridge_report.as_posix(),
                ],
                logs_dir / "00_plan_sample_support_sources.log",
                [sample_support_source_bridge, sample_support_source_bridge_report],
            )
        )

    if sample_support_export_preflight_enabled:
        stages.append(
            Stage(
                "stage_0_sample_support_export_preflight",
                [
                    python,
                    script("preflight_sample_support_exports.py"),
                    "--bridge",
                    sample_support_source_bridge.as_posix(),
                    "--preflight-output",
                    sample_support_export_preflight.as_posix(),
                    "--report-output",
                    sample_support_export_preflight_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_preflight_sample_support_exports.log",
                [sample_support_export_preflight, sample_support_export_preflight_report],
            )
        )

    if source_readiness_dashboard_enabled:
        stages.append(
            Stage(
                "stage_0_source_readiness_dashboard",
                [
                    python,
                    script("build_source_readiness_dashboard.py"),
                    "--minimum-source-plan",
                    minimum_source_curation_source_plan.as_posix(),
                    "--source-export-validation",
                    source_export_validation.as_posix(),
                    "--source-enablement-plan",
                    source_enablement_plan.as_posix(),
                    "--source-enablement-apply",
                    source_enablement_apply_report.as_posix(),
                    "--sample-support-preflight",
                    sample_support_export_preflight.as_posix(),
                    "--dashboard-output",
                    source_readiness_dashboard.as_posix(),
                    "--report-output",
                    source_readiness_dashboard_report.as_posix(),
                ],
                logs_dir / "00_build_source_readiness_dashboard.log",
                [source_readiness_dashboard, source_readiness_dashboard_report],
            )
        )

    if source_curation_work_order_enabled:
        stages.append(
            Stage(
                "stage_0_source_curation_work_order",
                [
                    python,
                    script("build_source_curation_work_order.py"),
                    "--dashboard",
                    source_readiness_dashboard.as_posix(),
                    "--sample-support-summary",
                    sample_support_summary.as_posix(),
                    "--work-order-output",
                    source_curation_work_order.as_posix(),
                    "--report-output",
                    source_curation_work_order_report.as_posix(),
                ],
                logs_dir / "00_build_source_curation_work_order.log",
                [source_curation_work_order, source_curation_work_order_report],
            )
        )

    if source_work_order_packets_enabled:
        stages.append(
            Stage(
                "stage_0_source_work_order_packets",
                [
                    python,
                    script("create_source_work_order_packets.py"),
                    "--work-orders",
                    source_curation_work_order.as_posix(),
                    "--starter-kit-manifest",
                    source_export_starter_kit_manifest.as_posix(),
                    "--dashboard",
                    source_readiness_dashboard.as_posix(),
                    "--output-dir",
                    source_work_order_packets_dir.as_posix(),
                    "--manifest-output",
                    source_work_order_packets_manifest.as_posix(),
                    "--report-output",
                    source_work_order_packets_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_create_source_work_order_packets.log",
                [source_work_order_packets_index, source_work_order_packets_manifest, source_work_order_packets_report],
            )
        )

    if source_curation_issue_bodies_enabled:
        stages.append(
            Stage(
                "stage_0_source_curation_issue_bodies",
                [
                    python,
                    script("create_source_curation_issue_bodies.py"),
                    "--work-orders",
                    source_curation_work_order.as_posix(),
                    "--issue-dir",
                    source_curation_issue_dir.as_posix(),
                    "--manifest-output",
                    source_curation_issue_manifest.as_posix(),
                    "--commands-output",
                    source_curation_issue_commands.as_posix(),
                    "--shell-output",
                    source_curation_issue_shell.as_posix(),
                    "--report-output",
                    source_curation_issue_report.as_posix(),
                ],
                logs_dir / "00_create_source_curation_issue_bodies.log",
                [source_curation_issue_manifest, source_curation_issue_commands, source_curation_issue_shell, source_curation_issue_report],
            )
        )

    if source_work_order_acceptance_enabled:
        stages.append(
            Stage(
                "stage_0_source_work_order_acceptance",
                [
                    python,
                    script("check_source_work_order_acceptance.py"),
                    "--work-orders",
                    source_curation_work_order.as_posix(),
                    "--acceptance-output",
                    source_work_order_acceptance.as_posix(),
                    "--report-output",
                    source_work_order_acceptance_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_check_source_work_order_acceptance.log",
                [source_work_order_acceptance, source_work_order_acceptance_report],
            )
        )

    if source_post_acceptance_enabled:
        stages.append(
            Stage(
                "stage_0_source_post_acceptance",
                [
                    python,
                    script("plan_source_post_acceptance.py"),
                    "--acceptance",
                    source_work_order_acceptance.as_posix(),
                    "--enablement-plan",
                    source_enablement_plan.as_posix(),
                    "--enablement-apply",
                    source_enablement_apply_report.as_posix(),
                    "--plan-output",
                    source_post_acceptance_plan.as_posix(),
                    "--report-output",
                    source_post_acceptance_report.as_posix(),
                ],
                logs_dir / "00_plan_source_post_acceptance.log",
                [source_post_acceptance_plan, source_post_acceptance_report],
            )
        )

    if sample_support_curation_packet_enabled:
        stages.append(
            Stage(
                "stage_0_sample_support_curation_packet",
                [
                    python,
                    script("create_sample_support_curation_packet.py"),
                    "--bridge",
                    sample_support_source_bridge.as_posix(),
                    "--preflight",
                    sample_support_export_preflight.as_posix(),
                    "--output-dir",
                    sample_support_curation_packet_dir.as_posix(),
                    "--manifest-output",
                    sample_support_curation_packet_manifest.as_posix(),
                    "--report-output",
                    sample_support_curation_packet_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_create_sample_support_curation_packet.log",
                [sample_support_curation_packet_index, sample_support_curation_packet_manifest, sample_support_curation_packet_report],
            )
        )

    stages.append(
        Stage(
            "stage_1_manifest",
            [
                python,
                script("00_build_phage_manifest.py"),
                "--input",
                samples.as_posix(),
                "--manifest-output",
                manifest.as_posix(),
                "--report-output",
                manifest_report.as_posix(),
                "--excluded-output",
                excluded.as_posix(),
            ],
            logs_dir / "00_build_phage_manifest.log",
            [manifest, manifest_report, excluded],
        )
    )

    if sequence_acquisition_enabled:
        stages.append(
            Stage(
                "stage_1_sequence_acquisition",
                [
                    python,
                    script("plan_sequence_acquisition.py"),
                    "--manifest",
                    manifest.as_posix(),
                    "--raw-directory",
                    sequence_raw_directory.as_posix(),
                    "--plan-output",
                    sequence_acquisition_plan.as_posix(),
                    "--report-output",
                    sequence_acquisition_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_plan_sequence_acquisition.log",
                [sequence_acquisition_plan, sequence_acquisition_report],
            )
        )

    if sequence_fetch_manifest_enabled:
        stages.append(
            Stage(
                "stage_1_sequence_fetch_manifest",
                [
                    python,
                    script("create_sequence_fetch_manifest.py"),
                    "--sequence-plan",
                    sequence_acquisition_plan.as_posix(),
                    "--manifest-output",
                    sequence_fetch_manifest.as_posix(),
                    "--commands-output",
                    sequence_fetch_commands.as_posix(),
                    "--report-output",
                    sequence_fetch_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_create_sequence_fetch_manifest.log",
                [sequence_fetch_manifest, sequence_fetch_commands, sequence_fetch_report],
            )
        )

    if sequence_fetch_review_packet_enabled:
        stages.append(
            Stage(
                "stage_1_sequence_fetch_review_packet",
                [
                    python,
                    script("create_sequence_fetch_review_packet.py"),
                    "--manifest",
                    sequence_fetch_manifest.as_posix(),
                    "--packet-output",
                    sequence_fetch_review_packet.as_posix(),
                    "--report-output",
                    sequence_fetch_review_report.as_posix(),
                ],
                logs_dir / "00_create_sequence_fetch_review_packet.log",
                [sequence_fetch_review_packet, sequence_fetch_review_report],
            )
        )

    stages.append(
        Stage(
            "stage_1_sequence_qc",
            [
                python,
                script("00_qc_genome_sequences.py"),
                "--manifest",
                manifest.as_posix(),
                "--thresholds",
                thresholds.as_posix(),
                "--qc-output",
                sequence_qc.as_posix(),
                "--report-output",
                sequence_qc_report.as_posix(),
                "--root",
                root.as_posix(),
            ],
            logs_dir / "00_qc_genome_sequences.log",
            [sequence_qc, sequence_qc_report],
        )
    )

    if external_evidence_enabled:
        stages.append(
            Stage(
                "stage_1_external_evidence_plan",
                [
                    python,
                    script("plan_external_evidence.py"),
                    "--workflow-config",
                    validation_workflow_config,
                    "--tool-availability",
                    tool_availability.as_posix(),
                    "--manifest",
                    manifest.as_posix(),
                    "--sequence-qc",
                    sequence_qc.as_posix(),
                    "--plan-output",
                    external_evidence_plan.as_posix(),
                    "--report-output",
                    external_evidence_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_plan_external_evidence.log",
                [external_evidence_plan, external_evidence_report],
            )
        )

    if external_evidence_templates_enabled:
        stages.append(
            Stage(
                "stage_1_external_evidence_templates",
                [
                    python,
                    script("create_external_evidence_templates.py"),
                    "--evidence-plan",
                    external_evidence_plan.as_posix(),
                    "--templates-dir",
                    external_evidence_templates_dir.as_posix(),
                    "--manifest-output",
                    external_evidence_template_manifest.as_posix(),
                    "--report-output",
                    external_evidence_template_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_create_external_evidence_templates.log",
                [external_evidence_template_manifest, external_evidence_template_report],
            )
        )

    if external_evidence_run_packets_enabled:
        stages.append(
            Stage(
                "stage_1_external_evidence_run_packets",
                [
                    python,
                    script("create_external_evidence_run_packets.py"),
                    "--evidence-plan",
                    external_evidence_plan.as_posix(),
                    "--template-manifest",
                    external_evidence_template_manifest.as_posix(),
                    "--output-dir",
                    external_evidence_run_packets_dir.as_posix(),
                    "--manifest-output",
                    external_evidence_run_packets_manifest.as_posix(),
                    "--report-output",
                    external_evidence_run_packets_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_create_external_evidence_run_packets.log",
                [external_evidence_run_packets_manifest, external_evidence_run_packets_report, external_evidence_run_packets_dir / "README.md"],
            )
        )

    if external_evidence_acceptance_enabled:
        stages.append(
            Stage(
                "stage_1_external_evidence_acceptance",
                [
                    python,
                    script("check_external_evidence_acceptance.py"),
                    "--evidence-plan",
                    external_evidence_plan.as_posix(),
                    "--acceptance-output",
                    external_evidence_acceptance.as_posix(),
                    "--report-output",
                    external_evidence_acceptance_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "00_check_external_evidence_acceptance.log",
                [external_evidence_acceptance, external_evidence_acceptance_report],
            )
        )

    if external_evidence_unlocks_enabled:
        stages.append(
            Stage(
                "stage_1_external_evidence_unlocks",
                [
                    python,
                    script("plan_external_evidence_unlocks.py"),
                    "--external-evidence-plan",
                    external_evidence_plan.as_posix(),
                    "--external-evidence-template-manifest",
                    external_evidence_template_manifest.as_posix(),
                    "--plan-output",
                    external_evidence_unlock_plan.as_posix(),
                    "--matrix-output",
                    external_evidence_unlock_matrix.as_posix(),
                    "--report-output",
                    external_evidence_unlock_report.as_posix(),
                ],
                logs_dir / "00_plan_external_evidence_unlocks.log",
                [external_evidence_unlock_plan, external_evidence_unlock_matrix, external_evidence_unlock_report],
            )
        )

    if production_evidence_handoff_enabled:
        stages.append(
            Stage(
                "stage_1_production_evidence_handoff",
                [
                    python,
                    script("create_production_evidence_handoff.py"),
                    "--external-evidence-plan",
                    external_evidence_plan.as_posix(),
                    "--unlock-plan",
                    external_evidence_unlock_plan.as_posix(),
                    "--output",
                    production_evidence_handoff.as_posix(),
                    "--report-output",
                    production_evidence_handoff_report.as_posix(),
                ],
                logs_dir / "00_create_production_evidence_handoff.log",
                [production_evidence_handoff, production_evidence_handoff_report],
            )
        )

    if pipeline_efficiency_enabled:
        stages.append(
            Stage(
                "stage_1_pipeline_efficiency_audit",
                [
                    python,
                    script("audit_pipeline_efficiency.py"),
                    "--workflow-config",
                    pipeline_efficiency_workflow_config.as_posix(),
                    "--source-catalog",
                    sample_builder_catalog.as_posix(),
                    "--source-imports",
                    source_imports_config.as_posix(),
                    "--thresholds",
                    thresholds.as_posix(),
                    "--external-evidence-plan",
                    external_evidence_plan.as_posix(),
                    "--sequence-acquisition-plan",
                    sequence_acquisition_plan.as_posix(),
                    "--output",
                    pipeline_efficiency_audit.as_posix(),
                    "--report-output",
                    pipeline_efficiency_report.as_posix(),
                ],
                logs_dir / "00_audit_pipeline_efficiency.log",
                [pipeline_efficiency_audit, pipeline_efficiency_report],
            )
        )

    stages.extend([
        Stage(
            "stage_2_dereplication",
            [
                python,
                script("01_dereplicate_phages.py"),
                "--manifest",
                manifest.as_posix(),
                "--thresholds",
                thresholds.as_posix(),
                "--sequence-qc",
                sequence_qc.as_posix(),
                "--ani-output",
                ani.as_posix(),
                "--clusters-output",
                clusters.as_posix(),
                "--representatives-output",
                representatives.as_posix(),
                "--report-output",
                derep_report.as_posix(),
            ],
            logs_dir / "01_dereplicate_phages.log",
            [ani, clusters, representatives, derep_report],
        ),
        Stage(
            "stage_3_annotations",
            [
                python,
                script("02_build_annotation_tables.py"),
                "--manifest",
                manifest.as_posix(),
                "--clusters",
                clusters.as_posix(),
                "--annotations-output",
                annotations.as_posix(),
                "--gene-clusters-output",
                gene_clusters.as_posix(),
                "--pangenome-output",
                pangenome.as_posix(),
                "--report-output",
                annotation_report.as_posix(),
            ],
            logs_dir / "02_build_annotation_tables.log",
            [annotations, gene_clusters, pangenome, annotation_report],
        ),
    ])

    if external_evidence_proteins_enabled:
        stages.append(
            Stage(
                "stage_3_external_evidence_proteins",
                [
                    python,
                    script("export_external_evidence_proteins.py"),
                    "--annotations",
                    annotations.as_posix(),
                    "--all-proteins-output",
                    external_evidence_all_proteins.as_posix(),
                    "--candidate-proteins-output",
                    external_evidence_candidate_proteins.as_posix(),
                    "--manifest-output",
                    external_evidence_protein_manifest.as_posix(),
                    "--report-output",
                    external_evidence_protein_report.as_posix(),
                ],
                logs_dir / "03_export_external_evidence_proteins.log",
                [
                    external_evidence_all_proteins,
                    external_evidence_candidate_proteins,
                    external_evidence_protein_manifest,
                    external_evidence_protein_report,
                ],
            )
        )

    if phage_antidefense_handoff_enabled:
        stages.append(
            Stage(
                "stage_3_phage_antidefense_handoff",
                [
                    python,
                    script("create_phage_antidefense_screening_handoff.py"),
                    "--annotations",
                    annotations.as_posix(),
                    "--protein-manifest",
                    external_evidence_protein_manifest.as_posix(),
                    "--all-proteins",
                    external_evidence_all_proteins.as_posix(),
                    "--manifest-output",
                    phage_antidefense_handoff_manifest.as_posix(),
                    "--commands-output",
                    phage_antidefense_handoff_commands.as_posix(),
                    "--report-output",
                    phage_antidefense_handoff_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "03_create_phage_antidefense_screening_handoff.log",
                [phage_antidefense_handoff_manifest, phage_antidefense_handoff_commands, phage_antidefense_handoff_report],
            )
        )

    stages.extend([
        Stage(
            "stage_4_rbp_depolymerase",
            [
                python,
                script("03_predict_rbps_depolymerases.py"),
                "--annotations",
                annotations.as_posix(),
                "--gene-clusters",
                gene_clusters.as_posix(),
                "--thresholds",
                thresholds.as_posix(),
                "--candidates-output",
                rbp_candidates.as_posix(),
                "--domain-architectures-output",
                domain_architectures.as_posix(),
                "--module-clusters-output",
                module_clusters.as_posix(),
                "--novel-candidates-output",
                novel_candidates.as_posix(),
                "--report-output",
                rbp_report.as_posix(),
            ],
            logs_dir / "03_predict_rbps_depolymerases.log",
            [rbp_candidates, domain_architectures, module_clusters, novel_candidates, rbp_report],
        ),
        Stage(
            "stage_5_host_features",
            [
                python,
                script("04_integrate_host_features.py"),
                "--manifest",
                manifest.as_posix(),
                "--clusters",
                clusters.as_posix(),
                "--host-metadata-output",
                host_metadata.as_posix(),
                "--kaptive-output",
                kaptive.as_posix(),
                "--kleborate-output",
                kleborate.as_posix(),
                "--phage-host-links-output",
                phage_host_links.as_posix(),
                "--report-output",
                host_report.as_posix(),
            ],
            logs_dir / "04_integrate_host_features.log",
            [host_metadata, kaptive, kleborate, phage_host_links, host_report],
        ),
    ])

    if host_defense_handoff_enabled:
        stages.append(
            Stage(
                "stage_5_host_defense_handoff",
                [
                    python,
                    script("create_host_defense_run_handoff.py"),
                    "--host-metadata",
                    host_metadata.as_posix(),
                    "--sequence-plan",
                    sequence_acquisition_plan.as_posix(),
                    "--manifest-output",
                    host_defense_handoff_manifest.as_posix(),
                    "--commands-output",
                    host_defense_handoff_commands.as_posix(),
                    "--report-output",
                    host_defense_handoff_report.as_posix(),
                    "--root",
                    root.as_posix(),
                ],
                logs_dir / "05_create_host_defense_run_handoff.log",
                [host_defense_handoff_manifest, host_defense_handoff_commands, host_defense_handoff_report],
            )
        )

    stages.extend([
        Stage(
            "stage_6_defense_counterdefense",
            [
                python,
                script("05_integrate_defense_counterdefense.py"),
                "--host-metadata",
                host_metadata.as_posix(),
                "--phage-host-links",
                phage_host_links.as_posix(),
                "--annotations",
                annotations.as_posix(),
                "--host-defense-output",
                host_defense.as_posix(),
                "--phage-antidefense-output",
                phage_antidefense.as_posix(),
                "--compatibility-output",
                compatibility.as_posix(),
                "--report-output",
                defense_report.as_posix(),
            ],
            logs_dir / "05_integrate_defense_counterdefense.log",
            [host_defense, phage_antidefense, compatibility, defense_report],
        ),
        Stage(
            "stage_7_models",
            [
                python,
                script("06_compare_feature_models.py"),
                "--manifest",
                manifest.as_posix(),
                "--clusters",
                clusters.as_posix(),
                "--rbp-candidates",
                rbp_candidates.as_posix(),
                "--phage-host-links",
                phage_host_links.as_posix(),
                "--compatibility-features",
                compatibility.as_posix(),
                "--model-comparison-output",
                model_comparison.as_posix(),
                "--feature-importance-output",
                feature_importance.as_posix(),
                "--prediction-errors-output",
                prediction_errors.as_posix(),
                "--hypothesis-summary-output",
                hypothesis_summary.as_posix(),
                "--report-output",
                model_report.as_posix(),
            ],
            logs_dir / "06_compare_feature_models.log",
            [model_comparison, feature_importance, prediction_errors, hypothesis_summary, model_report],
        ),
        Stage(
            "stage_8_figures",
            [
                python,
                script("07_generate_figure_sources.py"),
                "--manifest",
                manifest.as_posix(),
                "--clusters",
                clusters.as_posix(),
                "--gene-clusters",
                gene_clusters.as_posix(),
                "--pangenome",
                pangenome.as_posix(),
                "--rbp-candidates",
                rbp_candidates.as_posix(),
                "--rbp-modules",
                module_clusters.as_posix(),
                "--novel-candidates",
                novel_candidates.as_posix(),
                "--host-metadata",
                host_metadata.as_posix(),
                "--phage-host-links",
                phage_host_links.as_posix(),
                "--host-defense",
                host_defense.as_posix(),
                "--phage-antidefense",
                phage_antidefense.as_posix(),
                "--compatibility",
                compatibility.as_posix(),
                "--model-comparison",
                model_comparison.as_posix(),
                "--feature-importance",
                feature_importance.as_posix(),
                "--output-dir",
                figure_dir.as_posix(),
                "--manifest-output",
                figure_manifest.as_posix(),
                "--report-output",
                figure_report.as_posix(),
            ],
            logs_dir / "07_generate_figure_sources.log",
            figure_outputs,
        ),
        Stage(
            "stage_9_source_export_validation_self_test",
            [
                python,
                script("self_test_source_export_validation.py"),
                "--output",
                source_export_validation_self_test.as_posix(),
                "--report-output",
                source_export_validation_self_test_report.as_posix(),
            ],
            logs_dir / "09_self_test_source_export_validation.log",
            [source_export_validation_self_test, source_export_validation_self_test_report],
        ),
        Stage(
            "stage_9_external_evidence_acceptance_self_test",
            [
                python,
                script("self_test_external_evidence_acceptance.py"),
                "--output",
                external_evidence_acceptance_self_test.as_posix(),
                "--report-output",
                external_evidence_acceptance_self_test_report.as_posix(),
            ],
            logs_dir / "09_self_test_external_evidence_acceptance.log",
            [external_evidence_acceptance_self_test, external_evidence_acceptance_self_test_report],
        ),
        Stage(
            "stage_9_validation",
            [
                python,
                script("08_validate_workflow.py"),
                "--root",
                root.as_posix(),
                "--results-dir",
                validation_results_dir,
                "--samples",
                validation_samples,
                "--workflow-config",
                validation_workflow_config,
                "--schema-output",
                validation_schema.as_posix(),
                "--hypothesis-output",
                validation_hypotheses.as_posix(),
                "--inventory-output",
                validation_inventory.as_posix(),
                "--report-output",
                validation_report.as_posix(),
            ],
            logs_dir / "08_validate_workflow.log",
            [validation_schema, validation_hypotheses, validation_inventory, validation_report],
        ),
        Stage(
            "stage_10_study_readiness",
            [
                python,
                script("09_audit_study_readiness.py"),
                "--root",
                root.as_posix(),
                "--results-dir",
                validation_results_dir,
                "--samples",
                validation_samples,
                "--readiness-output",
                study_readiness.as_posix(),
                "--report-output",
                study_readiness_report.as_posix(),
            ],
            logs_dir / "09_audit_study_readiness.log",
            [study_readiness, study_readiness_report],
        ),
        Stage(
            "stage_10_readiness_actions",
            [
                python,
                script("10_plan_readiness_actions.py"),
                "--root",
                root.as_posix(),
                "--results-dir",
                validation_results_dir,
                "--readiness",
                study_readiness.as_posix(),
                "--source-curation-tasks",
                source_curation_tasks.as_posix(),
                "--hypothesis-source-unlocks",
                hypothesis_source_unlock_plan.as_posix(),
                "--sequence-fetch-manifest",
                sequence_fetch_manifest.as_posix(),
                "--external-evidence-unlocks",
                external_evidence_unlock_plan.as_posix(),
                "--action-output",
                readiness_action_plan.as_posix(),
                "--report-output",
                readiness_action_report.as_posix(),
            ],
            logs_dir / "10_plan_readiness_actions.log",
            [readiness_action_plan, readiness_action_report],
        ),
        Stage(
            "stage_11_hypothesis_traceability",
            [
                python,
                script("12_build_hypothesis_traceability.py"),
                "--source-plan",
                minimum_source_curation_hypothesis_plan.as_posix(),
                "--evidence-plan",
                external_evidence_unlock_plan.as_posix(),
                "--sample-support",
                sample_support_hypotheses.as_posix(),
                "--hypothesis-summary",
                hypothesis_summary.as_posix(),
                "--hypothesis-coverage",
                validation_hypotheses.as_posix(),
                "--figure-manifest",
                figure_manifest.as_posix(),
                "--readiness",
                study_readiness.as_posix(),
                "--trace-output",
                hypothesis_traceability.as_posix(),
                "--report-output",
                hypothesis_traceability_report.as_posix(),
            ],
            logs_dir / "12_build_hypothesis_traceability.log",
            [hypothesis_traceability, hypothesis_traceability_report],
        ),
        Stage(
            "stage_11_claim_support_audit",
            [
                python,
                script("13_audit_claim_support.py"),
                "--claim-ledger",
                (root / "docs" / "claim_ledger.md").as_posix(),
                "--workflow-validation",
                validation_report.as_posix(),
                "--hypothesis-summary",
                hypothesis_summary.as_posix(),
                "--hypothesis-traceability",
                hypothesis_traceability.as_posix(),
                "--external-evidence-plan",
                external_evidence_plan.as_posix(),
                "--audit-output",
                claim_support_audit.as_posix(),
                "--report-output",
                claim_support_report.as_posix(),
            ],
            logs_dir / "13_audit_claim_support.log",
            [claim_support_audit, claim_support_report],
        ),
        Stage(
            "stage_11_goal_completion_audit",
            [
                python,
                script("11_audit_goal_completion.py"),
                "--root",
                root.as_posix(),
                "--results-dir",
                validation_results_dir,
                "--audit-output",
                goal_completion_audit.as_posix(),
                "--report-output",
                goal_completion_report.as_posix(),
            ],
            logs_dir / "11_audit_goal_completion.log",
            [goal_completion_audit, goal_completion_report],
        ),
    ])

    optional_by_stage = {
        "stage_2_dereplication": [("--pairwise-similarity", optional_input(config, root, ("inputs", "pairwise_similarity")))],
        "stage_3_annotations": [("--annotation-input", optional_input(config, root, ("inputs", "annotation_input")))],
        "stage_4_rbp_depolymerase": [
            ("--domain-evidence", optional_input(config, root, ("inputs", "domain_evidence"))),
            ("--structural-evidence", optional_input(config, root, ("inputs", "structural_evidence"))),
        ],
        "stage_5_host_features": [
            ("--kleborate-input", optional_input(config, root, ("inputs", "kleborate_input"))),
            ("--kaptive-input", optional_input(config, root, ("inputs", "kaptive_input"))),
        ],
        "stage_6_defense_counterdefense": [
            ("--host-defense-input", optional_input(config, root, ("inputs", "host_defense_input"))),
            ("--phage-antidefense-input", optional_input(config, root, ("inputs", "phage_antidefense_input"))),
        ],
    }

    for stage in stages:
        for option, path in optional_by_stage.get(stage.name, []):
            add_optional(stage.command, option, path)

    return stages, run_report


def run_stage(root: Path, stage: Stage, dry_run: bool) -> dict[str, str]:
    ensure_parent_dirs([stage.log_path, *stage.expected_outputs])
    command = command_text(stage.command)
    if dry_run:
        print(f"[dry-run] {stage.name}: {command}")
        return {
            "stage": stage.name,
            "status": "dry_run",
            "return_code": "",
            "command": command,
            "log_path": rel_or_abs(root, stage.log_path),
            "expected_outputs": ";".join(rel_or_abs(root, path) for path in stage.expected_outputs),
            "missing_outputs": "",
            "message": "command not executed",
        }

    with stage.log_path.open("w") as log_handle:
        log_handle.write(f"$ {command}\n\n")
        result = subprocess.run(stage.command, cwd=root, stdout=log_handle, stderr=subprocess.STDOUT, text=True)

    missing_outputs = [path for path in stage.expected_outputs if not path.exists()]
    status = "pass" if result.returncode == 0 and not missing_outputs else "fail"
    return {
        "stage": stage.name,
        "status": status,
        "return_code": str(result.returncode),
        "command": command,
        "log_path": rel_or_abs(root, stage.log_path),
        "expected_outputs": ";".join(rel_or_abs(root, path) for path in stage.expected_outputs),
        "missing_outputs": ";".join(rel_or_abs(root, path) for path in missing_outputs),
        "message": "ok" if status == "pass" else "stage failed or expected outputs are missing",
    }


def select_stages(stages: list[Stage], requested: list[str]) -> list[Stage]:
    if not requested:
        return stages
    requested_set = set(requested)
    return [stage for stage in stages if stage.name in requested_set]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    config_path = resolve(root, args.config)

    try:
        config = load_yaml(config_path)
        stages, run_report = build_stages(config, root)
        selected = select_stages(stages, args.stages)
        report_rows = []
        for stage in selected:
            row = run_stage(root, stage, args.dry_run)
            report_rows.append(row)
            if row["status"] == "fail":
                break
        if not args.dry_run:
            write_tsv(run_report, REPORT_COLUMNS, report_rows)
        failures = [row for row in report_rows if row["status"] == "fail"]
        if failures:
            print(f"Workflow stopped after {len(report_rows)} stage(s); first failure: {failures[0]['stage']}")
            return 1
        print(f"Workflow completed {len(report_rows)} stage(s).")
        if not args.dry_run:
            print(f"Run report: {rel_or_abs(root, run_report)}")
        return 0
    except WorkflowError as exc:
        print(f"Workflow error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
