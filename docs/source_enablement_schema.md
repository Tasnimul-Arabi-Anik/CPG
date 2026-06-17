# Source Enablement Schema

Stage 0 writes a source enablement plan after source export validation, import planning, and minimum source curation ranking. The plan tells which reviewed exports are still missing, which sources are ready for import/catalog enablement, and which configuration entries need manual review.

## `results/qc/source_enablement_plan.tsv`

One row per configured source. Important columns:

| Column | Description |
| --- | --- |
| `source_id` | Source identifier. |
| `recommended_rank` | Rank from the minimum source curation plan. |
| `record_layer` | Source record layer. |
| `required_for_hypotheses` | H1-H6 hypotheses requiring this source. |
| `export_path` | Reviewed source export path. |
| `export_status` | Whether the reviewed export currently exists. |
| `export_row_count` | Number of rows in the reviewed export. |
| `export_validation_status` | Current source export validation status. |
| `import_id` | Matching import configuration ID. |
| `import_enabled` | Current `config/source_imports.yaml` enabled state. |
| `import_output_path` | Manifest path produced by import. |
| `catalog_enabled` | Current `config/source_catalog.yaml` enabled state. |
| `manifest_path` | Source manifest consumed by sample building. |
| `manifest_row_count` | Current source manifest row count. |
| `enablement_status` | `waiting_for_reviewed_export`, `export_empty`, `export_needs_validation_fix`, `ready_for_enablement`, or `enabled_for_sample_build`. |
| `config_actions_required` | Manual config actions still needed. |
| `validation_command` | Command to rerun after completing the action. |
| `next_action` | Human-readable next step. |

## `results/qc/source_enablement_report.tsv`

Run-level summary with source counts and enablement status counts.

## Interpretation

This stage does not automatically edit `config/source_imports.yaml` or `config/source_catalog.yaml`. Enablement is deliberately manual because reviewed exports and generated source manifests must be checked before they drive biological analyses.
