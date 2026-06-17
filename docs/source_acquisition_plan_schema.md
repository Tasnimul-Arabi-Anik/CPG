# Source Acquisition Plan Schema

`scripts/plan_source_acquisition.py` compares the source catalog, source import configuration, and local source-manifest files to produce a concrete checklist for moving the project from scaffold to populated study. It complements `results/qc/source_query_plan.tsv`, which records the upstream query and reviewed-export handoff for each planned source.

The stage is local-only. It does not download genomes, does not call public services, and does not modify `data/raw/`.

## Command

```bash
python scripts/plan_source_acquisition.py \
  --catalog config/source_catalog.yaml \
  --imports-config config/source_imports.yaml \
  --plan-output results/qc/source_acquisition_plan.tsv \
  --report-output results/qc/source_acquisition_report.tsv
```

The direct workflow runner executes this as `stage_0_source_plan` when `source_plan.enabled: true`.

## Plan Output

Default path: `results/qc/source_acquisition_plan.tsv`.

| Column | Description |
| --- | --- |
| `source_id` | Source entry identifier from `config/source_catalog.yaml`. |
| `record_layer` | Broad study layer: cultured phages, prophages, host genomes, literature-curated phages, or metagenomic discovery. |
| `catalog_enabled` | Whether the source is currently included by the sample builder. |
| `catalog_required` | Whether a missing source should be treated as required by the catalog. |
| `manifest_path` | Local source-manifest path. |
| `manifest_exists` | Whether the manifest path exists. |
| `manifest_row_count` | Number of data rows currently present in the manifest. |
| `import_id` | Matching source-import entry, if one exists. |
| `import_configured` | Whether an import entry maps to the manifest. |
| `import_enabled` | Whether the import entry is currently enabled. |
| `import_input_path` | Local metadata export expected by the import entry. |
| `import_input_exists` | Whether the local export exists. |
| `import_input_row_count` | Number of data rows in the local export when present. |
| `import_input_recognized_columns` | Canonical sample columns recognized from the local export header. |
| `import_input_identity_columns` | Recognized identity columns among `genome_id`, `accession`, and `raw_sequence_path`, or any catalog override. |
| `import_input_filter_pass_count` | Number of local export rows that pass configured import filters. |
| `import_input_filter_skip_count` | Number of local export rows excluded by configured import filters. |
| `import_output_path` | Manifest path written by the import entry. |
| `import_output_matches_manifest` | Whether the import output maps to the catalog manifest. |
| `acquisition_status` | Current state of this source. |
| `priority` | Required, primary, primary manual, or optional discovery. |
| `next_action` | Human-readable next action. |
| `suggested_command` | Command or file action that advances this source. |
| `notes` | Catalog notes retained for provenance. |

## Export Preflight Checks

When a configured local export exists, the planner reads it with the same delimiter setting used by `scripts/import_source_manifests.py`, recognizes the same column aliases, checks for at least one configured identity column, and applies the same Klebsiella/phage/include/exclude filters. Header-only exports, exports with no identity column, and exports where all rows are filtered out are not labeled import-ready.

## Status Values

Common `acquisition_status` values:

| Status | Meaning |
| --- | --- |
| `ready_for_sample_build` | Source is enabled and the manifest has rows. |
| `manifest_populated_but_catalog_disabled` | Source has rows but is not yet included in the build. |
| `catalog_enabled_but_manifest_empty` | Source is enabled but has no rows, which should be fixed before production analysis. |
| `local_export_ready_import_disabled` | A local export exists, contains rows, has a recognized identity column, passes filters, but the import entry is disabled. |
| `local_export_ready_for_import` | A local export exists and passes preflight checks, and the import entry is enabled. |
| `local_export_empty` | A configured local export exists but contains no data rows. |
| `local_export_missing_identity` | A local export exists but lacks a recognized identity column. |
| `local_export_filters_exclude_all` | A local export exists but all rows are removed by configured filters. |
| `import_output_mismatch` | The import output path does not match the manifest path in the source catalog. |
| `waiting_for_local_export` | An import entry exists, but the configured local export file is absent. |
| `manifest_template_empty` | A manifest template exists but contains no rows and no local import is ready. |
| `required_manifest_missing` | A required source manifest is absent. |
| `optional_manifest_missing` | An optional source manifest is absent. |

## Report Output

Default path: `results/qc/source_acquisition_report.tsv`.

Columns:

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Summary item or status category. |
| `message` | Human-readable summary. |

## Production Use

Use this plan before enabling a source in `config/source_catalog.yaml`. A source should normally move through this sequence:

1. local metadata export exists, or source manifest is manually populated;
2. import is run when applicable;
3. source manifest is reviewed;
4. catalog entry is enabled;
5. `stage_0_source_audit`, `stage_0_samples`, and Stage 1 are rerun.
