# Klebsiella Phage Comparative Genomics

This repository contains a reproducible comparative genomics workflow for testing whether Klebsiella phage host range is better predicted by receptor-binding/depolymerase module architecture plus defense/counter-defense compatibility than by phage taxonomy alone.

## Main Hypothesis

Klebsiella phage host range is shaped by two genomic filters:
1. receptor compatibility between phage RBP/depolymerase modules and host K/O surface antigens;
2. intracellular compatibility between host defense systems and phage anti-defense genes.

## Real Data Entry Point

Start with `config/source_queries.yaml` and `results/qc/source_query_plan.tsv` to identify the reviewed public-source exports needed for INPHARED, NCBI Virus/GenBank/RefSeq, literature-linked phages, prophages, optional metagenomic contigs, and host genomes. Save reviewed exports under `data/metadata/source_exports/`, import them into source manifests under `data/metadata/source_manifests/`, and enable selected entries in `config/source_catalog.yaml`. The default real workflow builds `results/source_builder/samples.tsv` from those manifests and uses that generated table for downstream analysis, leaving `config/samples.tsv` as a static template/fallback.

## Reviewer Handoff

For another AI or collaborator reviewing the repository, start with `docs/reviewer_handoff.md`. Reviewed source rows can be proposed with `.github/ISSUE_TEMPLATE/source-curation.yml`. It explains the expected real/mock workflow states, current biological blockers, validation commands, and claim boundaries. The machine-readable claim boundary is written to `results/validation/claim_support_audit.tsv` by the workflow.

## Workflow Stages

1. Dataset curation
2. Genome QC and dereplication
3. Phage annotation and pangenome
4. RBP/depolymerase discovery
5. Host K/O/ST/AMR/virulence annotation
6. Defense/counter-defense annotation
7. Statistical model comparison
8. Figure generation
9. Manuscript methods and interpretation

## Quick Start

Create the environment:

```bash
mamba env create -f environment.yml
mamba activate klebsiella-phage-cpg
```

Run the Snakemake entrypoint dry run. The Snakefile delegates to the same config-driven direct runner used below:

```bash
snakemake -n
```

Run the workflow directly from config when Snakemake is unavailable:

```bash
python scripts/run_workflow.py --config config/workflow.yaml
```

Run the fixture-backed workflow through Snakemake:

```bash
snakemake --config workflow_config=config/workflow.mock.yaml --cores 1
```

## Continuous Integration

After this repository is pushed to GitHub, `.github/workflows/ci.yml` runs a lightweight scaffold check on pushes and pull requests:

```bash
python -m py_compile scripts/*.py
python scripts/self_test_source_export_validation.py   --output results/validation/source_export_validation_self_test.tsv   --report-output results/validation/source_export_validation_self_test_report.tsv
python scripts/self_test_source_work_order_acceptance.py   --output results/validation/source_work_order_acceptance_self_test.tsv   --report-output results/validation/source_work_order_acceptance_self_test_report.tsv
python scripts/run_workflow.py --config config/workflow.mock.yaml
```

This CI proves that the pipeline scaffold, reviewed-export and source-intake regression tests, and mock H1-H6 workflow run from config. It does not prove that the real biological study is populated or manuscript-ready; real claims still require reviewed source exports and downstream evidence tables.

Audit workflow-core and planned external tool availability:

```bash
python scripts/audit_tool_availability.py \
  --tools-config config/tools.yaml \
  --availability-output results/qc/tool_availability.tsv \
  --report-output results/qc/tool_audit_report.tsv
```

Plan source queries and reviewed export handoffs:

```bash
python scripts/plan_source_queries.py   --queries-config config/source_queries.yaml   --catalog config/source_catalog.yaml   --imports-config config/source_imports.yaml   --plan-output results/qc/source_query_plan.tsv   --report-output results/qc/source_query_report.tsv
```

Create reviewed-export templates under `results/`:

```bash
python scripts/create_source_export_templates.py   --query-plan results/qc/source_query_plan.tsv   --templates-dir results/qc/source_export_templates   --manifest-output results/qc/source_export_template_manifest.tsv   --report-output results/qc/source_export_template_report.tsv
```

Create the source export column dictionary:

```bash
python scripts/create_source_export_dictionary.py \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --dictionary-output results/qc/source_export_column_dictionary.tsv \
  --report-output results/qc/source_export_column_dictionary_report.tsv
```

Generate reviewed-export query command sheets:

```bash
python scripts/create_source_query_commands.py \
  --source-query-plan results/qc/source_query_plan.tsv \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --commands-output results/qc/source_query_commands.tsv \
  --shell-output results/qc/source_query_commands.sh \
  --report-output results/qc/source_query_commands_report.tsv
```

Validate reviewed exports before import:

```bash
python scripts/validate_source_exports.py   --query-plan results/qc/source_query_plan.tsv   --template-manifest results/qc/source_export_template_manifest.tsv   --validation-output results/qc/source_export_validation.tsv   --report-output results/qc/source_export_validation_report.tsv   --root .
```

Run the validator regression self-test:

```bash
python scripts/self_test_source_export_validation.py \
  --output results/validation/source_export_validation_self_test.tsv \
  --report-output results/validation/source_export_validation_self_test_report.tsv
```

Import local public-source metadata exports into normalized source manifests:

```bash
python scripts/import_source_manifests.py \
  --config config/source_imports.yaml \
  --report-output results/qc/source_import_report.tsv
```

Plan source acquisition and enablement steps:

```bash
python scripts/plan_source_acquisition.py \
  --catalog config/source_catalog.yaml \
  --imports-config config/source_imports.yaml \
  --plan-output results/qc/source_acquisition_plan.tsv \
  --report-output results/qc/source_acquisition_report.tsv
```

Audit source manifest readiness:

```bash
python scripts/audit_source_catalog.py \
  --catalog config/source_catalog.yaml \
  --readiness-output results/qc/source_catalog_readiness.tsv \
  --report-output results/qc/source_catalog_audit_report.tsv
```

Summarize source curation tasks into one reviewed-export handoff table:

```bash
python scripts/summarize_source_curation_tasks.py \
  --source-query-plan results/qc/source_query_plan.tsv \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --export-validation results/qc/source_export_validation.tsv \
  --source-acquisition-plan results/qc/source_acquisition_plan.tsv \
  --source-readiness results/qc/source_catalog_readiness.tsv \
  --tasks-output results/qc/source_curation_tasks.tsv \
  --report-output results/qc/source_curation_tasks_report.tsv
```

Create source export starter files for A01:

```bash
python scripts/create_source_export_starter_kit.py \
  --source-curation-tasks results/qc/source_curation_tasks.tsv \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --column-dictionary results/qc/source_export_column_dictionary.tsv \
  --output-dir results/qc/source_export_starter_kit \
  --manifest-output results/qc/source_export_starter_kit_manifest.tsv \
  --report-output results/qc/source_export_starter_kit_report.tsv \
  --root .
```

Bootstrap fillable reviewed-export files at their configured curation paths:

```bash
python scripts/bootstrap_source_exports.py \
  --query-plan results/qc/source_query_plan.tsv \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --report-output results/qc/source_export_bootstrap_report.tsv \
  --root .
```


Map source curation state to H1-H6 unlock requirements:

```bash
python scripts/plan_hypothesis_source_unlocks.py \
  --source-curation-tasks results/qc/source_curation_tasks.tsv \
  --plan-output results/qc/hypothesis_source_unlock_plan.tsv \
  --matrix-output results/qc/hypothesis_source_unlock_matrix.tsv \
  --report-output results/qc/hypothesis_source_unlock_report.tsv
```

Rank minimum source exports for H1-H6:

```bash
python scripts/plan_minimum_source_curation.py \
  --hypothesis-source-unlocks results/qc/hypothesis_source_unlock_plan.tsv \
  --starter-kit-manifest results/qc/source_export_starter_kit_manifest.tsv \
  --source-plan-output results/qc/minimum_source_curation_plan.tsv \
  --hypothesis-plan-output results/qc/minimum_hypothesis_source_plan.tsv \
  --report-output results/qc/minimum_source_curation_report.tsv \
  --root .
```

Preflight the highest-priority reviewed exports:

```bash
python scripts/preflight_priority_source_exports.py \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --max-rank 2 \
  --preflight-output results/qc/priority_source_export_preflight.tsv \
  --issue-output results/qc/priority_source_export_preflight_issues.tsv \
  --report-output results/qc/priority_source_export_preflight_report.tsv \
  --root .
```

Create priority source collection packets:

```bash
python scripts/create_priority_source_collection_packet.py \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --source-query-commands results/qc/source_query_commands.tsv \
  --starter-kit-manifest results/qc/source_export_starter_kit_manifest.tsv \
  --preflight results/qc/priority_source_export_preflight.tsv \
  --output-dir results/qc/priority_source_collection_packet \
  --manifest-output results/qc/priority_source_collection_packet_manifest.tsv \
  --report-output results/qc/priority_source_collection_packet_report.tsv \
  --max-rank 2 \
  --root .
```

Plan source import/catalog enablement:

```bash
python scripts/plan_source_enablement.py \
  --source-acquisition-plan results/qc/source_acquisition_plan.tsv \
  --source-export-validation results/qc/source_export_validation.tsv \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --imports-config config/source_imports.yaml \
  --catalog config/source_catalog.yaml \
  --plan-output results/qc/source_enablement_plan.tsv \
  --report-output results/qc/source_enablement_report.tsv \
  --root .
```

Dry-run safe source import/catalog config enablement from the plan:

```bash
python scripts/apply_source_enablement.py \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --imports-config config/source_imports.yaml \
  --catalog config/source_catalog.yaml \
  --report-output results/qc/source_enablement_apply_report.tsv \
  --enable-imports \
  --root .
```


Render the source curation packet:

```bash
python scripts/create_source_curation_packet.py \
  --tasks results/qc/source_curation_tasks.tsv \
  --output-dir results/qc/source_curation_packet \
  --manifest-output results/qc/source_curation_packet_manifest.tsv \
  --report-output results/qc/source_curation_packet_report.tsv
```

Build the generated real-workflow sample table reproducibly from configured source manifests:

```bash
python scripts/build_samples_from_sources.py \
  --catalog config/source_catalog.yaml \
  --output-samples results/source_builder/samples.tsv \
  --report-output results/source_builder/sample_source_report.tsv
```

Audit source overlaps after sample generation:

```bash
python scripts/audit_source_overlaps.py \
  --samples results/source_builder/samples.tsv \
  --overlap-output results/qc/source_overlap_groups.tsv \
  --source-summary-output results/qc/source_overlap_summary.tsv \
  --report-output results/qc/source_overlap_report.tsv
```

Audit minimum sample support for H1-H6:

```bash
python scripts/audit_sample_support.py \
  --samples results/source_builder/samples.tsv \
  --thresholds config/thresholds.yaml \
  --hypothesis-output results/qc/sample_support_by_hypothesis.tsv \
  --summary-output results/qc/sample_support_summary.tsv \
  --report-output results/qc/sample_support_report.tsv
```

Map missing sample-support metrics to source exports:

```bash
python scripts/plan_sample_support_sources.py \
  --sample-support-summary results/qc/sample_support_summary.tsv \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --column-dictionary results/qc/source_export_column_dictionary.tsv \
  --bridge-output results/qc/sample_support_source_bridge.tsv \
  --report-output results/qc/sample_support_source_bridge_report.tsv
```

Preflight source exports against sample-support metrics:

```bash
python scripts/preflight_sample_support_exports.py \
  --bridge results/qc/sample_support_source_bridge.tsv \
  --preflight-output results/qc/sample_support_export_preflight.tsv \
  --report-output results/qc/sample_support_export_preflight_report.tsv \
  --root .
```

Build the ranked source readiness dashboard:

```bash
python scripts/build_source_readiness_dashboard.py \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --source-export-validation results/qc/source_export_validation.tsv \
  --source-enablement-plan results/qc/source_enablement_plan.tsv \
  --source-enablement-apply results/qc/source_enablement_apply_report.tsv \
  --sample-support-preflight results/qc/sample_support_export_preflight.tsv \
  --dashboard-output results/qc/source_readiness_dashboard.tsv \
  --report-output results/qc/source_readiness_dashboard_report.tsv
```

Create source curation work orders from the dashboard:

```bash
python scripts/build_source_curation_work_order.py \
  --dashboard results/qc/source_readiness_dashboard.tsv \
  --sample-support-summary results/qc/sample_support_summary.tsv \
  --work-order-output results/qc/source_curation_work_order.tsv \
  --report-output results/qc/source_curation_work_order_report.tsv
```

Render source work-order packets:

```bash
python scripts/create_source_work_order_packets.py \
  --work-orders results/qc/source_curation_work_order.tsv \
  --starter-kit-manifest results/qc/source_export_starter_kit_manifest.tsv \
  --dashboard results/qc/source_readiness_dashboard.tsv \
  --output-dir results/qc/source_work_order_packets \
  --manifest-output results/qc/source_work_order_packet_manifest.tsv \
  --report-output results/qc/source_work_order_packet_report.tsv \
  --root .
```

Check source work-order acceptance:

```bash
python scripts/check_source_work_order_acceptance.py \
  --work-orders results/qc/source_curation_work_order.tsv \
  --acceptance-output results/qc/source_work_order_acceptance.tsv \
  --report-output results/qc/source_work_order_acceptance_report.tsv \
  --root .
```

Plan post-acceptance source transitions:

```bash
python scripts/plan_source_post_acceptance.py \
  --acceptance results/qc/source_work_order_acceptance.tsv \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --enablement-apply results/qc/source_enablement_apply_report.tsv \
  --plan-output results/qc/source_post_acceptance_plan.tsv \
  --report-output results/qc/source_post_acceptance_report.tsv
```

Create sample-support curation packets:

```bash
python scripts/create_sample_support_curation_packet.py \
  --bridge results/qc/sample_support_source_bridge.tsv \
  --preflight results/qc/sample_support_export_preflight.tsv \
  --output-dir results/qc/sample_support_curation_packet \
  --manifest-output results/qc/sample_support_curation_packet_manifest.tsv \
  --report-output results/qc/sample_support_curation_packet_report.tsv \
  --root .
```

Populated source manifests must contain at least one identity column, by default `genome_id`, `accession`, or `raw_sequence_path`. Missing recommended metadata columns are reported as warnings and filled from source defaults or `NA` during early curation. External evidence TSVs are checked for minimum required columns before they are treated as ready.

Preview the config-driven commands without executing them:

```bash
python scripts/run_workflow.py --config config/workflow.yaml --dry-run
```

Run the populated smoke-test workflow with bundled fixtures:

```bash
python scripts/run_workflow.py --config config/workflow.mock.yaml
```

Run the seed real-data profile, which writes to `results/seed/` and keeps biological claims blocked:

```bash
python scripts/run_workflow.py --config config/workflow.seed.yaml
```

Inspect the production profile without requiring production evidence files yet:

```bash
python scripts/run_workflow.py --config config/workflow.production.yaml --dry-run
```

Run the implemented stages directly:

```bash
python scripts/00_build_phage_manifest.py \
  --input results/source_builder/samples.tsv \
  --manifest-output results/qc/phage_genome_manifest.tsv \
  --report-output results/qc/manifest_validation_report.tsv \
  --excluded-output results/qc/excluded_genomes.tsv
```

Plan local genome sequence acquisition:

```bash
python scripts/plan_sequence_acquisition.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --raw-directory data/raw/genomes \
  --plan-output results/qc/sequence_acquisition_plan.tsv \
  --report-output results/qc/sequence_acquisition_report.tsv \
  --root .
```

Create a review-only sequence fetch manifest:

```bash
python scripts/create_sequence_fetch_manifest.py \
  --sequence-plan results/qc/sequence_acquisition_plan.tsv \
  --manifest-output results/qc/sequence_fetch_manifest.tsv \
  --commands-output results/qc/sequence_fetch_commands.sh \
  --report-output results/qc/sequence_fetch_report.tsv \
  --root .
```

Validate reviewed raw FASTA acquisition checksums without tracking raw files:

```bash
python scripts/validate_sequence_acquisition_manifest.py \
  --manifest data/metadata/sequence_acquisition_manifest.tsv \
  --validation-output results/validation/sequence_acquisition_manifest_validation.tsv \
  --report-output results/validation/sequence_acquisition_manifest_validation_report.tsv \
  --root .
```

Audit source-manifest drift from authoritative source exports:

```bash
python scripts/audit_source_manifest_drift.py \
  --config config/source_imports.yaml \
  --drift-output results/qc/source_manifest_drift.tsv \
  --report-output results/qc/source_manifest_drift_report.tsv \
  --root .
```

Create external evidence templates after evidence planning:

```bash
python scripts/create_external_evidence_templates.py \
  --evidence-plan results/qc/external_evidence_plan.tsv \
  --templates-dir results/qc/external_evidence_templates \
  --manifest-output results/qc/external_evidence_template_manifest.tsv \
  --report-output results/qc/external_evidence_template_report.tsv \
  --root .
```

Map external evidence readiness to hypothesis unlock status:

```bash
python scripts/plan_external_evidence_unlocks.py \
  --evidence-plan results/qc/external_evidence_plan.tsv \
  --template-manifest results/qc/external_evidence_template_manifest.tsv \
  --unlock-output results/qc/external_evidence_unlock_plan.tsv \
  --matrix-output results/qc/external_evidence_unlock_matrix.tsv \
  --report-output results/qc/external_evidence_unlock_report.tsv \
  --root .
```

```bash
python scripts/00_qc_genome_sequences.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --thresholds config/thresholds.yaml \
  --qc-output results/qc/genome_sequence_qc.tsv \
  --report-output results/qc/genome_sequence_qc_report.tsv \
  --root .

python scripts/01_dereplicate_phages.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --thresholds config/thresholds.yaml \
  --sequence-qc results/qc/genome_sequence_qc.tsv \
  --ani-output results/clusters/phage_ani.tsv \
  --clusters-output results/clusters/phage_clusters.tsv \
  --representatives-output results/clusters/representatives.tsv \
  --report-output results/clusters/dereplication_report.tsv

python scripts/02_build_annotation_tables.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --annotations-output results/annotations/phage_annotations.tsv \
  --gene-clusters-output results/annotations/gene_clusters.tsv \
  --pangenome-output results/annotations/pangenome_matrix.tsv \
  --report-output results/annotations/annotation_report.tsv

python scripts/03_predict_rbps_depolymerases.py \
  --annotations results/annotations/phage_annotations.tsv \
  --gene-clusters results/annotations/gene_clusters.tsv \
  --thresholds config/thresholds.yaml \
  --candidates-output results/rbp_depolymerase/candidates.tsv \
  --domain-architectures-output results/rbp_depolymerase/domain_architectures.tsv \
  --module-clusters-output results/rbp_depolymerase/module_clusters.tsv \
  --novel-candidates-output results/rbp_depolymerase/novel_candidates.tsv \
  --report-output results/rbp_depolymerase/rbp_depolymerase_report.tsv

python scripts/04_integrate_host_features.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --host-metadata-output results/host_features/host_metadata.tsv \
  --kaptive-output results/host_features/kaptive_results.tsv \
  --kleborate-output results/host_features/kleborate_results.tsv \
  --phage-host-links-output results/host_features/phage_host_links.tsv \
  --phage-host-relationships-output results/host_features/phage_host_relationships.tsv \
  --report-output results/host_features/host_feature_report.tsv

python scripts/05_integrate_defense_counterdefense.py \
  --host-metadata results/host_features/host_metadata.tsv \
  --phage-host-links results/host_features/phage_host_links.tsv \
  --annotations results/annotations/phage_annotations.tsv \
  --host-defense-output results/defense_systems/host_defense_systems.tsv \
  --phage-antidefense-output results/defense_systems/phage_antidefense_candidates.tsv \
  --compatibility-output results/defense_systems/compatibility_features.tsv \
  --report-output results/defense_systems/defense_counterdefense_report.tsv

python scripts/06_compare_feature_models.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --rbp-candidates results/rbp_depolymerase/candidates.tsv \
  --phage-host-links results/host_features/phage_host_links.tsv \
  --compatibility-features results/defense_systems/compatibility_features.tsv \
  --model-comparison-output results/models/model_comparison.tsv \
  --feature-importance-output results/models/feature_importance.tsv \
  --prediction-errors-output results/models/prediction_errors.tsv \
  --hypothesis-summary-output results/models/hypothesis_summary.tsv \
  --report-output results/models/model_report.tsv

python scripts/07_generate_figure_sources.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --gene-clusters results/annotations/gene_clusters.tsv \
  --pangenome results/annotations/pangenome_matrix.tsv \
  --rbp-candidates results/rbp_depolymerase/candidates.tsv \
  --rbp-modules results/rbp_depolymerase/module_clusters.tsv \
  --novel-candidates results/rbp_depolymerase/novel_candidates.tsv \
  --host-metadata results/host_features/host_metadata.tsv \
  --phage-host-links results/host_features/phage_host_links.tsv \
  --host-defense results/defense_systems/host_defense_systems.tsv \
  --phage-antidefense results/defense_systems/phage_antidefense_candidates.tsv \
  --compatibility results/defense_systems/compatibility_features.tsv \
  --model-comparison results/models/model_comparison.tsv \
  --feature-importance results/models/feature_importance.tsv \
  --output-dir results/figures \
  --manifest-output results/figures/figure_manifest.tsv \
  --report-output results/figures/figure_generation_report.tsv

python scripts/08_validate_workflow.py \
  --root . \
  --schema-output results/validation/schema_validation.tsv \
  --hypothesis-output results/validation/hypothesis_coverage.tsv \
  --inventory-output results/validation/output_inventory.tsv \
  --report-output results/validation/workflow_validation_report.tsv

python scripts/09_audit_study_readiness.py \
  --root . \
  --results-dir results \
  --samples results/source_builder/samples.tsv \
  --readiness-output results/validation/study_readiness.tsv \
  --report-output results/validation/study_readiness_report.tsv

python scripts/10_plan_readiness_actions.py \
  --root . \
  --results-dir results \
  --readiness results/validation/study_readiness.tsv \
  --source-curation-tasks results/qc/source_curation_tasks.tsv \
  --hypothesis-source-unlocks results/qc/hypothesis_source_unlock_plan.tsv \
  --sequence-fetch-manifest results/qc/sequence_fetch_manifest.tsv \
  --external-evidence-unlocks results/qc/external_evidence_unlock_plan.tsv \
  --action-output results/validation/readiness_action_plan.tsv \
  --report-output results/validation/readiness_action_report.tsv

python scripts/12_build_hypothesis_traceability.py \
  --source-plan results/qc/minimum_hypothesis_source_plan.tsv \
  --evidence-plan results/qc/external_evidence_unlock_plan.tsv \
  --sample-support results/qc/sample_support_by_hypothesis.tsv \
  --hypothesis-summary results/models/hypothesis_summary.tsv \
  --hypothesis-coverage results/validation/hypothesis_coverage.tsv \
  --figure-manifest results/figures/figure_manifest.tsv \
  --readiness results/validation/study_readiness.tsv \
  --trace-output results/validation/hypothesis_traceability.tsv \
  --report-output results/validation/hypothesis_traceability_report.tsv

python scripts/11_audit_goal_completion.py \
  --root . \
  --results-dir results \
  --audit-output results/validation/goal_completion_audit.tsv \
  --report-output results/validation/goal_completion_report.tsv
```

Run the workflow:

```bash
snakemake --cores 1
```

## Key Outputs

- results/qc/source_query_plan.tsv
- results/qc/source_query_report.tsv
- results/qc/source_query_commands.tsv
- results/qc/source_query_commands.sh
- results/qc/source_query_commands_report.tsv
- results/qc/source_export_template_manifest.tsv
- results/qc/source_export_template_report.tsv
- results/qc/source_export_column_dictionary.tsv
- results/qc/source_export_column_dictionary_report.tsv
- results/qc/source_export_templates/
- results/qc/source_export_validation.tsv
- results/qc/source_export_validation_report.tsv
- results/qc/source_acquisition_plan.tsv
- results/qc/source_acquisition_report.tsv
- results/qc/source_curation_tasks.tsv
- results/qc/source_curation_tasks_report.tsv
- results/qc/source_export_starter_kit/
- results/qc/source_export_starter_kit_manifest.tsv
- results/qc/source_export_starter_kit_report.tsv
- results/qc/hypothesis_source_unlock_plan.tsv
- results/qc/hypothesis_source_unlock_matrix.tsv
- results/qc/hypothesis_source_unlock_report.tsv
- results/qc/minimum_source_curation_plan.tsv
- results/qc/minimum_hypothesis_source_plan.tsv
- results/qc/minimum_source_curation_report.tsv
- results/qc/priority_source_export_preflight.tsv
- results/qc/priority_source_export_preflight_issues.tsv
- results/qc/priority_source_export_preflight_report.tsv
- results/qc/priority_source_collection_packet/
- results/qc/priority_source_collection_packet_manifest.tsv
- results/qc/priority_source_collection_packet_report.tsv
- results/qc/source_enablement_plan.tsv
- results/qc/source_enablement_report.tsv
- results/qc/source_enablement_apply_report.tsv
- results/qc/source_curation_packet/
- results/qc/source_curation_packet_manifest.tsv
- results/qc/source_curation_packet_report.tsv
- results/qc/source_overlap_groups.tsv
- results/qc/source_overlap_summary.tsv
- results/qc/source_overlap_report.tsv
- results/qc/sample_support_by_hypothesis.tsv
- results/qc/sample_support_summary.tsv
- results/qc/sample_support_report.tsv
- results/qc/sample_support_source_bridge.tsv
- results/qc/sample_support_source_bridge_report.tsv
- results/qc/sample_support_export_preflight.tsv
- results/qc/sample_support_export_preflight_report.tsv
- results/qc/source_readiness_dashboard.tsv
- results/qc/source_readiness_dashboard_report.tsv
- results/qc/source_curation_work_order.tsv
- results/qc/source_curation_work_order_report.tsv
- results/qc/source_work_order_packets/
- results/qc/source_work_order_packet_manifest.tsv
- results/qc/source_work_order_packet_report.tsv
- results/qc/source_work_order_acceptance.tsv
- results/qc/source_work_order_acceptance_report.tsv
- results/qc/source_post_acceptance_plan.tsv
- results/qc/source_post_acceptance_report.tsv
- results/qc/sample_support_curation_packet/
- results/qc/sample_support_curation_packet_manifest.tsv
- results/qc/sample_support_curation_packet_report.tsv
- results/qc/tool_availability.tsv
- results/qc/tool_audit_report.tsv
- results/qc/phage_genome_manifest.tsv
- results/qc/manifest_validation_report.tsv
- results/qc/excluded_genomes.tsv
- results/qc/sequence_acquisition_plan.tsv
- results/qc/sequence_acquisition_report.tsv
- results/qc/sequence_fetch_manifest.tsv
- results/qc/sequence_fetch_commands.sh
- results/qc/sequence_fetch_report.tsv
- results/qc/genome_sequence_qc.tsv
- results/qc/genome_sequence_qc_report.tsv
- results/qc/external_evidence_plan.tsv
- results/qc/external_evidence_report.tsv
- results/qc/external_evidence_unlock_plan.tsv
- results/qc/external_evidence_unlock_matrix.tsv
- results/qc/external_evidence_unlock_report.tsv
- results/qc/external_evidence_template_manifest.tsv
- results/qc/external_evidence_template_report.tsv
- results/qc/external_evidence_templates/
- results/clusters/phage_ani.tsv
- results/clusters/phage_clusters.tsv
- results/clusters/representatives.tsv
- results/clusters/dereplication_report.tsv
- results/annotations/phage_annotations.tsv
- results/annotations/gene_clusters.tsv
- results/annotations/pangenome_matrix.tsv
- results/annotations/annotation_report.tsv
- results/rbp_depolymerase/candidates.tsv
- results/rbp_depolymerase/domain_architectures.tsv
- results/rbp_depolymerase/module_clusters.tsv
- results/rbp_depolymerase/novel_candidates.tsv
- results/rbp_depolymerase/rbp_depolymerase_report.tsv
- results/host_features/host_metadata.tsv
- results/host_features/kaptive_results.tsv
- results/host_features/kleborate_results.tsv
- results/host_features/phage_host_relationships.tsv
- results/host_features/phage_host_links.tsv
- results/host_features/host_feature_report.tsv
- results/defense_systems/host_defense_systems.tsv
- results/defense_systems/phage_antidefense_candidates.tsv
- results/defense_systems/compatibility_features.tsv
- results/defense_systems/defense_counterdefense_report.tsv
- results/models/model_comparison.tsv
- results/models/feature_importance.tsv
- results/models/prediction_errors.tsv
- results/models/hypothesis_summary.tsv
- results/models/model_report.tsv
- results/figures/figure_manifest.tsv
- results/figures/figure_generation_report.tsv
- results/figures/figure_1_dataset_atlas_source.tsv
- results/figures/figure_2_phage_pangenome_source.tsv
- results/figures/figure_3_rbp_module_network_source.tsv
- results/figures/figure_4_k_o_association_source.tsv
- results/figures/figure_5_defense_counterdefense_source.tsv
- results/figures/figure_6_novelty_prioritization_source.tsv
- results/validation/schema_validation.tsv
- results/validation/hypothesis_coverage.tsv
- results/validation/output_inventory.tsv
- results/validation/workflow_validation_report.tsv
- results/validation/study_readiness.tsv
- results/validation/study_readiness_report.tsv
- results/validation/readiness_action_plan.tsv
- results/validation/readiness_action_report.tsv
- results/validation/goal_completion_audit.tsv
- results/validation/goal_completion_report.tsv
- results/validation/hypothesis_traceability.tsv
- results/validation/hypothesis_traceability_report.tsv

## Documentation

- docs/methods.md
- docs/hypotheses.md
- docs/metadata_schema.md
- docs/tool_availability_schema.md
- docs/genome_sequence_qc_schema.md
- docs/source_catalog_schema.md
- docs/source_catalog_readiness_schema.md
- docs/source_manifest_import_schema.md
- docs/source_export_starter_kit_schema.md
- docs/source_export_bootstrap_schema.md
- docs/minimum_source_curation_schema.md
- docs/source_enablement_schema.md
- docs/source_enablement_apply_schema.md
- docs/source_readiness_dashboard_schema.md
- docs/source_curation_work_order_schema.md
- docs/source_work_order_packet_schema.md
- docs/source_work_order_acceptance_schema.md
- docs/source_post_acceptance_schema.md
- docs/priority_source_preflight_schema.md
- docs/priority_source_collection_packet_schema.md
- docs/source_overlap_schema.md
- docs/sample_support_schema.md
- docs/sample_support_source_bridge_schema.md
- docs/sample_support_export_preflight_schema.md
- docs/sample_support_curation_packet_schema.md
- docs/dereplication_schema.md
- docs/annotation_schema.md
- docs/rbp_depolymerase_schema.md
- docs/host_feature_schema.md
- docs/defense_counterdefense_schema.md
- docs/modeling_schema.md
- docs/figure_generation_schema.md
- docs/workflow_validation_schema.md
- docs/workflow_runner.md
- docs/sequence_acquisition_manifest_schema.md
- docs/source_manifest_drift_schema.md
- docs/study_readiness_schema.md
- docs/readiness_action_plan_schema.md
- docs/goal_completion_audit_schema.md
- docs/hypothesis_traceability_schema.md
- docs/figure_plan.md
- docs/limitations.md
- docs/claim_ledger.md

## Current Status

The repository currently implements Stage 1 metadata validation, source/sequence/external-evidence planning, checksum-backed raw acquisition manifests, source-manifest drift auditing, source export starter-kit generation, minimum source curation prioritization, priority source preflight, priority collection packets, source enablement planning, source enablement dry-run auditing, source readiness dashboarding, source curation work-order generation, source work-order packet rendering, source work-order acceptance checks, post-acceptance source transition planning, and source overlap auditing, Stage 2 dereplication/similarity schemas, Stage 3 annotation/pangenome table construction, Stage 4 RBP/depolymerase candidate prioritization, Stage 5 host-feature integration, Stage 6 defense/counter-defense feature integration, Stage 7 model-comparison scaffolding, Stage 8 figure source/draft SVG generation, Stage 9 workflow validation/audit reporting, and a direct config-driven workflow runner for environments without Snakemake. The study readiness audit now reports source, sample-support, sequence, and evidence acquisition status before downstream biological outputs. The readiness action plan prioritizes the highest-ranked missing source exports from the minimum source curation plan before downstream sequence and evidence steps.
