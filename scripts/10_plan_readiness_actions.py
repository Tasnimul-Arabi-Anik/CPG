#!/usr/bin/env python3
"""Create a ranked action plan from manuscript-readiness blockers."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


ACTION_COLUMNS = [
    "action_id",
    "priority",
    "action_area",
    "requirement_ids",
    "blocking_requirement_count",
    "related_hypotheses",
    "primary_artifacts_to_populate",
    "supporting_planning_files",
    "command_hint",
    "validation_command",
    "expected_downstream_outputs",
    "readiness_blockers_addressed",
    "rationale",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a ranked manuscript-readiness action plan from current workflow outputs.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--results-dir", default="results", help="Audited results directory, relative to root unless absolute.")
    parser.add_argument("--readiness", required=True, help="Study readiness TSV from scripts/09_audit_study_readiness.py.")
    parser.add_argument("--source-curation-tasks", required=True, help="Source curation task TSV.")
    parser.add_argument("--hypothesis-source-unlocks", required=True, help="H1-H6 source unlock plan TSV.")
    parser.add_argument("--sequence-fetch-manifest", required=True, help="Sequence fetch manifest TSV.")
    parser.add_argument("--external-evidence-unlocks", required=True, help="H1-H6 external evidence unlock plan TSV.")
    parser.add_argument("--action-output", required=True, help="Output ranked action plan TSV.")
    parser.add_argument("--report-output", required=True, help="Output summary report TSV.")
    return parser.parse_args()


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
        reader = csv.DictReader(handle, delimiter="	")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="	")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def join(values: Iterable[str]) -> str:
    cleaned = []
    for value in values:
        if not is_missing(value) and value not in cleaned:
            cleaned.append(value)
    return ";".join(cleaned) if cleaned else "NA"


def split_joined(value: str) -> list[str]:
    if is_missing(value):
        return []
    parts: list[str] = []
    for token in value.replace(",", ";").split(";"):
        token = token.strip()
        if token and token not in parts:
            parts.append(token)
    return parts


def blocking_requirements(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("blocking_for_manuscript") == "true" or row.get("status") == "fail"]


def reqs_by_area(rows: list[dict[str, str]], areas: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("area") in areas and (row.get("blocking_for_manuscript") == "true" or row.get("status") == "fail")]


def hypotheses_from_unlock_rows(rows: list[dict[str, str]], blocked_column: str) -> list[str]:
    return [row.get("hypothesis", "") for row in rows if not is_missing(row.get(blocked_column))]


def blocked_values(rows: list[dict[str, str]], column: str) -> list[str]:
    values: list[str] = []
    for row in rows:
        values.extend(split_joined(row.get(column, "")))
    return values


def source_artifacts(tasks: list[dict[str, str]]) -> list[str]:
    artifacts: list[str] = []
    for row in tasks:
        if row.get("blocking_for_real_study") == "true" or row.get("curation_status") != "ready_for_sample_build":
            artifacts.extend([row.get("expected_export_path", ""), row.get("template_path", ""), row.get("command_hint", "")])
    return artifacts


def parse_rank(row: dict[str, str]) -> int:
    try:
        return int(float(row.get("recommended_rank", "999")))
    except ValueError:
        return 999


def prioritized_source_artifacts(minimum_source_rows: list[dict[str, str]], fallback_tasks: list[dict[str, str]], max_rank: int = 2) -> list[str]:
    priority_rows = [
        row for row in sorted(minimum_source_rows, key=parse_rank)
        if parse_rank(row) <= max_rank and row.get("curation_status") != "ready_for_sample_build"
    ]
    if not priority_rows:
        return source_artifacts(fallback_tasks)
    artifacts: list[str] = []
    for row in priority_rows:
        artifacts.extend([
            row.get("expected_export_path", ""),
            row.get("starter_template_path", ""),
            row.get("starter_readme_path", ""),
            row.get("recommended_action", ""),
        ])
    return artifacts


def prioritized_source_hypotheses(minimum_source_rows: list[dict[str, str]], fallback_hypotheses: Iterable[str], max_rank: int = 2) -> list[str]:
    hypotheses: list[str] = []
    for row in sorted(minimum_source_rows, key=parse_rank):
        if parse_rank(row) <= max_rank:
            hypotheses.extend(split_joined(row.get("required_for_hypotheses", "")))
    return hypotheses or list(fallback_hypotheses)


def source_work_order_artifacts(acceptance_rows: list[dict[str, str]], packet_rows: list[dict[str, str]], max_items: int = 2) -> list[str]:
    packet_by_work_order = {row.get("work_order_id", ""): row for row in packet_rows}
    artifacts: list[str] = []
    blocking_rows = [row for row in acceptance_rows if row.get("blocking_issue") == "true"]
    for row in sorted(blocking_rows, key=lambda item: item.get("work_order_id", ""))[:max_items]:
        packet = packet_by_work_order.get(row.get("work_order_id", ""), {})
        artifacts.extend([
            packet.get("packet_path", ""),
            row.get("expected_export_path", ""),
            row.get("next_action", ""),
        ])
    return artifacts


def combine_artifacts(*groups: Iterable[str]) -> list[str]:
    artifacts: list[str] = []
    for group in groups:
        for value in group:
            if not is_missing(value) and value not in artifacts:
                artifacts.append(value)
    return artifacts


def sequence_artifacts(fetch_rows: list[dict[str, str]], results_dir: Path, root: Path) -> list[str]:
    artifacts = [display_path(root, results_dir / "qc/sequence_acquisition_plan.tsv"), display_path(root, results_dir / "qc/sequence_fetch_commands.sh")]
    for row in fetch_rows:
        if row.get("ready_to_run") == "true" or row.get("acquisition_status") not in {"local_sequence_ready", "already_local"}:
            artifacts.extend([row.get("expected_sequence_path", ""), row.get("command_text", "")])
    return artifacts


def build_action(
    action_id: str,
    priority: int,
    action_area: str,
    requirements: list[dict[str, str]],
    related_hypotheses: Iterable[str],
    artifacts: Iterable[str],
    supporting: Iterable[str],
    command_hint: str,
    validation_command: str,
    expected: Iterable[str],
    rationale: str,
) -> dict[str, str]:
    return {
        "action_id": action_id,
        "priority": str(priority),
        "action_area": action_area,
        "requirement_ids": join(row.get("requirement_id", "") for row in requirements),
        "blocking_requirement_count": str(len(requirements)),
        "related_hypotheses": join(related_hypotheses),
        "primary_artifacts_to_populate": join(artifacts),
        "supporting_planning_files": join(supporting),
        "command_hint": command_hint,
        "validation_command": validation_command,
        "expected_downstream_outputs": join(expected),
        "readiness_blockers_addressed": join(row.get("area", "") for row in requirements),
        "rationale": rationale,
    }


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    results_dir = resolve(root, args.results_dir)
    readiness_path = resolve(root, args.readiness)
    source_tasks_path = resolve(root, args.source_curation_tasks)
    hypothesis_source_path = resolve(root, args.hypothesis_source_unlocks)
    sequence_fetch_path = resolve(root, args.sequence_fetch_manifest)
    external_unlock_path = resolve(root, args.external_evidence_unlocks)
    action_output = resolve(root, args.action_output)
    report_output = resolve(root, args.report_output)

    _, readiness_rows = read_tsv(readiness_path)
    _, source_tasks = read_tsv(source_tasks_path)
    _, hypothesis_source_unlocks = read_tsv(hypothesis_source_path)
    _, minimum_source_rows = read_tsv(results_dir / "qc/minimum_source_curation_plan.tsv")
    _, source_work_order_acceptance = read_tsv(results_dir / "qc/source_work_order_acceptance.tsv")
    _, source_work_order_packets = read_tsv(results_dir / "qc/source_work_order_packet_manifest.tsv")
    _, fetch_rows = read_tsv(sequence_fetch_path)
    _, external_unlocks = read_tsv(external_unlock_path)

    blockers = blocking_requirements(readiness_rows)
    actions: list[dict[str, str]] = []

    source_reqs = reqs_by_area(readiness_rows, {"dataset_curation", "source_curation", "source_acquisition", "source_work_order_acceptance", "sample_support"})
    if source_reqs:
        actions.append(build_action(
            "A01",
            1,
            "curate_reviewed_source_exports",
            source_reqs,
            prioritized_source_hypotheses(minimum_source_rows, hypotheses_from_unlock_rows(hypothesis_source_unlocks, "blocking_required_sources")),
            combine_artifacts(
                source_work_order_artifacts(source_work_order_acceptance, source_work_order_packets),
                prioritized_source_artifacts(minimum_source_rows, source_tasks),
            ),
            [display_path(root, source_tasks_path), display_path(root, hypothesis_source_path), display_path(root, results_dir / "qc/minimum_source_curation_plan.tsv"), display_path(root, results_dir / "qc/minimum_hypothesis_source_plan.tsv"), display_path(root, results_dir / "qc/source_curation_work_order.tsv"), display_path(root, results_dir / "qc/source_work_order_packet_manifest.tsv"), display_path(root, results_dir / "qc/source_work_order_packets"), display_path(root, results_dir / "qc/source_work_order_acceptance.tsv"), display_path(root, results_dir / "qc/source_post_acceptance_plan.tsv"), display_path(root, results_dir / "qc/sample_support_by_hypothesis.tsv"), display_path(root, results_dir / "qc/sample_support_summary.tsv"), display_path(root, results_dir / "qc/sample_support_source_bridge.tsv"), display_path(root, results_dir / "qc/sample_support_export_preflight.tsv"), display_path(root, results_dir / "qc/sample_support_curation_packet_manifest.tsv"), display_path(root, results_dir / "qc/sample_support_curation_packet"), display_path(root, results_dir / "qc/source_query_commands.sh"), display_path(root, results_dir / "qc/source_export_column_dictionary.tsv")],
            "Fill the highest-ranked reviewed export TSVs from the source work-order packets first, then rerun acceptance and enable imports in config/source_imports.yaml or config/source_catalog.yaml.",
            "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_curation_tasks stage_0_hypothesis_source_unlocks stage_0_samples stage_0_source_overlap_audit stage_0_sample_support stage_1_manifest",
            ["results/source_builder/samples.tsv", "results/qc/sample_support_by_hypothesis.tsv", "results/qc/phage_genome_manifest.tsv", "results/qc/source_curation_tasks.tsv"],
            "Real sample rows are the first dependency for every downstream genome, host, evidence, model, and figure requirement. The primary artifacts list starts with blocking source work-order packets when available, then falls back to the highest-ranked missing source exports.",
        ))

    sequence_reqs = reqs_by_area(readiness_rows, {"sequence_acquisition", "sequence_qc"})
    if sequence_reqs:
        actions.append(build_action(
            "A02",
            2,
            "add_or_fetch_genome_fastas",
            sequence_reqs,
            hypotheses_from_unlock_rows(hypothesis_source_unlocks, "blocking_required_sources"),
            sequence_artifacts(fetch_rows, results_dir, root),
            [display_path(root, sequence_fetch_path), display_path(root, results_dir / "qc/sequence_acquisition_plan.tsv"), "data/raw/genomes/"],
            "Place curated FASTA files under data/raw/genomes/ or run reviewed accession fetch commands from the sequence fetch manifest; do not edit data/raw/ outputs in pipeline scripts.",
            "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_1_sequence_acquisition stage_1_sequence_fetch_manifest stage_1_sequence_qc stage_2_dereplication",
            ["results/qc/genome_sequence_qc.tsv", "results/clusters/phage_clusters.tsv", "results/clusters/representatives.tsv"],
            "Passing FASTA-backed records are required before dereplication, annotation planning, and external tool outputs are meaningful.",
        ))

    evidence_reqs = reqs_by_area(readiness_rows, {"external_evidence", "annotation_pangenome", "rbp_depolymerase", "host_features", "defense_counterdefense"})
    if evidence_reqs:
        actions.append(build_action(
            "A03",
            3,
            "provide_external_analysis_evidence",
            evidence_reqs,
            hypotheses_from_unlock_rows(external_unlocks, "blocking_required_evidence"),
            blocked_values(external_unlocks, "blocking_required_evidence"),
            [display_path(root, external_unlock_path), display_path(root, results_dir / "qc/external_evidence_plan.tsv"), display_path(root, results_dir / "qc/external_evidence_template_manifest.tsv"), display_path(root, results_dir / "qc/external_evidence_templates")],
            "Generate or paste reviewed tool outputs for pairwise similarity, Pharokka/PHROGs annotations, domain/structural RBP evidence, Kleborate/Kaptive, host defense, and phage anti-defense tables; configure their paths in config/workflow.yaml inputs.",
            "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_1_external_evidence_plan stage_1_external_evidence_templates stage_1_external_evidence_unlocks stage_3_annotations stage_4_rbp_depolymerase stage_5_host_features stage_6_defense_counterdefense",
            ["results/annotations/phage_annotations.tsv", "results/rbp_depolymerase/candidates.tsv", "results/host_features/phage_host_links.tsv", "results/defense_systems/compatibility_features.tsv"],
            "H1-H6 require external evidence beyond metadata: RBP/depolymerase modules, K/O/ST host features, and defense/counter-defense features.",
        ))

    analysis_reqs = reqs_by_area(readiness_rows, {"dereplication", "hypothesis_tests", "figures"})
    if analysis_reqs:
        actions.append(build_action(
            "A04",
            4,
            "rerun_models_figures_and_readiness_audit",
            analysis_reqs,
            ["H1", "H2", "H3", "H4", "H5", "H6"],
            ["results/models/model_comparison.tsv", "results/models/hypothesis_summary.tsv", "results/figures/"],
            [display_path(root, results_dir / "validation/hypothesis_coverage.tsv"), display_path(root, results_dir / "figures/figure_manifest.tsv"), display_path(root, readiness_path)],
            "After source rows, sequences, and evidence tables are populated, rerun the full workflow and inspect H1-H6 coverage before drafting claims.",
            "python scripts/run_workflow.py --config config/workflow.yaml",
            ["results/models/model_comparison.tsv", "results/models/hypothesis_summary.tsv", "results/figures/figure_manifest.tsv", "results/validation/study_readiness.tsv"],
            "Quantitative tests and figure source data should be regenerated only after upstream evidence is populated.",
        ))

    if not actions:
        actions.append(build_action(
            "A00",
            0,
            "no_blocking_action_required",
            [],
            ["H1", "H2", "H3", "H4", "H5", "H6"],
            [display_path(root, readiness_path)],
            [display_path(root, readiness_path)],
            "No blocking manuscript-readiness actions were detected by the current audit.",
            "python scripts/run_workflow.py --config config/workflow.yaml",
            ["results/validation/study_readiness.tsv"],
            "The readiness audit currently has no blocking rows; continue with scientific review of outputs and claim wording.",
        ))

    actions = sorted(actions, key=lambda row: int(row["priority"]))
    reports = [
        {"severity": "info", "item": "readiness_actions", "message": f"actions={len(actions)}; blocking_requirements={len(blockers)}"},
    ]
    if blockers:
        reports.append({"severity": "warning", "item": "readiness_actions", "message": "One or more actions are required before manuscript-level claims are supported."})
    else:
        reports.append({"severity": "info", "item": "readiness_actions", "message": "No blocking manuscript-readiness actions detected."})

    write_tsv(action_output, ACTION_COLUMNS, actions)
    write_tsv(report_output, REPORT_COLUMNS, reports)
    print(f"Wrote {len(actions)} readiness action rows for {len(blockers)} blocking requirements.")


if __name__ == "__main__":
    main()
