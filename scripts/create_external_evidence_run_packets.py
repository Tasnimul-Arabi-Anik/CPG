#!/usr/bin/env python3
"""Render reviewer-facing packets for producing external evidence TSVs."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "evidence_id",
    "packet_path",
    "template_path",
    "optional_input_key",
    "configured_input_path",
    "evidence_status",
    "tool_ids",
    "tool_status",
    "eligible_sequence_records",
    "action_status",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create production run packets for external evidence TSVs.")
    parser.add_argument("--evidence-plan", required=True, help="External evidence plan TSV.")
    parser.add_argument("--template-manifest", required=True, help="External evidence template manifest TSV.")
    parser.add_argument("--output-dir", required=True, help="Directory for Markdown packets.")
    parser.add_argument("--manifest-output", required=True, help="Packet manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV.")
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


def display_path(root: Path, path: Path | str) -> str:
    path_obj = Path(path)
    if not str(path_obj):
        return ""
    try:
        return path_obj.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path_obj.as_posix()


def safe_filename(value: str, fallback: str) -> str:
    raw = value or fallback
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")
    return raw or fallback


def template_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("evidence_id", ""): row for row in rows if row.get("evidence_id", "")}


def packet_status(row: dict[str, str]) -> str:
    status = row.get("evidence_status", "")
    configured_rows = row.get("configured_input_rows", "0") or "0"
    if status == "provided_input_ready" and configured_rows != "0":
        return "configured_input_ready"
    if row.get("eligible_sequence_records", "0") in {"", "0"}:
        return "waiting_for_sequence_records"
    if status in {"missing_tool_or_input", "manual_evidence_required"}:
        return "ready_for_external_run_or_reviewed_tsv"
    return "review_current_evidence_state"


def render_packet(root: Path, row: dict[str, str], template: dict[str, str]) -> str:
    evidence_id = row.get("evidence_id", "")
    template_path = template.get("template_path", "")
    header_columns = template.get("header_columns", "")
    required_columns = row.get("configured_input_required_columns", "")
    suggested_command = row.get("suggested_command", "")
    configured_path = row.get("configured_input_path", "")
    optional_key = row.get("optional_input_key", "")
    antidefense_handoff_lines: list[str] = []
    if evidence_id == "phage_antidefense_candidates":
        antidefense_handoff_lines = [
            "## Workflow Phage Protein Inputs",
            "",
            "The workflow exports a phage anti-defense screening handoff linked to stable `annotation_gene_id` values:",
            "",
            "- Screening manifest: `results/qc/phage_antidefense_screening_handoff.tsv`",
            "- HMM/sequence-search command hints: `results/qc/phage_antidefense_screening_commands.sh`",
            "- All phage/prophage proteins: `results/qc/external_evidence_proteins/phage_proteins.faa`",
            "",
            "These files are screening instructions only; they are not accepted anti-defense calls and should not be configured as `inputs.phage_antidefense_input`.",
            "",
            "## Normalization Commands",
            "",
            "Reviewed phage anti-defense hit tables can be normalized with `scripts/normalize_defense_external_evidence.py` into the Stage 6 optional input schema.",
            "",
            "```bash",
            "python scripts/normalize_defense_external_evidence.py --phage-antidefense-input <reviewed_antidefense_hits.tsv> --phage-antidefense-format reviewed_hits_tsv --phage-antidefense-output data/metadata/external_evidence/phage_antidefense_candidates.tsv --report-output results/qc/normalize_defense_external_evidence_report.tsv",
            "```",
            "",
            "After review, configure the populated phage anti-defense TSV in `config/workflow.yaml` as `inputs.phage_antidefense_input`. Header-only normalizer outputs are not accepted evidence.",
            "",
        ]
    host_defense_handoff_lines: list[str] = []
    if evidence_id == "host_defense_systems":
        host_defense_handoff_lines = [
            "## Workflow Host FASTA Inputs",
            "",
            "The workflow exports a host-defense run handoff for reviewed host genomes with local FASTA files:",
            "",
            "- Host defense run manifest: `results/qc/host_defense_run_handoff.tsv`",
            "- DefenseFinder/PADLOC command file: `results/qc/host_defense_run_commands.sh`",
            "",
            "These files are run instructions only; they are not host defense calls and should not be configured as `inputs.host_defense_input`.",
            "",
            "## Normalization Commands",
            "",
            "Reviewed DefenseFinder/PADLOC-style host-defense tables can be normalized with `scripts/normalize_defense_external_evidence.py` into the Stage 6 optional input schema.",
            "",
            "```bash",
            "python scripts/normalize_defense_external_evidence.py --host-defense-input <reviewed_host_defense.tsv> --host-defense-format defensefinder_tsv --host-defense-output data/metadata/external_evidence/host_defense_systems.tsv --report-output results/qc/normalize_defense_external_evidence_report.tsv",
            "```",
            "",
            "Use `--host-defense-format padloc_tsv` for reviewed PADLOC-style tables. After review, configure the populated host defense TSV in `config/workflow.yaml` as `inputs.host_defense_input`. Header-only normalizer outputs are not accepted evidence.",
            "",
        ]
    protein_handoff_lines: list[str] = []
    if evidence_id in {"rbp_domain_evidence", "rbp_structural_evidence"}:
        protein_handoff_lines = [
            "## Workflow Protein Inputs",
            "",
            "The workflow exports protein FASTA files after normalized annotation so domain/profile and structure-informed tools can be run against stable `annotation_gene_id` values:",
            "",
            "- All phage/prophage proteins: `results/qc/external_evidence_proteins/phage_proteins.faa`",
            "- RBP/depolymerase-prioritized proteins: `results/qc/external_evidence_proteins/rbp_depolymerase_candidate_proteins.faa`",
            "- Protein manifest with priority rationale: `results/qc/external_evidence_proteins/protein_export_manifest.tsv`",
            "",
            "Priority labels are run-target hints only; they are not domain or structural evidence and should not be used as novelty support without external tool results.",
            "",
            "## Normalization Commands",
            "",
            "Reviewed HMMER/Foldseek/Phold-style outputs can be normalized with `scripts/normalize_rbp_external_evidence.py`. The normalizer writes both target TSVs so Stage 4 can consume a consistent schema.",
            "",
            "For HMMER domain evidence only:",
            "",
            "```bash",
            "python scripts/normalize_rbp_external_evidence.py --domain-input <reviewed_hmmer.domtblout> --domain-format hmmer_domtblout --hmmer-mode hmmsearch --annotation-manifest results/annotations/phage_annotations.tsv --domain-tool hmmer --domain-database <reviewed_profile_database> --domain-database-version <reviewed_snapshot> --domain-output data/metadata/external_evidence/rbp_domain_evidence.tsv --structural-output data/metadata/external_evidence/rbp_structural_evidence.tsv --report-output results/qc/rbp_external_evidence_normalization_report.tsv",
            "```",
            "",
            "For reviewed generic domain and Foldseek/Phold-style structural tables:",
            "",
            "```bash",
            "python scripts/normalize_rbp_external_evidence.py --domain-input <reviewed_domain_hits.tsv> --domain-format generic_tsv --structural-input <reviewed_structural_hits.tsv> --structural-format foldseek_tsv --foldseek-fields query,target,alntmscore,prob,evalue --annotation-manifest results/annotations/phage_annotations.tsv --domain-tool <reviewed_domain_tool> --domain-database <reviewed_profile_database> --domain-database-version <reviewed_profile_snapshot> --structural-tool foldseek --structural-database <reviewed_structure_database> --structural-database-version <reviewed_structure_snapshot> --domain-output data/metadata/external_evidence/rbp_domain_evidence.tsv --structural-output data/metadata/external_evidence/rbp_structural_evidence.tsv --report-output results/qc/rbp_external_evidence_normalization_report.tsv",
            "```",
            "",
            "After review, configure the populated target TSVs in `config/workflow.yaml` as `inputs.domain_evidence` and `inputs.structural_evidence`. Header-only normalizer outputs are not accepted evidence. Existing evidence outputs are preserved when an input is absent unless `--overwrite-empty` is explicitly supplied; when both inputs are supplied, use evidence-type-specific provenance flags rather than shared provenance.",
            "",
            "Normalized evidence targets:",
            "",
            "- Domain evidence target: `data/metadata/external_evidence/rbp_domain_evidence.tsv`",
            "- Structural evidence target: `data/metadata/external_evidence/rbp_structural_evidence.tsv`",
            "",
        ]
    lines = [
        f"# External Evidence Packet: {evidence_id}",
        "",
        "This packet describes how to produce or review one production evidence TSV.",
        "",
        "## Current State",
        "",
        f"- Analysis layer: `{row.get('analysis_layer', '')}`",
        f"- Hypotheses supported: `{row.get('hypotheses_supported', '')}`",
        f"- Evidence status: `{row.get('evidence_status', '')}`",
        f"- Tool status: `{row.get('tool_status', '')}`",
        f"- Planned tool IDs: `{row.get('tool_ids', '') or 'NA'}`",
        f"- Required sequence scope: `{row.get('required_sequence_scope', '')}`",
        f"- Eligible sequence records: `{row.get('eligible_sequence_records', '0')}`",
        f"- Real-claim use status: `{row.get('real_claim_use_status', '')}`",
        "",
        "## Required TSV",
        "",
        f"- Workflow input key: `{optional_key}`",
        f"- Configure path in `config/workflow.yaml` under `inputs.{optional_key}`.",
        f"- Current configured path: `{configured_path or 'not configured'}`",
        f"- Template path: `{template_path or 'not available'}`",
        f"- Required columns: `{required_columns or 'see template'}`",
        f"- Template columns: `{header_columns or 'not available'}`",
        "",
        "## Suggested Production Command",
        "",
        "```bash",
        suggested_command or "# No command specified; provide a reviewed TSV matching the required schema.",
        "```",
        "",
        "The command is advisory. Run the appropriate standard tool in the environment where its databases and compute resources are available, then normalize the output to the template columns.",
        "",
        *protein_handoff_lines,
        *host_defense_handoff_lines,
        *antidefense_handoff_lines,
        "## Acceptance Checklist",
        "",
        "- The TSV is derived from reviewed sequence-backed records, not mock fixtures.",
        "- The TSV has the required identity columns and provenance fields.",
        "- Unknown biological values use `NA` rather than invented values.",
        "- The `evidence_source` or `notes` field records tool name, version or database snapshot when available, command context, and reviewer initials/date if manually curated.",
        "- After configuring the TSV path, rerun:",
        "",
        "```bash",
        "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_1_external_evidence_plan stage_1_external_evidence_templates stage_1_external_evidence_run_packets stage_1_external_evidence_unlocks stage_1_production_evidence_handoff stage_1_pipeline_efficiency_audit stage_9_validation stage_10_study_readiness stage_11_claim_support_audit",
        "```",
        "",
        "## Claim Boundary",
        "",
        "This packet only supports evidence acquisition. Do not strengthen biological claims until the full workflow, study-readiness audit, hypothesis coverage, and claim-support audit allow it.",
        "",
    ]
    return "\n".join(lines)


def write_index(root: Path, output_dir: Path, manifest_rows: list[dict[str, str]]) -> None:
    lines = [
        "# External Evidence Run Packets",
        "",
        "These packets convert `results/qc/external_evidence_plan.tsv` into per-evidence production handoffs.",
        "They are not evidence by themselves. Populate reviewed TSVs, configure them in `config/workflow.yaml`, and rerun validation.",
        "",
        "| evidence_id | status | packet | template |",
        "| --- | --- | --- | --- |",
    ]
    for row in manifest_rows:
        lines.append(
            f"| `{row['evidence_id']}` | `{row['action_status']}` | `{row['packet_path']}` | `{row['template_path']}` |"
        )
    lines.append("")
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    evidence_path = Path(args.evidence_plan)
    if not evidence_path.is_absolute():
        evidence_path = root / evidence_path
    template_manifest_path = Path(args.template_manifest)
    if not template_manifest_path.is_absolute():
        template_manifest_path = root / template_manifest_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    manifest_output = Path(args.manifest_output)
    if not manifest_output.is_absolute():
        manifest_output = root / manifest_output
    report_output = Path(args.report_output)
    if not report_output.is_absolute():
        report_output = root / report_output

    evidence_fields, evidence_rows = read_tsv(evidence_path)
    template_fields, template_rows = read_tsv(template_manifest_path)
    report: list[dict[str, str]] = []
    required = {"evidence_id", "optional_input_key", "evidence_status", "suggested_command"}
    missing = sorted(required - set(evidence_fields))
    if missing:
        write_tsv(manifest_output, MANIFEST_COLUMNS, [])
        write_tsv(report_output, REPORT_COLUMNS, [{"severity": "error", "item": "external_evidence_run_packets", "message": "Missing evidence plan columns: " + ";".join(missing)}])
        return 1
    if not template_fields:
        write_tsv(manifest_output, MANIFEST_COLUMNS, [])
        write_tsv(report_output, REPORT_COLUMNS, [{"severity": "error", "item": "external_evidence_run_packets", "message": "Template manifest is missing or empty."}])
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    templates = template_lookup(template_rows)
    manifest: list[dict[str, str]] = []
    for index, row in enumerate(evidence_rows, start=1):
        evidence_id = row.get("evidence_id", "") or f"evidence_{index}"
        template = templates.get(evidence_id, {})
        packet_path = output_dir / (safe_filename(evidence_id, f"evidence_{index}") + ".md")
        packet_path.write_text(render_packet(root, row, template), encoding="utf-8")
        status = packet_status(row)
        manifest.append(
            {
                "evidence_id": evidence_id,
                "packet_path": display_path(root, packet_path),
                "template_path": template.get("template_path", ""),
                "optional_input_key": row.get("optional_input_key", ""),
                "configured_input_path": row.get("configured_input_path", ""),
                "evidence_status": row.get("evidence_status", ""),
                "tool_ids": row.get("tool_ids", ""),
                "tool_status": row.get("tool_status", ""),
                "eligible_sequence_records": row.get("eligible_sequence_records", ""),
                "action_status": status,
                "next_action": row.get("next_action", ""),
            }
        )

    write_index(root, output_dir, manifest)
    ready = sum(1 for row in manifest if row["action_status"] == "ready_for_external_run_or_reviewed_tsv")
    configured = sum(1 for row in manifest if row["action_status"] == "configured_input_ready")
    waiting = sum(1 for row in manifest if row["action_status"] == "waiting_for_sequence_records")
    report.append(
        {
            "severity": "info",
            "item": "external_evidence_run_packets",
            "message": f"packets={len(manifest)}; configured={configured}; ready_for_external_run_or_reviewed_tsv={ready}; waiting_for_sequence_records={waiting}",
        }
    )
    write_tsv(manifest_output, MANIFEST_COLUMNS, manifest)
    write_tsv(report_output, REPORT_COLUMNS, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
