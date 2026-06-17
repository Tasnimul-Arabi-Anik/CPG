# Source Export Starter Kit Schema

Stage 0 writes a source-export starter kit under `results/qc/source_export_starter_kit/`. The kit is an operational handoff for A01 source curation: it does not create biological data, but it gives a fillable header, source-specific README, expected reviewed export path, query, identity rules, and validation command for each configured source.

## `results/qc/source_export_starter_kit_manifest.tsv`

One row per configured source. Important columns:

| Column | Description |
| --- | --- |
| `source_id` | Source identifier from `config/source_catalog.yaml` and source curation tasks. |
| `query_id` | Query identifier from `config/source_queries.yaml`. |
| `record_layer` | Cultured phage, prophage, host genome, or optional discovery layer. |
| `review_priority` | Source priority for real-data curation. |
| `target_database` | Database or local review source. |
| `starter_readme_path` | Per-source curation checklist under `results/qc/source_export_starter_kit/`. |
| `starter_template_path` | Fillable header-only TSV under `results/qc/source_export_starter_kit/`. |
| `expected_export_path` | Reviewed TSV path to populate outside `results/`, usually under `data/metadata/source_exports/`. |
| `required_columns` | Header expected by source export validation/import. |
| `identity_columns_required` | At least one identity column that must be populated per row. |
| `query_string` | Search or curation query used to find records. |
| `command_hint` | Existing source-specific validation hint. |
| `validation_command` | Command to rerun after the reviewed export has been populated. |
| `curation_status` | Current source curation status. |
| `next_action` | Next action from the source curation task table. |

## `results/qc/source_export_starter_kit/README.md`

Index of all source-specific starter files.

## Per-source files

Each source gets:

- `<source_id>.template.tsv`: header-only starter TSV for manual curation.
- `<source_id>.README.md`: source-specific checklist, query, required identity columns, column dictionary, expected export path, and validation command.

## Interpretation

Starter files under `results/` are not imported as study data. Reviewed records must be saved to the configured `expected_export_path`, then validated and imported by the normal workflow.
