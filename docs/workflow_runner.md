# Config-Driven Workflow Runner

`scripts/run_workflow.py` executes the implemented workflow stages from `config/workflow.yaml`.
It is a lightweight runner for local validation and environments where Snakemake is not installed.
Snakemake remains the preferred orchestrator for larger production runs.

## Command

```bash
python scripts/run_workflow.py --config config/workflow.yaml
```

## Snakemake Entrypoint

The `Snakefile` delegates to the same config-driven direct runner instead of duplicating stage commands. This prevents drift between Snakemake and `scripts/run_workflow.py`.

```bash
snakemake -n
snakemake --cores 1
snakemake --config workflow_config=config/workflow.mock.yaml --cores 1
```

Use `--dry-run` to print the commands without executing them:

```bash
python scripts/run_workflow.py --config config/workflow.yaml --dry-run
```

Run only selected stages by name:

```bash
python scripts/run_workflow.py --config config/workflow.yaml --stages stage_1_manifest stage_2_dereplication
```

## Stage Names

- `stage_0_tool_audit` when `tool_audit.enabled: true`
- `stage_0_source_queries` when `source_queries.enabled: true`
- `stage_0_source_export_templates` when `source_export_templates.enabled: true`
- `stage_0_source_export_validation` when `source_export_validation.enabled: true`
- `stage_0_source_imports` when `source_imports.enabled: true`
- `stage_0_source_plan` when `source_plan.enabled: true`
- `stage_0_source_audit` when `source_audit.enabled: true`
- `stage_0_source_curation_tasks` when `source_curation_tasks.enabled: true`
- `stage_0_source_export_starter_kit` when `source_export_starter_kit.enabled: true`
- `stage_0_hypothesis_source_unlocks` when `hypothesis_source_unlocks.enabled: true`
- `stage_0_minimum_source_curation` when `minimum_source_curation.enabled: true`
- `stage_0_priority_source_preflight` when `priority_source_preflight.enabled: true`
- `stage_0_priority_source_collection_packet` when `priority_source_collection_packet.enabled: true`
- `stage_0_source_enablement` when `source_enablement.enabled: true`
- `stage_0_source_enablement_apply` when `source_enablement_apply.enabled: true`
- `stage_0_source_curation_packet` when `source_curation_packet.enabled: true`
- `stage_0_samples` when `sample_builder.enabled: true`
- `stage_0_source_overlap` when `source_overlap.enabled: true`
- `stage_0_sample_support` when `sample_support.enabled: true`
- `stage_0_sample_support_sources` when `sample_support_sources.enabled: true`
- `stage_0_sample_support_export_preflight` when `sample_support_export_preflight.enabled: true`
- `stage_0_source_readiness_dashboard` when `source_readiness_dashboard.enabled: true`
- `stage_0_source_curation_work_order` when `source_curation_work_order.enabled: true`
- `stage_0_source_work_order_packets` when `source_work_order_packets.enabled: true`
- `stage_0_source_curation_issue_bodies` when `source_curation_issue_bodies.enabled: true`
- `stage_0_source_work_order_acceptance` when `source_work_order_acceptance.enabled: true`
- `stage_0_source_post_acceptance` when `source_post_acceptance.enabled: true`
- `stage_0_sample_support_curation_packet` when `sample_support_curation_packet.enabled: true`
- `stage_1_manifest`
- `stage_1_sequence_acquisition`
- `stage_1_sequence_fetch_manifest` when `sequence_fetch_manifest.enabled: true`
- `stage_1_sequence_qc`
- `stage_1_external_evidence_plan`
- `stage_1_external_evidence_templates` when `external_evidence_templates.enabled: true`
- `stage_2_dereplication`
- `stage_3_annotations`
- `stage_4_rbp_depolymerase`
- `stage_5_host_features`
- `stage_6_defense_counterdefense`
- `stage_7_models`
- `stage_8_figures`
- `stage_9_source_export_validation_self_test`
- `stage_9_external_evidence_acceptance_self_test`
- `stage_9_rbp_external_evidence_normalization_self_test`
- `stage_9_defense_external_evidence_normalization_self_test`
- `stage_9_phage_host_assay_validation_self_test`
- `stage_9_phage_host_assay_validation`
- `stage_9_validation`
- `stage_10_study_readiness`
- `stage_11_hypothesis_traceability`
- `stage_11_claim_support_audit`
- `stage_11_goal_completion_audit`

## Real-Study Sample Builder

The default real workflow enables `sample_builder.enabled: true`. It reads enabled source manifests from `config/source_catalog.yaml`, writes the generated sample table to `results/source_builder/samples.tsv`, and uses that generated table for downstream manifest validation, sequence QC, validation, and readiness checks.

To advance from the scaffold to a populated study, first use `results/qc/source_query_plan.tsv` to create reviewed exports under `data/metadata/source_exports/`, import them into source manifests, set the selected source entries to `enabled: true`, and rerun:

```bash
python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_audit stage_0_samples stage_1_manifest stage_1_sequence_qc
```

`config/samples.tsv` remains in the repository as a static schema/template and fallback input, but it is not overwritten by the default real workflow.

## Optional Inputs

Optional upstream evidence tables are configured under `inputs`:

- `pairwise_similarity`
- `annotation_input`
- `domain_evidence`
- `structural_evidence`
- `kleborate_input`
- `kaptive_input`
- `host_defense_input`
- `phage_antidefense_input`
- `phage_host_assays`
- `phage_host_relationships`

Leave optional paths blank until the corresponding upstream tool output exists. If a path is supplied, the runner checks that it exists before starting the relevant stage.

## Outputs

All default outputs are under `results/`. The runner also writes:

- `results/validation/workflow_run_report.tsv`
- per-stage logs under `logs/`

The workflow-run report records each command, log path, status, return code, and expected outputs. When `stage_11_goal_completion_audit` is selected, the direct runner refreshes that audit once after writing the final current-run report so `results/validation/goal_completion_audit.tsv` does not read a stale report from an earlier partial run.

The runner regenerates `results/qc/source_query_plan.tsv` through `stage_0_source_queries`. This table records query intent, reviewed export paths, expected columns, and source rationale before source import.

The runner regenerates `results/qc/source_export_template_manifest.tsv` and header-only templates under `results/qc/source_export_templates/` through `stage_0_source_export_templates`. These templates help create reviewed exports without making empty files under `data/metadata/source_exports/`.

The runner validates reviewed exports through `stage_0_source_export_validation`, writing `results/qc/source_export_validation.tsv`. Missing exports remain warnings, while malformed populated exports block source import.

The runner also regenerates `results/qc/source_acquisition_plan.tsv` through `stage_0_source_plan`. This table is the handoff checklist for local metadata exports, source manifests, and catalog enablement.

The runner writes `results/qc/source_enablement_plan.tsv` through `stage_0_source_enablement`, then writes `results/qc/source_enablement_apply_report.tsv` through `stage_0_source_enablement_apply`. The apply stage is a dry-run in normal workflow execution; it records whether imports or catalog entries would be safe to enable without modifying YAML files.

After Stage 1 manifest generation, the runner writes `results/qc/sequence_acquisition_plan.tsv` through `stage_1_sequence_acquisition`. This table identifies records with existing FASTA files, records that can be fetched from accessions, and metadata-only records that need additional curation before production sequence QC.

The runner then writes `results/qc/sequence_fetch_manifest.tsv` and `results/qc/sequence_fetch_commands.sh` through `stage_1_sequence_fetch_manifest`. The commands file is a review artifact and is not executed by the workflow.

Stage 5 writes `results/host_features/phage_host_relationships.tsv` as the explicit non-assay relationship table and keeps `results/host_features/phage_host_links.tsv` only as a deprecated compatibility output for current downstream scaffold stages.

After sequence QC, the runner writes `results/qc/external_evidence_plan.tsv` through `stage_1_external_evidence_plan`. This table records whether pairwise similarity, annotation, RBP domain/structural, host-feature, and defense/counter-defense evidence are already configured or still need external tool runs.

The runner then writes `results/qc/external_evidence_template_manifest.tsv` and templates under `results/qc/external_evidence_templates/` through `stage_1_external_evidence_templates`. These are fillable schemas for production evidence TSVs and are not consumed as evidence unless configured under `inputs`.


## Populated Smoke Test

The repository includes a fixture-backed workflow config that first builds a sample table from `config/source_catalog.mock.yaml` and then exercises optional inputs without modifying `config/samples.tsv` or `results/` for the real study:

```bash
python scripts/run_workflow.py --config config/workflow.mock.yaml
```

This writes populated test outputs under `results/mock/` and stage logs under `logs/mock/`. It is intended to verify that optional pairwise similarity, annotation, domain, structural, host-feature, defense, and anti-defense evidence tables are wired correctly.

The runner writes `results/qc/source_readiness_dashboard.tsv` through `stage_0_source_readiness_dashboard`. This table is the ranked source-curation dashboard that combines export validation, enablement dry-run status, and sample-support preflight blockers.

The runner writes `results/qc/source_curation_work_order.tsv` through `stage_0_source_curation_work_order`. This table converts the source readiness dashboard into concrete reviewed-row curation tasks with required fields, minimum rows, and validation commands.

The runner writes `results/qc/source_work_order_packets/` through `stage_0_source_work_order_packets`. This directory contains one Markdown curation packet per source work order plus an index and manifest.

The runner writes `results/qc/source_curation_issue_manifest.tsv`, `results/qc/source_curation_issue_commands.tsv`, `results/qc/source_curation_issue_commands.sh`, and Markdown issue bodies under `results/qc/github_issue_bodies/` through `stage_0_source_curation_issue_bodies`. These files are GitHub-ready handoffs generated from current work orders; the shell commands are review artifacts and are not executed by the workflow.

The runner writes `results/qc/source_work_order_acceptance.tsv` through `stage_0_source_work_order_acceptance`. This table checks whether reviewed exports satisfy the current source curation work orders.

The runner writes `results/qc/source_post_acceptance_plan.tsv` through `stage_0_source_post_acceptance`. This table records the next command after source work-order acceptance, such as import enablement or sample-support reruns.

## Source Export Validation Self-Test

The runner writes `results/validation/source_export_validation_self_test.tsv` through `stage_9_source_export_validation_self_test`. This stage creates temporary reviewed-export examples and verifies that malformed year, GC, lifestyle, and identity fields are blocked before source import.


## Phage-Host Assay Validation

The runner writes `results/validation/phage_host_assay_validation.tsv`, `results/validation/phage_host_relationship_validation.tsv`, and `results/validation/phage_host_assay_validation_report.tsv` through `stage_9_phage_host_assay_validation`. Header-only assay and relationship tables pass as schema scaffolds, but they do not support host-range or productive-infection claims.

The runner also writes `results/validation/phage_host_assay_validation_self_test.tsv` through `stage_9_phage_host_assay_validation_self_test`. This self-test verifies valid positives, tested negatives, untested-negative contradictions, spot-only productive-infection claims, malformed EOP values, duplicates, unknown IDs, and invalid relationship types.

## Claim Support Audit

`stage_11_claim_support_audit` writes `results/validation/claim_support_audit.tsv` and `results/validation/claim_support_report.tsv`. These files join the claim ledger to validation, H1-H6 traceability, model summaries, and external evidence provenance so scaffold or mock-only outputs cannot be promoted to real biological claims.
