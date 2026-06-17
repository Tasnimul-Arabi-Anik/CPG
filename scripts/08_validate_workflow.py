#!/usr/bin/env python3
"""Validate workflow outputs, schemas, docs, figures, and hypothesis coverage."""

from __future__ import annotations

import argparse
import csv
import py_compile
import shutil
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = ["severity", "item", "status", "message"]
SCHEMA_COLUMNS = [
    "stage",
    "path",
    "exists",
    "row_count",
    "required_columns_present",
    "missing_columns",
    "status",
    "notes",
]
HYPOTHESIS_COLUMNS = [
    "hypothesis",
    "required_test",
    "evidence_path",
    "matching_rows",
    "ok_rows",
    "limited_rows",
    "status",
    "notes",
]
INVENTORY_COLUMNS = ["path", "exists", "size_bytes", "row_count", "status", "notes"]

REQUIRED_OUTPUTS = [
    ("stage_0_tool_availability", "results/qc/tool_availability.tsv", ["tool_id", "command", "required_for_current_workflow", "availability_status"]),
    ("stage_0_tool_audit_report", "results/qc/tool_audit_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_query_plan", "results/qc/source_query_plan.tsv", ["query_id", "source_id", "target_database", "query_string", "expected_export_path", "query_status", "next_action"]),
    ("stage_0_source_query_report", "results/qc/source_query_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_query_commands", "results/qc/source_query_commands.tsv", ["query_id", "source_id", "target_database", "expected_export_path", "requires_network", "review_mode", "command_text"]),
    ("stage_0_source_query_commands_report", "results/qc/source_query_commands_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_export_template_manifest", "results/qc/source_export_template_manifest.tsv", ["query_id", "source_id", "template_path", "expected_export_path", "header_columns", "identity_columns_required", "template_status", "next_action"]),
    ("stage_0_source_export_template_report", "results/qc/source_export_template_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_export_dictionary", "results/qc/source_export_column_dictionary.tsv", ["source_id", "query_id", "record_layer", "column_name", "column_role", "description", "expected_format", "missing_value_policy"]),
    ("stage_0_source_export_dictionary_report", "results/qc/source_export_column_dictionary_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_export_validation", "results/qc/source_export_validation.tsv", ["query_id", "source_id", "expected_export_path", "export_exists", "export_row_count", "validation_status", "blocking_issue", "next_action"]),
    ("stage_0_source_export_validation_report", "results/qc/source_export_validation_report.tsv", ["severity", "item", "message"]),
    ("stage_9_source_export_validation_self_test", "results/validation/source_export_validation_self_test.tsv", ["test_id", "scenario", "expected_status", "observed_status", "status"]),
    ("stage_9_source_export_validation_self_test_report", "results/validation/source_export_validation_self_test_report.tsv", ["severity", "item", "message"]),
    ("stage_9_external_evidence_acceptance_self_test", "results/validation/external_evidence_acceptance_self_test.tsv", ["test_id", "scenario", "expected_acceptance_status", "observed_acceptance_status", "status"]),
    ("stage_9_external_evidence_acceptance_self_test_report", "results/validation/external_evidence_acceptance_self_test_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_import_report", "results/qc/source_import_report.tsv", ["severity", "import_id", "input_path", "output_path", "message"]),
    ("stage_0_source_acquisition_plan", "results/qc/source_acquisition_plan.tsv", ["source_id", "record_layer", "manifest_path", "manifest_row_count", "import_input_row_count", "import_input_identity_columns", "import_input_filter_pass_count", "acquisition_status", "next_action"]),
    ("stage_0_source_acquisition_report", "results/qc/source_acquisition_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_readiness", "results/qc/source_catalog_readiness.tsv", ["source_id", "path", "enabled", "row_count", "ready_status", "suggested_action"]),
    ("stage_0_source_audit_report", "results/qc/source_catalog_audit_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_curation_tasks", "results/qc/source_curation_tasks.tsv", ["source_id", "query_id", "expected_export_path", "curation_status", "blocking_for_real_study", "next_action", "command_hint"]),
    ("stage_0_source_curation_tasks_report", "results/qc/source_curation_tasks_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_export_starter_kit_manifest", "results/qc/source_export_starter_kit_manifest.tsv", ["source_id", "starter_readme_path", "starter_template_path", "expected_export_path", "validation_command"]),
    ("stage_0_source_export_starter_kit_report", "results/qc/source_export_starter_kit_report.tsv", ["severity", "item", "message"]),
    ("stage_0_hypothesis_source_unlock_plan", "results/qc/hypothesis_source_unlock_plan.tsv", ["hypothesis", "required_source_ids", "blocking_required_sources", "minimum_unlock_status", "next_action"]),
    ("stage_0_hypothesis_source_unlock_matrix", "results/qc/hypothesis_source_unlock_matrix.tsv", ["hypothesis", "source_id", "source_role", "curation_status", "expected_export_path"]),
    ("stage_0_hypothesis_source_unlock_report", "results/qc/hypothesis_source_unlock_report.tsv", ["severity", "item", "message"]),
    ("stage_0_minimum_source_curation_plan", "results/qc/minimum_source_curation_plan.tsv", ["source_id", "recommended_rank", "required_for_hypotheses", "expected_export_path", "recommended_action"]),
    ("stage_0_minimum_hypothesis_source_plan", "results/qc/minimum_hypothesis_source_plan.tsv", ["hypothesis", "minimum_required_sources", "missing_required_sources", "minimum_source_count", "expected_export_paths"]),
    ("stage_0_minimum_source_curation_report", "results/qc/minimum_source_curation_report.tsv", ["severity", "item", "message"]),
    ("stage_0_priority_source_preflight", "results/qc/priority_source_export_preflight.tsv", ["source_id", "recommended_rank", "expected_export_path", "preflight_status", "blocking_issue_count"]),
    ("stage_0_priority_source_preflight_issues", "results/qc/priority_source_export_preflight_issues.tsv", ["source_id", "row_number", "issue_severity", "issue_code", "field"]),
    ("stage_0_priority_source_preflight_report", "results/qc/priority_source_export_preflight_report.tsv", ["severity", "item", "message"]),
    ("stage_0_priority_source_collection_packet_manifest", "results/qc/priority_source_collection_packet_manifest.tsv", ["source_id", "recommended_rank", "packet_path", "expected_export_path", "preflight_status"]),
    ("stage_0_priority_source_collection_packet_report", "results/qc/priority_source_collection_packet_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_enablement_plan", "results/qc/source_enablement_plan.tsv", ["source_id", "enablement_status", "config_actions_required", "validation_command", "next_action"]),
    ("stage_0_source_enablement_report", "results/qc/source_enablement_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_enablement_apply_report", "results/qc/source_enablement_apply_report.tsv", ["source_id", "enablement_status", "action_status", "message"]),
    ("stage_0_source_curation_packet_manifest", "results/qc/source_curation_packet_manifest.tsv", ["source_id", "packet_path", "expected_export_path", "curation_status", "blocking_for_real_study", "next_action"]),
    ("stage_0_source_curation_packet_report", "results/qc/source_curation_packet_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_overlap_groups", "results/qc/source_overlap_groups.tsv", ["overlap_key_type", "overlap_key", "record_count", "sources", "overlap_status"]),
    ("stage_0_source_overlap_summary", "results/qc/source_overlap_summary.tsv", ["source", "record_count", "record_types", "duplicate_key_count"]),
    ("stage_0_source_overlap_report", "results/qc/source_overlap_report.tsv", ["severity", "item", "message"]),
    ("stage_0_sample_support_hypotheses", "results/qc/sample_support_by_hypothesis.tsv", ["hypothesis", "support_status", "sample_rows", "missing_support"]),
    ("stage_0_sample_support_summary", "results/qc/sample_support_summary.tsv", ["metric", "value", "threshold", "status"]),
    ("stage_0_sample_support_report", "results/qc/sample_support_report.tsv", ["severity", "item", "message"]),
    ("stage_0_sample_support_source_bridge", "results/qc/sample_support_source_bridge.tsv", ["metric", "source_id", "expected_export_path", "fields_to_populate"]),
    ("stage_0_sample_support_source_bridge_report", "results/qc/sample_support_source_bridge_report.tsv", ["severity", "item", "message"]),
    ("stage_0_sample_support_export_preflight", "results/qc/sample_support_export_preflight.tsv", ["metric", "source_id", "preflight_status", "blocking_issue"]),
    ("stage_0_sample_support_export_preflight_report", "results/qc/sample_support_export_preflight_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_readiness_dashboard", "results/qc/source_readiness_dashboard.tsv", ["source_id", "recommended_rank", "curation_priority", "next_action"]),
    ("stage_0_source_readiness_dashboard_report", "results/qc/source_readiness_dashboard_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_curation_work_order", "results/qc/source_curation_work_order.tsv", ["work_order_id", "source_id", "minimum_rows_to_add", "required_fields", "validation_command"]),
    ("stage_0_source_curation_work_order_report", "results/qc/source_curation_work_order_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_work_order_packet_manifest", "results/qc/source_work_order_packet_manifest.tsv", ["work_order_id", "source_id", "packet_path", "expected_export_path"]),
    ("stage_0_source_work_order_packet_report", "results/qc/source_work_order_packet_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_curation_issue_manifest", "results/qc/source_curation_issue_manifest.tsv", ["work_order_id", "source_id", "issue_title", "issue_body_path", "labels"]),
    ("stage_0_source_curation_issue_commands", "results/qc/source_curation_issue_commands.tsv", ["work_order_id", "source_id", "issue_title", "issue_body_path", "labels", "gh_command"]),
    ("stage_0_source_curation_issue_report", "results/qc/source_curation_issue_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_work_order_acceptance", "results/qc/source_work_order_acceptance.tsv", ["work_order_id", "source_id", "acceptance_status", "blocking_issue"]),
    ("stage_0_source_work_order_acceptance_report", "results/qc/source_work_order_acceptance_report.tsv", ["severity", "item", "message"]),
    ("stage_0_source_post_acceptance_plan", "results/qc/source_post_acceptance_plan.tsv", ["source_id", "transition_status", "next_command", "next_action"]),
    ("stage_0_source_post_acceptance_report", "results/qc/source_post_acceptance_report.tsv", ["severity", "item", "message"]),
    ("stage_0_sample_support_curation_packet_manifest", "results/qc/sample_support_curation_packet_manifest.tsv", ["source_id", "packet_path", "blocked_metrics", "fields_to_populate"]),
    ("stage_0_sample_support_curation_packet_report", "results/qc/sample_support_curation_packet_report.tsv", ["severity", "item", "message"]),
    ("stage_1_manifest", "results/qc/phage_genome_manifest.tsv", ["record_type", "genome_id", "validation_status"]),
    ("stage_1_report", "results/qc/manifest_validation_report.tsv", ["genome_id", "record_type", "severity", "field", "message"]),
    ("stage_1_sequence_acquisition_plan", "results/qc/sequence_acquisition_plan.tsv", ["genome_id", "record_type", "accession", "raw_sequence_path", "expected_sequence_path", "acquisition_status", "retrieval_method"]),
    ("stage_1_sequence_acquisition_report", "results/qc/sequence_acquisition_report.tsv", ["severity", "item", "message"]),
    ("stage_1_sequence_fetch_manifest", "results/qc/sequence_fetch_manifest.tsv", ["command_id", "genome_id", "acquisition_status", "command_class", "requires_network", "ready_to_run", "next_action"]),
    ("stage_1_sequence_fetch_report", "results/qc/sequence_fetch_report.tsv", ["severity", "item", "message"]),
    ("stage_1_sequence_fetch_review_packet_report", "results/qc/sequence_fetch_review_packet_report.tsv", ["severity", "item", "message"]),
    ("stage_1_sequence_qc", "results/qc/genome_sequence_qc.tsv", ["genome_id", "raw_sequence_path", "sequence_qc_status", "total_length_bp", "gc_percent_observed", "passes_sequence_qc"]),
    ("stage_1_external_evidence_plan", "results/qc/external_evidence_plan.tsv", ["evidence_id", "analysis_layer", "optional_input_key", "configured_input_path", "configured_input_schema_status", "configured_input_missing_columns", "eligible_sequence_records", "tool_status", "evidence_status", "evidence_origin", "real_claim_use_status", "next_action"]),
    ("stage_1_external_evidence_report", "results/qc/external_evidence_report.tsv", ["severity", "item", "message"]),
    ("stage_1_external_evidence_template_manifest", "results/qc/external_evidence_template_manifest.tsv", ["evidence_id", "optional_input_key", "template_path", "required_columns_spec", "header_columns", "template_status", "next_action"]),
    ("stage_1_external_evidence_template_report", "results/qc/external_evidence_template_report.tsv", ["severity", "item", "message"]),
    ("stage_1_external_evidence_run_packet_manifest", "results/qc/external_evidence_run_packet_manifest.tsv", ["evidence_id", "packet_path", "template_path", "action_status", "next_action"]),
    ("stage_1_external_evidence_run_packet_report", "results/qc/external_evidence_run_packet_report.tsv", ["severity", "item", "message"]),
    ("stage_1_external_evidence_acceptance", "results/qc/external_evidence_acceptance.tsv", ["evidence_id", "acceptance_status", "blocking_issue", "provenance_lint", "next_action"]),
    ("stage_1_external_evidence_acceptance_report", "results/qc/external_evidence_acceptance_report.tsv", ["severity", "item", "message"]),
    ("stage_1_external_evidence_unlock_plan", "results/qc/external_evidence_unlock_plan.tsv", ["hypothesis", "required_evidence_ids", "blocking_required_evidence", "minimum_unlock_status", "next_action"]),
    ("stage_1_external_evidence_unlock_matrix", "results/qc/external_evidence_unlock_matrix.tsv", ["hypothesis", "evidence_id", "analysis_layer", "evidence_status", "template_path"]),
    ("stage_1_external_evidence_unlock_report", "results/qc/external_evidence_unlock_report.tsv", ["severity", "item", "message"]),
    ("stage_1_production_evidence_handoff_report", "results/qc/production_evidence_handoff_report.tsv", ["severity", "item", "message"]),
    ("stage_1_pipeline_efficiency_audit", "results/validation/pipeline_efficiency_audit.tsv", ["check_id", "area", "reviewer_question", "status", "blocking_for_efficiency"]),
    ("stage_1_pipeline_efficiency_report", "results/validation/pipeline_efficiency_report.tsv", ["severity", "item", "message"]),
    ("stage_1_sequence_qc_report", "results/qc/genome_sequence_qc_report.tsv", ["genome_id", "record_type", "severity", "field", "message"]),
    ("stage_2_clusters", "results/clusters/phage_clusters.tsv", ["genome_id", "record_type", "cluster_id", "representative_id", "cluster_size", "sequence_qc_status", "passes_sequence_qc"]),
    ("stage_2_representatives", "results/clusters/representatives.tsv", ["cluster_id", "representative_id", "cluster_size", "member_genome_ids", "representative_sequence_qc_status"]),
    ("stage_3_annotations", "results/annotations/phage_annotations.tsv", ["genome_id", "annotation_gene_id", "product", "gene_cluster_id", "module_hint"]),
    ("stage_3_gene_clusters", "results/annotations/gene_clusters.tsv", ["gene_cluster_id", "gene_cluster_key", "gene_count", "genome_count", "module_hint"]),
    ("stage_3_pangenome", "results/annotations/pangenome_matrix.tsv", ["gene_cluster_id", "gene_cluster_key", "genome_count", "gene_count"]),
    ("stage_3_external_evidence_protein_manifest", "results/qc/external_evidence_proteins/protein_export_manifest.tsv", ["annotation_gene_id", "genome_id", "candidate_priority", "candidate_reason", "sequence_source"]),
    ("stage_3_external_evidence_protein_report", "results/qc/external_evidence_proteins/protein_export_report.tsv", ["severity", "item", "message"]),
    ("stage_3_phage_antidefense_handoff", "results/qc/phage_antidefense_screening_handoff.tsv", ["annotation_gene_id", "phage_genome_id", "screening_priority", "protein_fasta", "run_status"]),
    ("stage_3_phage_antidefense_handoff_report", "results/qc/phage_antidefense_screening_handoff_report.tsv", ["severity", "item", "message"]),
    ("stage_4_rbp_candidates", "results/rbp_depolymerase/candidates.tsv", ["candidate_id", "genome_id", "annotation_gene_id", "module_cluster_id", "confidence_score", "novelty_tier"]),
    ("stage_4_rbp_modules", "results/rbp_depolymerase/module_clusters.tsv", ["module_cluster_id", "candidate_count", "genome_count", "predicted_enzyme_classes"]),
    ("stage_5_host_metadata", "results/host_features/host_metadata.tsv", ["host_genome_id", "host_record_type", "K_type", "O_type", "ST"]),
    ("stage_5_phage_host_links", "results/host_features/phage_host_links.tsv", ["phage_genome_id", "host_genome_id", "host_link_status", "K_type", "O_type", "ST"]),
    ("stage_5_host_defense_handoff", "results/qc/host_defense_run_handoff.tsv", ["host_genome_id", "raw_sequence_path", "raw_sequence_exists", "defensefinder_command", "padloc_command", "run_status"]),
    ("stage_5_host_defense_handoff_report", "results/qc/host_defense_run_handoff_report.tsv", ["severity", "item", "message"]),
    ("stage_6_host_defense", "results/defense_systems/host_defense_systems.tsv", ["host_genome_id", "defense_system", "defense_type", "evidence_source"]),
    ("stage_6_phage_antidefense", "results/defense_systems/phage_antidefense_candidates.tsv", ["phage_genome_id", "candidate_id", "antidefense_class", "target_defense_system", "evidence_type"]),
    ("stage_6_compatibility", "results/defense_systems/compatibility_features.tsv", ["phage_genome_id", "host_genome_id", "K_type", "O_type", "host_defense_system_count", "phage_antidefense_count", "compatibility_feature_status"]),
    ("stage_7_model_comparison", "results/models/model_comparison.tsv", ["analysis_id", "hypothesis", "task", "target", "feature_set", "status"]),
    ("stage_7_feature_importance", "results/models/feature_importance.tsv", ["analysis_id", "hypothesis", "task", "feature_set", "feature", "association_metric"]),
    ("stage_7_prediction_errors", "results/models/prediction_errors.tsv", ["analysis_id", "task", "target", "feature_set", "sample_id", "true_label", "predicted_label"]),
    ("stage_7_hypothesis_summary", "results/models/hypothesis_summary.tsv", ["hypothesis", "primary_question", "required_test", "matching_model_rows", "ok_model_rows", "summary_status", "claim_status"]),
    ("stage_8_figure_manifest", "results/figures/figure_manifest.tsv", ["figure_id", "source_tsv", "draft_svg", "row_count", "status"]),
]

REQUIRED_DOCS = [
    "AGENTS.md",
    "README.md",
    "project_goal.md",
    "docs/methods.md",
    "docs/hypotheses.md",
    "docs/limitations.md",
    "docs/claim_ledger.md",
    "docs/figure_plan.md",
    "docs/metadata_schema.md",
    "docs/tool_availability_schema.md",
    "docs/genome_sequence_qc_schema.md",
    "docs/sequence_acquisition_schema.md",
    "docs/sequence_fetch_manifest_schema.md",
    "docs/external_evidence_plan_schema.md",
    "docs/external_evidence_template_schema.md",
    "docs/external_evidence_run_packet_schema.md",
    "docs/external_evidence_protein_handoff_schema.md",
    "docs/external_evidence_acceptance_schema.md",
    "docs/external_evidence_acceptance_self_test_schema.md",
    "docs/external_evidence_unlock_schema.md",
    "docs/source_catalog_schema.md",
    "docs/source_catalog_readiness_schema.md",
    "docs/source_manifest_import_schema.md",
    "docs/source_query_plan_schema.md",
    "docs/source_query_commands_schema.md",
    "docs/source_export_template_schema.md",
    "docs/source_export_dictionary_schema.md",
    "docs/source_export_validation_schema.md",
    "docs/source_export_validation_self_test_schema.md",
    "docs/source_acquisition_plan_schema.md",
    "docs/source_curation_tasks_schema.md",
    "docs/source_export_starter_kit_schema.md",
    "docs/source_export_bootstrap_schema.md",
    "docs/minimum_source_curation_schema.md",
    "docs/source_enablement_schema.md",
    "docs/source_enablement_apply_schema.md",
    "docs/source_readiness_dashboard_schema.md",
    "docs/source_curation_work_order_schema.md",
    "docs/source_curation_issue_body_schema.md",
    "docs/source_work_order_packet_schema.md",
    "docs/source_work_order_acceptance_schema.md",
    "docs/source_work_order_acceptance_self_test_schema.md",
    "docs/source_post_acceptance_schema.md",
    "docs/priority_source_preflight_schema.md",
    "docs/priority_source_collection_packet_schema.md",
    "docs/hypothesis_source_unlock_schema.md",
    "docs/source_curation_packet_schema.md",
    "docs/source_overlap_schema.md",
    "docs/sample_support_schema.md",
    "docs/sample_support_source_bridge_schema.md",
    "docs/sample_support_export_preflight_schema.md",
    "docs/sample_support_curation_packet_schema.md",
    "docs/dereplication_schema.md",
    "docs/annotation_schema.md",
    "docs/rbp_depolymerase_schema.md",
    "docs/host_feature_schema.md",
    "docs/defense_counterdefense_schema.md",
    "docs/host_defense_run_handoff_schema.md",
    "docs/phage_antidefense_screening_handoff_schema.md",
    "docs/modeling_schema.md",
    "docs/figure_generation_schema.md",
    "docs/workflow_runner.md",
    "docs/reviewer_handoff.md",
    "docs/study_readiness_schema.md",
    "docs/readiness_action_plan_schema.md",
    "docs/goal_completion_audit_schema.md",
    "docs/pipeline_efficiency_audit_schema.md",
    "docs/hypothesis_traceability_schema.md",
    "docs/claim_support_audit_schema.md",
    "docs/manuscript_outline.md",
]

REQUIRED_SCRIPTS = [
    "scripts/run_workflow.py",
    "scripts/audit_tool_availability.py",
    "scripts/plan_source_queries.py",
    "scripts/create_source_query_commands.py",
    "scripts/create_source_export_templates.py",
    "scripts/create_source_export_dictionary.py",
    "scripts/validate_source_exports.py",
    "scripts/self_test_source_export_validation.py",
    "scripts/self_test_source_work_order_acceptance.py",
    "scripts/self_test_external_evidence_acceptance.py",
    "scripts/import_source_manifests.py",
    "scripts/plan_source_acquisition.py",
    "scripts/build_samples_from_sources.py",
    "scripts/audit_source_catalog.py",
    "scripts/summarize_source_curation_tasks.py",
    "scripts/create_source_export_starter_kit.py",
    "scripts/bootstrap_source_exports.py",
    "scripts/plan_hypothesis_source_unlocks.py",
    "scripts/plan_minimum_source_curation.py",
    "scripts/preflight_priority_source_exports.py",
    "scripts/create_priority_source_collection_packet.py",
    "scripts/plan_source_enablement.py",
    "scripts/apply_source_enablement.py",
    "scripts/build_source_readiness_dashboard.py",
    "scripts/build_source_curation_work_order.py",
    "scripts/create_source_work_order_packets.py",
    "scripts/create_source_curation_issue_bodies.py",
    "scripts/check_source_work_order_acceptance.py",
    "scripts/plan_source_post_acceptance.py",
    "scripts/create_source_curation_packet.py",
    "scripts/audit_source_overlaps.py",
    "scripts/audit_sample_support.py",
    "scripts/plan_sample_support_sources.py",
    "scripts/preflight_sample_support_exports.py",
    "scripts/create_sample_support_curation_packet.py",
    "scripts/00_build_phage_manifest.py",
    "scripts/00_qc_genome_sequences.py",
    "scripts/plan_sequence_acquisition.py",
    "scripts/create_sequence_fetch_manifest.py",
    "scripts/create_sequence_fetch_review_packet.py",
    "scripts/plan_external_evidence.py",
    "scripts/create_external_evidence_templates.py",
    "scripts/create_external_evidence_run_packets.py",
    "scripts/create_phage_antidefense_screening_handoff.py",
    "scripts/export_external_evidence_proteins.py",
    "scripts/check_external_evidence_acceptance.py",
    "scripts/plan_external_evidence_unlocks.py",
    "scripts/create_production_evidence_handoff.py",
    "scripts/audit_pipeline_efficiency.py",
    "scripts/01_dereplicate_phages.py",
    "scripts/build_host_feature_bridge_evidence.py",
    "scripts/02_build_annotation_tables.py",
    "scripts/03_predict_rbps_depolymerases.py",
    "scripts/04_integrate_host_features.py",
    "scripts/create_host_defense_run_handoff.py",
    "scripts/05_integrate_defense_counterdefense.py",
    "scripts/06_compare_feature_models.py",
    "scripts/07_generate_figure_sources.py",
    "scripts/08_validate_workflow.py",
    "scripts/09_audit_study_readiness.py",
    "scripts/10_plan_readiness_actions.py",
    "scripts/11_audit_goal_completion.py",
    "scripts/12_build_hypothesis_traceability.py",
    "scripts/13_audit_claim_support.py",
]

REQUIRED_CONFIGS = [
    "Snakefile",
    "config/samples.tsv",
    "config/thresholds.yaml",
    "config/tools.yaml",
    "config/workflow.yaml",
    "config/source_catalog.yaml",
    "config/source_catalog.mock.yaml",
    "config/source_imports.yaml",
    "config/source_imports.mock.yaml",
    "config/source_queries.yaml",
    "config/source_queries.mock.yaml",
]

REQUIRED_FIGURES = [
    "figure_1_dataset_atlas",
    "figure_2_phage_pangenome",
    "figure_3_rbp_module_network",
    "figure_4_k_o_association",
    "figure_5_defense_counterdefense",
    "figure_6_novelty_prioritization",
]

HYPOTHESIS_TESTS = [
    ("H1", "K/O prediction model comparison", lambda row: row.get("hypothesis") == "H1" and row.get("task") in {"predict_K_type", "predict_O_type"}),
    ("H2", "prophage RBP module reservoir summary", lambda row: row.get("analysis_id") == "record_type_vs_rbp_modules"),
    ("H3", "RBP module versus counter-defense summary", lambda row: row.get("analysis_id") == "rbp_modules_vs_counterdefense"),
    ("H4", "receptor plus defense/counter-defense model comparison", lambda row: row.get("hypothesis") == "H4" and row.get("feature_set") in {"receptor_plus_defense_counterdefense", "taxonomy_plus_receptor_defense_counterdefense"}),
    ("H5", "host background versus defense burden summary", lambda row: row.get("analysis_id") == "st_vs_defense_status"),
    ("H6", "source and cluster novelty prioritization summary", lambda row: row.get("analysis_id") in {"source_vs_rbp_novelty", "cluster_size_vs_rbp_novelty"}),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Klebsiella phage CPG workflow state.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--results-dir", default="results", help="Results directory to audit, relative to root unless absolute.")
    parser.add_argument("--samples", default="config/samples.tsv", help="Sample table used by the audited workflow.")
    parser.add_argument("--workflow-config", default="config/workflow.yaml", help="Workflow config used by the audited workflow.")
    parser.add_argument("--schema-output", required=True, help="Schema validation TSV.")
    parser.add_argument("--hypothesis-output", required=True, help="Hypothesis coverage TSV.")
    parser.add_argument("--inventory-output", required=True, help="Output inventory TSV.")
    parser.add_argument("--report-output", required=True, help="Workflow validation report TSV.")
    return parser.parse_args()


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


def add_report(report: list[dict[str, str]], severity: str, item: str, status: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "status": status, "message": message})

def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def remap_results_path(rel_path: str, results_dir: Path) -> Path:
    suffix = rel_path[len("results/"):] if rel_path.startswith("results/") else rel_path
    return results_dir / suffix


def flatten_config_values(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for nested in value.values():
            values.extend(flatten_config_values(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(flatten_config_values(nested))
    elif isinstance(value, str):
        values.append(value)
    return values


def mock_fixture_references(config_text: str) -> list[str]:
    try:
        import yaml  # type: ignore
        loaded = yaml.safe_load(config_text) or {}
        values = flatten_config_values(loaded)
    except Exception:
        values = [line.strip() for line in config_text.splitlines()]
    refs: list[str] = []
    for value in values:
        normalized = value.replace("\\", "/")
        lowered = normalized.lower()
        if (
            "/mock" in lowered
            or "mock_" in lowered
            or lowered.startswith("results/mock")
            or lowered.startswith("data/metadata/mock")
            or lowered.startswith("data/raw/mock")
            or lowered.endswith(".mock.yaml")
        ):
            if normalized not in refs:
                refs.append(normalized)
    return refs


def validate_schemas(root: Path, results_dir: Path) -> list[dict[str, str]]:
    rows = []
    for stage, rel_path, required_columns in REQUIRED_OUTPUTS:
        path = remap_results_path(rel_path, results_dir)
        fieldnames, data_rows = read_tsv(path)
        missing = [column for column in required_columns if column not in fieldnames]
        exists = path.exists()
        if not exists:
            status = "fail"
            notes = "missing required output"
        elif missing:
            status = "fail"
            notes = "missing required columns"
        elif len(data_rows) == 0 and stage == "stage_1_report":
            status = "pass"
            notes = "schema valid; no validation issues reported"
        elif len(data_rows) == 0:
            status = "warn"
            notes = "schema valid but no data rows"
        else:
            status = "pass"
            notes = "schema valid"
        rows.append(
            {
                "stage": stage,
                "path": display_path(root, path),
                "exists": str(exists).lower(),
                "row_count": str(len(data_rows)),
                "required_columns_present": str(not missing and exists).lower(),
                "missing_columns": ";".join(missing),
                "status": status,
                "notes": notes,
            }
        )
    return rows


def validate_docs(root: Path, report: list[dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_DOCS if not (root / path).exists()]
    if missing:
        add_report(report, "error", "documentation", "fail", "Missing docs: " + ";".join(missing))
    else:
        add_report(report, "info", "documentation", "pass", f"All {len(REQUIRED_DOCS)} required documentation files exist.")

    limitations = (root / "docs/limitations.md").read_text(encoding="utf-8") if (root / "docs/limitations.md").exists() else ""
    if "experiment" in limitations.lower() and "computational" in limitations.lower():
        add_report(report, "info", "limitations", "pass", "Limitations distinguish computational predictions from experimental validation needs.")
    else:
        add_report(report, "warning", "limitations", "warn", "Limitations doc may not clearly distinguish computational predictions from experimental validation.")

    validate_claim_ledger(root, report)


def validate_claim_ledger(root: Path, report: list[dict[str, str]]) -> None:
    path = root / "docs/claim_ledger.md"
    if not path.exists():
        add_report(report, "error", "claim_ledger", "fail", "docs/claim_ledger.md is missing.")
        return
    text = path.read_text(encoding="utf-8").lower()
    required_terms = [
        "workflow_supported",
        "data_dependent",
        "computational_inference",
        "experimental_validation_required",
        "remaining speculative claims",
        "allowed wording",
        "forbidden wording",
    ]
    missing_terms = [term for term in required_terms if term not in text]
    missing_hypotheses = [f"h{index}" for index in range(1, 7) if f"h{index}" not in text]
    if missing_terms or missing_hypotheses:
        details = []
        if missing_terms:
            details.append("missing terms: " + ";".join(missing_terms))
        if missing_hypotheses:
            details.append("missing hypotheses: " + ";".join(missing_hypotheses))
        add_report(report, "error", "claim_ledger", "fail", "Claim ledger is incomplete; " + " | ".join(details))
    else:
        add_report(report, "info", "claim_ledger", "pass", "Claim ledger covers H1-H6, claim status categories, allowed wording, forbidden wording, and remaining speculative claims.")


def validate_scripts(root: Path, report: list[dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_SCRIPTS if not (root / path).exists()]
    if missing:
        add_report(report, "error", "scripts", "fail", "Missing scripts: " + ";".join(missing))
        return
    failed = []
    for rel_path in REQUIRED_SCRIPTS:
        try:
            py_compile.compile(str(root / rel_path), doraise=True)
        except py_compile.PyCompileError as exc:
            failed.append(f"{rel_path}:{exc.msg}")
    if failed:
        add_report(report, "error", "scripts", "fail", "Compile failures: " + ";".join(failed))
    else:
        add_report(report, "info", "scripts", "pass", f"All {len(REQUIRED_SCRIPTS)} workflow scripts compile.")


def validate_configs(root: Path, report: list[dict[str, str]], workflow_config: Path) -> None:
    missing = [path for path in REQUIRED_CONFIGS if not (root / path).exists()]
    if missing:
        add_report(report, "error", "workflow_config", "fail", "Missing config files: " + ";".join(missing))
        return

    snakefile = root / "Snakefile"
    snake_text = snakefile.read_text(encoding="utf-8")
    if "scripts/run_workflow.py" not in snake_text or "WORKFLOW_CONFIG" not in snake_text:
        add_report(report, "error", "snakefile", "fail", "Snakefile must delegate to scripts/run_workflow.py with a workflow config.")
    else:
        add_report(report, "info", "snakefile", "pass", "Snakefile delegates to the config-driven direct workflow runner.")

    if not workflow_config.exists():
        add_report(report, "error", "workflow_config", "fail", f"Workflow config does not exist: {display_path(root, workflow_config)}")
        return
    text = workflow_config.read_text(encoding="utf-8")
    required_sections = ["execution:", "inputs:", "outputs:", "logs:"]
    missing_sections = [section for section in required_sections if section not in text]
    if missing_sections:
        add_report(report, "error", "workflow_config", "fail", f"{display_path(root, workflow_config)} missing sections: " + ";".join(missing_sections))
    else:
        add_report(report, "info", "workflow_config", "pass", f"Workflow config {display_path(root, workflow_config)} exists with required top-level sections.")

    mock_refs = mock_fixture_references(text)
    is_mock_config = workflow_config.name.endswith(".mock.yaml") or "/mock" in display_path(root, workflow_config).lower()
    if is_mock_config:
        add_report(report, "info", "mock_fixture_boundary", "pass", f"Mock workflow config allows fixture references; fixture_refs={len(mock_refs)}.")
    elif mock_refs:
        add_report(report, "error", "mock_fixture_boundary", "fail", "Real workflow config references mock fixture paths: " + ";".join(mock_refs[:20]))
    else:
        add_report(report, "info", "mock_fixture_boundary", "pass", "Real workflow config has no mock fixture path references.")


def validate_figures(root: Path, results_dir: Path, report: list[dict[str, str]]) -> None:
    manifest_path = results_dir / "figures/figure_manifest.tsv"
    _, rows = read_tsv(manifest_path)
    by_id = {row.get("figure_id", ""): row for row in rows}
    missing = [figure for figure in REQUIRED_FIGURES if figure not in by_id]
    missing_files = []
    for figure in REQUIRED_FIGURES:
        row = by_id.get(figure, {})
        for column in ["source_tsv", "draft_svg"]:
            value = row.get(column, "")
            figure_path = resolve_path(root, value) if value else Path("")
            if not value or not figure_path.exists():
                missing_files.append(f"{figure}:{column}")
    if missing or missing_files:
        add_report(report, "error", "figures", "fail", "Missing figures or files: " + ";".join(missing + missing_files))
    else:
        add_report(report, "info", "figures", "pass", f"All {len(REQUIRED_FIGURES)} planned figures have source TSVs and draft SVGs.")
    empty = [row.get("figure_id", "") for row in rows if row.get("status") == "empty_schema_valid"]
    if empty:
        add_report(report, "warning", "figures_data", "warn", "Figures with empty source data: " + ";".join(empty))


def validate_hypotheses(root: Path, results_dir: Path, report: list[dict[str, str]]) -> list[dict[str, str]]:
    model_path = results_dir / "models/model_comparison.tsv"
    _, model_rows = read_tsv(model_path)
    output_rows = []
    for hypothesis, required_test, predicate in HYPOTHESIS_TESTS:
        matching = [row for row in model_rows if predicate(row)]
        ok_rows = [row for row in matching if row.get("status") == "ok"]
        limited = [row for row in matching if row.get("status") and row.get("status") != "ok"]
        if not matching:
            status = "fail"
            notes = "no matching quantitative test rows"
        elif ok_rows:
            status = "pass"
            notes = "quantitative test rows present with at least one ok status"
        else:
            status = "warn"
            notes = "quantitative test rows present but current data are insufficient or uninformative"
        output_rows.append(
            {
                "hypothesis": hypothesis,
                "required_test": required_test,
                "evidence_path": display_path(root, model_path),
                "matching_rows": str(len(matching)),
                "ok_rows": str(len(ok_rows)),
                "limited_rows": str(len(limited)),
                "status": status,
                "notes": notes,
            }
        )
    failures = [row["hypothesis"] for row in output_rows if row["status"] == "fail"]
    warnings = [row["hypothesis"] for row in output_rows if row["status"] == "warn"]
    if failures:
        add_report(report, "error", "hypothesis_coverage", "fail", "Missing quantitative tests for: " + ";".join(failures))
    elif warnings:
        add_report(report, "warning", "hypothesis_coverage", "warn", "Tests exist but current data are limited for: " + ";".join(warnings))
    else:
        add_report(report, "info", "hypothesis_coverage", "pass", "All H1-H6 have quantitative tests with ok status rows.")
    return output_rows


def inventory_outputs(root: Path, results_dir: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(results_dir.rglob("*")) if results_dir.exists() else []:
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        row_count = ""
        notes = ""
        if path.suffix == ".tsv":
            _, data_rows = read_tsv(path)
            row_count = str(len(data_rows))
            if len(data_rows) == 0:
                notes = "empty table"
        rows.append(
            {
                "path": rel,
                "exists": "true",
                "size_bytes": str(path.stat().st_size),
                "row_count": row_count,
                "status": "present",
                "notes": notes,
            }
        )
    return rows


def validate_inputs(root: Path, samples_path: Path, report: list[dict[str, str]]) -> None:
    _, rows = read_tsv(samples_path)
    sample_label = display_path(root, samples_path)
    if not rows:
        add_report(report, "warning", "project_data", "warn", f"{sample_label} has no data rows; workflow is currently a validated scaffold, not a populated study.")
    else:
        add_report(report, "info", "project_data", "pass", f"{sample_label} contains {len(rows)} data rows.")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    results_dir = resolve_path(root, args.results_dir)
    samples_path = resolve_path(root, args.samples)
    workflow_config = resolve_path(root, args.workflow_config)
    report: list[dict[str, str]] = []

    schema_rows = validate_schemas(root, results_dir)
    schema_failures = [row for row in schema_rows if row["status"] == "fail"]
    schema_warnings = [row for row in schema_rows if row["status"] == "warn"]
    if schema_failures:
        add_report(report, "error", "required_output_schemas", "fail", f"{len(schema_failures)} required output schemas failed.")
    elif schema_warnings:
        add_report(report, "warning", "required_output_schemas", "warn", f"All required schemas exist, but {len(schema_warnings)} are empty.")
    else:
        add_report(report, "info", "required_output_schemas", "pass", f"All {len(schema_rows)} required output schemas passed.")

    validate_inputs(root, samples_path, report)
    validate_docs(root, report)
    validate_scripts(root, report)
    validate_configs(root, report, workflow_config)
    validate_figures(root, results_dir, report)
    hypothesis_rows = validate_hypotheses(root, results_dir, report)

    if shutil.which("snakemake"):
        add_report(report, "info", "snakemake", "pass", "snakemake is available on PATH.")
    else:
        add_report(report, "warning", "snakemake", "warn", "snakemake is not available on PATH in the current shell; direct Python commands were used for validation.")

    write_tsv(Path(args.schema_output), SCHEMA_COLUMNS, schema_rows)
    write_tsv(Path(args.hypothesis_output), HYPOTHESIS_COLUMNS, hypothesis_rows)
    write_tsv(Path(args.inventory_output), INVENTORY_COLUMNS, inventory_outputs(root, results_dir))
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)

    error_count = sum(1 for row in report if row["severity"] == "error")
    warning_count = sum(1 for row in report if row["severity"] == "warning")
    print(f"Workflow validation complete: {error_count} errors, {warning_count} warnings.")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
