# Snakemake entrypoint for the config-driven Klebsiella phage CPG workflow.
# The direct runner is the single source of stage order and command wiring.
# Use a different workflow config with:
#   snakemake --config workflow_config=config/workflow.mock.yaml --cores 1

import glob
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from workflow_config import load_workflow_config

WORKFLOW_CONFIG = config.get("workflow_config", "config/workflow.yaml")
PYTHON = config.get("python", "python")


WF = load_workflow_config(WORKFLOW_CONFIG, ".")


def nested_get(data, keys, default=""):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return "" if current is None else str(current)


def configured_path(*keys, default=""):
    return nested_get(WF, keys, default)


def add_path(paths, value):
    if value:
        paths.append(value)


def collect_output_paths(node, paths, key=""):
    skip_keys = {"directory", "results_dir", "workflow_config"}
    if isinstance(node, dict):
        for child_key, child_value in node.items():
            collect_output_paths(child_value, paths, child_key)
    elif isinstance(node, str) and node and key not in skip_keys:
        paths.append(node)


def unique(paths):
    seen = set()
    output = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            output.append(path)
    return output


workflow_outputs = []

# Stage 0 planning, source, and sample-builder outputs.
add_path(workflow_outputs, configured_path("tool_audit", "availability", default="results/qc/tool_availability.tsv"))
add_path(workflow_outputs, configured_path("tool_audit", "report", default="results/qc/tool_audit_report.tsv"))
add_path(workflow_outputs, configured_path("source_queries", "plan", default="results/qc/source_query_plan.tsv"))
add_path(workflow_outputs, configured_path("source_queries", "report", default="results/qc/source_query_report.tsv"))
add_path(workflow_outputs, configured_path("source_export_templates", "manifest", default="results/qc/source_export_template_manifest.tsv"))
add_path(workflow_outputs, configured_path("source_export_templates", "report", default="results/qc/source_export_template_report.tsv"))
add_path(workflow_outputs, configured_path("source_export_validation", "validation", default="results/qc/source_export_validation.tsv"))
add_path(workflow_outputs, configured_path("source_export_validation", "report", default="results/qc/source_export_validation_report.tsv"))
add_path(workflow_outputs, configured_path("source_imports", "report", default="results/qc/source_import_report.tsv"))
add_path(workflow_outputs, configured_path("source_plan", "plan", default="results/qc/source_acquisition_plan.tsv"))
add_path(workflow_outputs, configured_path("source_plan", "report", default="results/qc/source_acquisition_report.tsv"))
add_path(workflow_outputs, configured_path("source_audit", "readiness", default="results/qc/source_catalog_readiness.tsv"))
add_path(workflow_outputs, configured_path("source_audit", "report", default="results/qc/source_catalog_audit_report.tsv"))
add_path(workflow_outputs, configured_path("sample_builder", "output_samples", default="results/source_builder/samples.tsv"))
add_path(workflow_outputs, configured_path("sample_builder", "report", default="results/source_builder/sample_source_report.tsv"))

# Stage 1 handoff outputs not always represented under outputs.qc in older configs.
add_path(workflow_outputs, configured_path("sequence_fetch_manifest", "manifest", default="results/qc/sequence_fetch_manifest.tsv"))
add_path(workflow_outputs, configured_path("sequence_fetch_manifest", "commands", default="results/qc/sequence_fetch_commands.sh"))
add_path(workflow_outputs, configured_path("sequence_fetch_manifest", "report", default="results/qc/sequence_fetch_report.tsv"))
add_path(workflow_outputs, configured_path("external_evidence_templates", "manifest", default="results/qc/external_evidence_template_manifest.tsv"))
add_path(workflow_outputs, configured_path("external_evidence_templates", "report", default="results/qc/external_evidence_template_report.tsv"))

# All configured workflow outputs.
collect_output_paths(WF.get("outputs", {}), workflow_outputs)

# Figure files are generated from outputs.figures.directory, but only the directory,
# manifest, and report are configurable.
figure_dir = configured_path("outputs", "figures", "directory", default="results/figures") or "results/figures"
for figure_id in [
    "figure_1_dataset_atlas",
    "figure_2_phage_pangenome",
    "figure_3_rbp_module_network",
    "figure_4_k_o_association",
    "figure_5_defense_counterdefense",
    "figure_6_novelty_prioritization",
]:
    workflow_outputs.append(f"{figure_dir}/{figure_id}_source.tsv")
    workflow_outputs.append(f"{figure_dir}/{figure_id}.svg")

WORKFLOW_OUTPUTS = unique(workflow_outputs)
WORKFLOW_INPUTS = unique([WORKFLOW_CONFIG, "scripts/run_workflow.py", *sorted(glob.glob("scripts/*.py")), *sorted(glob.glob("config/*.yaml")), *sorted(glob.glob("config/*.tsv"))])

rule all:
    input:
        WORKFLOW_OUTPUTS

rule run_configured_workflow:
    input:
        WORKFLOW_INPUTS
    output:
        WORKFLOW_OUTPUTS
    log:
        "logs/snakemake_run_workflow.log"
    shell:
        "{PYTHON} scripts/run_workflow.py --config {WORKFLOW_CONFIG} > {log} 2>&1"
