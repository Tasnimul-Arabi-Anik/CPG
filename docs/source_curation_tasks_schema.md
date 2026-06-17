# Source Curation Tasks Schema

Stage 0 writes `results/qc/source_curation_tasks.tsv` as the single handoff table for moving from planned public-source queries to real sample rows. It consolidates source query plans, export templates, export validation, source acquisition status, and catalog readiness.

## Inputs

- `results/qc/source_query_plan.tsv`
- `results/qc/source_export_template_manifest.tsv`
- `results/qc/source_export_validation.tsv`
- `results/qc/source_acquisition_plan.tsv`
- `results/qc/source_catalog_readiness.tsv`

## Outputs

### `results/qc/source_curation_tasks.tsv`

Important columns:

- `source_id`: source catalog identifier.
- `query_id`: planned query/export identifier.
- `record_layer`: cultured phage, prophage, host genome, or discovery layer.
- `priority`: primary, primary manual, or optional discovery priority.
- `target_database`: source system or manual curation context.
- `expected_export_path`: local reviewed export path to populate.
- `template_path`: generated blank template path for the export.
- `manifest_path`: normalized source manifest path used by sample building.
- `import_id`: matching source import entry.
- `import_enabled`: whether the import is enabled in `config/source_imports.yaml`.
- `catalog_enabled`: whether the source is enabled in `config/source_catalog.yaml`.
- `export_status`: export validation state.
- `manifest_status`: source catalog readiness or acquisition state.
- `curation_status`: consolidated status for the next curation decision.
- `blocking_for_real_study`: `true` when real sample generation is blocked by this source state.
- `required_export_columns`: expected columns for the reviewed export.
- `identity_columns_required`: identity columns that make rows importable.
- `query_string`: query or manual curation definition.
- `next_action`: human-readable next step.
- `command_hint`: command or config-edit hint for the next workflow rerun.

### `results/qc/source_curation_tasks_report.tsv`

Run-level summary with task, ready, blocking, missing-export, and invalid-export counts.

## Interpretation

This table does not download or trust external metadata automatically. It makes the reviewed local-export handoff auditable so source population can be completed without hidden manual steps. A source is ready for downstream sample building only after reviewed exports are present, imports are enabled when needed, catalog entries are enabled, and source readiness reports pass.

## Human-Readable Packet

`results/qc/source_curation_packet/` is generated from this task table. It contains a README plus one Markdown checklist per source for manual reviewed-export curation.
