#!/usr/bin/env python3
"""Plan external evidence generation for production comparative genomics analyses."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


PLAN_COLUMNS = [
    "evidence_id",
    "analysis_layer",
    "hypotheses_supported",
    "optional_input_key",
    "configured_input_path",
    "configured_input_exists",
    "configured_input_rows",
    "configured_input_schema_status",
    "configured_input_required_columns",
    "configured_input_missing_columns",
    "required_sequence_scope",
    "eligible_sequence_records",
    "tool_ids",
    "tool_status",
    "evidence_status",
    "blocking_for_manuscript",
    "next_action",
    "suggested_command",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
PHAGE_LIKE = {"phage", "prophage", "metagenomic_viral_contig"}

EVIDENCE_SPECS = [
    {
        "evidence_id": "pairwise_similarity",
        "analysis_layer": "dereplication",
        "hypotheses_supported": "H1;H6",
        "optional_input_key": "pairwise_similarity",
        "required_all": ["genome_id_1", "genome_id_2", "identity_percent", "coverage_percent", "method"],
        "required_any": [],
        "required_sequence_scope": "phage_like",
        "tool_ids": ["mash", "viridic"],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Run Mash/VIRIDIC or provide a pairwise similarity TSV matching docs/dereplication_schema.md.",
        "command": "mash sketch phage_fastas/*.fna && mash dist sketches.msh sketches.msh > pairwise_similarity.tsv; or run VIRIDIC and export pairwise identity/coverage TSV.",
        "notes": "Needed for species-like dereplication and taxonomy-vs-RBP model comparisons.",
    },
    {
        "evidence_id": "phage_annotation",
        "analysis_layer": "annotation_pangenome",
        "hypotheses_supported": "H1;H2;H3;H4;H6",
        "optional_input_key": "annotation_input",
        "required_all": ["genome_id", "gene_id", "product"],
        "required_any": [],
        "required_sequence_scope": "phage_like",
        "tool_ids": ["pharokka"],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Run Pharokka or provide a phage annotation TSV matching docs/annotation_schema.md.",
        "command": "pharokka.py -i <phage_fasta> -o results/external/pharokka/<genome_id> -d <pharokka_db> -t <threads>",
        "notes": "Primary source for gene calls, PHROGs, RBP keywords, pangenome inputs, and anti-defense keyword screening.",
    },
    {
        "evidence_id": "rbp_domain_evidence",
        "analysis_layer": "rbp_depolymerase",
        "hypotheses_supported": "H1;H2;H3;H6",
        "optional_input_key": "domain_evidence",
        "required_all": ["annotation_gene_id", "domain_id", "domain_name"],
        "required_any": [],
        "required_sequence_scope": "phage_like",
        "tool_ids": [],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Provide domain evidence TSV from HMM/profile/domain searches matching docs/rbp_depolymerase_schema.md.",
        "command": "Run local domain/profile annotation on predicted proteins and write gene_id/domain/evidence columns to the configured domain_evidence TSV.",
        "notes": "Supports modular RBP/depolymerase architecture rather than BLAST-only novelty claims.",
    },
    {
        "evidence_id": "rbp_structural_evidence",
        "analysis_layer": "rbp_depolymerase",
        "hypotheses_supported": "H1;H2;H3;H6",
        "optional_input_key": "structural_evidence",
        "required_all": ["annotation_gene_id", "structural_hit_id", "structural_hit_name"],
        "required_any": [],
        "required_sequence_scope": "phage_like",
        "tool_ids": ["phold"],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Run Phold/Foldseek-style structural annotation or provide structural evidence TSV matching docs/rbp_depolymerase_schema.md.",
        "command": "phold run -i <pharokka_output_or_proteins> -o results/external/phold/<genome_id>",
        "notes": "Needed for remote RBP/depolymerase homolog detection and structural novelty claims.",
    },
    {
        "evidence_id": "kleborate_host_features",
        "analysis_layer": "host_features",
        "hypotheses_supported": "H1;H2;H4;H5",
        "optional_input_key": "kleborate_input",
        "required_all": [],
        "required_any": [["sample", "genome_id", "host_genome_id", "strain", "assembly"]],
        "required_sequence_scope": "host",
        "tool_ids": ["kleborate"],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Run Kleborate or provide host feature TSV matching docs/host_feature_schema.md.",
        "command": "kleborate -a host_genomes/*.fna -o results/external/kleborate.tsv",
        "notes": "Provides species complex, ST, AMR, and virulence context for host-background models.",
    },
    {
        "evidence_id": "kaptive_ko_typing",
        "analysis_layer": "host_features",
        "hypotheses_supported": "H1;H2;H4;H5",
        "optional_input_key": "kaptive_input",
        "required_all": [],
        "required_any": [["sample", "genome_id", "host_genome_id", "strain", "assembly"]],
        "required_sequence_scope": "host",
        "tool_ids": ["kaptive"],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Run Kaptive or provide K/O typing TSV matching docs/host_feature_schema.md.",
        "command": "kaptive assembly --assembly host_genomes/*.fna --out results/external/kaptive.tsv <kaptive_db>",
        "notes": "Provides K/O labels used for receptor-module association tests.",
    },
    {
        "evidence_id": "host_defense_systems",
        "analysis_layer": "defense_counterdefense",
        "hypotheses_supported": "H4;H5",
        "optional_input_key": "host_defense_input",
        "required_all": ["system", "type"],
        "required_any": [["sample", "genome_id", "host_genome_id"]],
        "required_sequence_scope": "host",
        "tool_ids": ["defensefinder", "padloc"],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Run DefenseFinder/PADLOC or provide host defense TSV matching docs/defense_counterdefense_schema.md.",
        "command": "defense-finder run host_genomes/*.fna -o results/external/defensefinder/; or padloc --fna host_genomes/*.fna --outdir results/external/padloc/",
        "notes": "Required for the intracellular compatibility layer of the study.",
    },
    {
        "evidence_id": "phage_antidefense_candidates",
        "analysis_layer": "defense_counterdefense",
        "hypotheses_supported": "H3;H4",
        "optional_input_key": "phage_antidefense_input",
        "required_all": ["antidefense_class"],
        "required_any": [["phage_genome_id", "annotation_gene_id"]],
        "required_sequence_scope": "phage_like",
        "tool_ids": ["pharokka", "phold"],
        "blocking_for_manuscript": "true",
        "next_when_ready": "Provide curated phage anti-defense candidate TSV or derive candidates from annotation/structural evidence.",
        "command": "Screen phage annotations and structural evidence for anti-CRISPR, methyltransferase, DNA-modification, and defense-inhibitor candidates; write TSV matching docs/defense_counterdefense_schema.md.",
        "notes": "Needed for combined receptor plus defense/counter-defense model features.",
    },
]


class EvidencePlanError(Exception):
    """Raised for invalid evidence planning inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan external evidence generation for production analysis stages.")
    parser.add_argument("--workflow-config", required=True, help="Workflow YAML config used for optional input paths.")
    parser.add_argument("--tool-availability", required=True, help="Tool availability TSV from audit_tool_availability.py.")
    parser.add_argument("--manifest", required=True, help="Stage 1 manifest TSV.")
    parser.add_argument("--sequence-qc", required=True, help="Sequence QC TSV.")
    parser.add_argument("--plan-output", required=True, help="Output evidence plan TSV.")
    parser.add_argument("--report-output", required=True, help="Output evidence plan report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative paths.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise EvidencePlanError("PyYAML is required to read workflow configuration.") from exc
    if not path.exists():
        raise EvidencePlanError(f"Workflow config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise EvidencePlanError("Workflow config must contain a YAML mapping.")
    return data


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


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


def nested_get(data: dict, path: tuple[str, ...], default: str = "") -> str:
    current: object = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return "" if current is None else str(current)


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
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


def tool_status(tool_ids: list[str], tool_rows: dict[str, dict[str, str]]) -> str:
    if not tool_ids:
        return "not_configured"
    statuses = []
    for tool_id in tool_ids:
        row = tool_rows.get(tool_id, {})
        statuses.append(f"{tool_id}:{row.get('availability_status', 'not_audited')}")
    return ";".join(statuses)


def any_tool_available(tool_ids: list[str], tool_rows: dict[str, dict[str, str]]) -> bool:
    if not tool_ids:
        return False
    return any(tool_rows.get(tool_id, {}).get("availability_status") == "available" for tool_id in tool_ids)


def count_sequence_scope(manifest_rows: list[dict[str, str]], sequence_rows: list[dict[str, str]], scope: str) -> int:
    by_id = {row.get("genome_id", ""): row for row in manifest_rows}
    count = 0
    for seq_row in sequence_rows:
        if seq_row.get("passes_sequence_qc") != "true":
            continue
        genome_id = seq_row.get("genome_id", "")
        record_type = by_id.get(genome_id, {}).get("record_type", seq_row.get("record_type", ""))
        if scope == "phage_like" and record_type in PHAGE_LIKE:
            count += 1
        elif scope == "host" and record_type == "host":
            count += 1
        elif scope == "any":
            count += 1
    return count


def validate_input_schema(fieldnames: list[str], required_all: list[str], required_any: list[list[str]]) -> tuple[str, str, str]:
    if not fieldnames:
        required = [*required_all, *("one_of:" + "|".join(group) for group in required_any)]
        return "not_checked", ";".join(required), ""
    fields = set(fieldnames)
    missing = [column for column in required_all if column not in fields]
    for group in required_any:
        if not any(column in fields for column in group):
            missing.append("one_of:" + "|".join(group))
    required = [*required_all, *("one_of:" + "|".join(group) for group in required_any)]
    status = "pass" if not missing else "fail"
    return status, ";".join(required), ";".join(missing)


def classify(
    configured_path: str,
    input_exists: bool,
    input_rows: int,
    schema_status: str,
    eligible_records: int,
    tool_ids: list[str],
    tools_available: bool,
) -> tuple[str, str]:
    if configured_path:
        if input_exists and input_rows > 0 and schema_status == "pass":
            return "provided_input_ready", "No action required unless replacing this evidence with production output."
        if input_exists and input_rows > 0:
            return "configured_input_schema_invalid", "Fix missing required columns in the configured evidence TSV."
        if input_exists and input_rows == 0:
            return "configured_input_empty", "Populate the configured evidence TSV or clear the optional input until it is ready."
        return "configured_input_missing", "Create the configured evidence TSV or update the workflow optional input path."
    if eligible_records <= 0:
        return "waiting_for_sequence_data", "Populate source manifests, acquire local genome FASTA files, and rerun sequence QC."
    if tool_ids and tools_available:
        return "ready_to_run_external_tool", "Run the planned external tool and set the resulting TSV path in config/workflow.yaml."
    if tool_ids:
        return "missing_tool_or_input", "Install the planned tool or provide a precomputed TSV through config/workflow.yaml."
    return "manual_evidence_required", "Provide the required evidence TSV from an appropriate external analysis."


def plan_evidence(root: Path, workflow_config: Path, tool_availability: Path, manifest: Path, sequence_qc: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    config = load_yaml(workflow_config)
    _, tool_data = read_tsv(tool_availability)
    _, manifest_rows = read_tsv(manifest)
    _, sequence_rows = read_tsv(sequence_qc)
    tool_rows = {row.get("tool_id", ""): row for row in tool_data}
    plan: list[dict[str, str]] = []
    report: list[dict[str, str]] = []

    for spec in EVIDENCE_SPECS:
        key = spec["optional_input_key"]
        configured_value = nested_get(config, ("inputs", key), "")
        configured_path = resolve(root, configured_value) if configured_value else Path("")
        input_exists = bool(configured_value and configured_path.exists())
        input_fields, input_rows = read_tsv(configured_path) if input_exists else ([], [])
        schema_status, required_columns, missing_columns = validate_input_schema(
            input_fields,
            spec.get("required_all", []),
            spec.get("required_any", []),
        )
        eligible = count_sequence_scope(manifest_rows, sequence_rows, spec["required_sequence_scope"])
        tool_ids = spec["tool_ids"]
        status_text = tool_status(tool_ids, tool_rows)
        tools_available = any_tool_available(tool_ids, tool_rows)
        evidence_status, next_action = classify(configured_value, input_exists, len(input_rows), schema_status, eligible, tool_ids, tools_available)
        suggested = spec["command"] if evidence_status in {"ready_to_run_external_tool", "missing_tool_or_input", "manual_evidence_required", "waiting_for_sequence_data"} else spec["next_when_ready"]
        plan.append(
            {
                "evidence_id": spec["evidence_id"],
                "analysis_layer": spec["analysis_layer"],
                "hypotheses_supported": spec["hypotheses_supported"],
                "optional_input_key": key,
                "configured_input_path": display_path(root, configured_path) if configured_value else "",
                "configured_input_exists": str(input_exists).lower(),
                "configured_input_rows": str(len(input_rows)),
                "configured_input_schema_status": schema_status,
                "configured_input_required_columns": required_columns,
                "configured_input_missing_columns": missing_columns,
                "required_sequence_scope": spec["required_sequence_scope"],
                "eligible_sequence_records": str(eligible),
                "tool_ids": ";".join(tool_ids),
                "tool_status": status_text,
                "evidence_status": evidence_status,
                "blocking_for_manuscript": spec["blocking_for_manuscript"],
                "next_action": next_action,
                "suggested_command": suggested,
                "notes": spec["notes"],
            }
        )

    status_counts: dict[str, int] = {}
    for row in plan:
        status_counts[row["evidence_status"]] = status_counts.get(row["evidence_status"], 0) + 1
    add_report(report, "info", "evidence_plan", f"Planned {len(plan)} external evidence inputs.")
    for status, count in sorted(status_counts.items()):
        severity = "info" if status == "provided_input_ready" else "warning"
        add_report(report, severity, status, f"{count} evidence input(s).")
    invalid_schema = [row["evidence_id"] for row in plan if row["evidence_status"] == "configured_input_schema_invalid"]
    if invalid_schema:
        add_report(report, "warning", "configured_input_schema_invalid", "Schema-invalid evidence inputs: " + ";".join(invalid_schema))
    ready = status_counts.get("provided_input_ready", 0)
    if ready < len(plan):
        add_report(report, "warning", "production_evidence", f"{len(plan) - ready} evidence input(s) still need production data, tool runs, or configured TSVs.")
    return plan, report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        plan, report = plan_evidence(
            root,
            resolve(root, args.workflow_config),
            resolve(root, args.tool_availability),
            resolve(root, args.manifest),
            resolve(root, args.sequence_qc),
        )
        write_tsv(Path(args.plan_output), PLAN_COLUMNS, plan)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        warnings = sum(1 for row in report if row.get("severity") == "warning")
        errors = sum(1 for row in report if row.get("severity") == "error")
        print(f"External evidence plan complete: {len(plan)} inputs, {errors} errors, {warnings} warnings.")
        return 1 if errors else 0
    except EvidencePlanError as exc:
        report = [{"severity": "error", "item": "external_evidence_plan", "message": str(exc)}]
        write_tsv(Path(args.plan_output), PLAN_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        print(f"External evidence plan failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
