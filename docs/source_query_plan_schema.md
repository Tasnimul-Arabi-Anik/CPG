# Source Query Plan Schema

`scripts/plan_source_queries.py` records the query and reviewed-export handoff for each public or local source before source manifests are imported. This stage is deliberately local-only: it does not call public services and does not download sequence data.

## Command

```bash
python scripts/plan_source_queries.py \
  --queries-config config/source_queries.yaml \
  --catalog config/source_catalog.yaml \
  --imports-config config/source_imports.yaml \
  --plan-output results/qc/source_query_plan.tsv \
  --report-output results/qc/source_query_report.tsv
```

The direct workflow runner executes this as `stage_0_source_queries` when `source_queries.enabled: true`.

## Plan Output

Default path: `results/qc/source_query_plan.tsv`.

| Column | Description |
| --- | --- |
| `query_id` | Stable identifier for the planned query or manual export. |
| `source_id` | Matching source from `config/source_catalog.yaml`. |
| `record_layer` | Study layer: cultured phages, prophages, host genomes, literature-curated phages, or discovery contigs. |
| `target_database` | Public database, local tool export, or manual curation source. |
| `acquisition_mode` | How the query is expected to become a local reviewed TSV. |
| `query_string` | Database query, search phrase, or precise manual export description. |
| `expected_export_path` | Local TSV path that should receive the reviewed export. |
| `export_path_exists` | Whether the expected export currently exists. |
| `export_row_count` | Number of data rows currently present in the export. |
| `expected_manifest_path` | Source manifest path from the source catalog. |
| `manifest_exists` | Whether the catalog manifest currently exists. |
| `manifest_row_count` | Number of data rows currently in the manifest. |
| `import_id` | Matching source import entry, if configured. |
| `import_configured` | Whether source imports can normalize this export. |
| `import_input_path` | Import input path from `config/source_imports.yaml`. |
| `export_path_matches_import` | Whether the query export path matches the import input path. |
| `import_output_path` | Import output manifest path. |
| `import_output_matches_manifest` | Whether import output matches the source catalog manifest path. |
| `expected_columns` | Expected export columns for reviewer checks. |
| `identity_columns_required` | Identity columns that must be present before import. |
| `review_priority` | Primary, primary manual, optional discovery, fixture, or similar priority label. |
| `query_status` | Current handoff status. |
| `blocking_issue` | Whether the status reflects a configuration problem. |
| `next_action` | Human-readable action to advance the source. |
| `suggested_command` | Local command or file action for the next handoff. |
| `rationale` | Why this source matters for the study hypothesis. |
| `notes` | Additional review notes. |

## Status Values

| Status | Meaning |
| --- | --- |
| `planned_query_ready` | Query is configured and waiting for a reviewed local export. |
| `local_export_present` | Reviewed export exists and has data rows. |
| `local_export_empty` | Export path exists but has no data rows. |
| `source_already_enabled` | Source manifest is populated and enabled in the catalog. |
| `manual_query_no_import` | Query exists but no matching source import is configured. |
| `config_error` | Source, query, import input, or import output configuration is inconsistent. |

## Production Use

Use this plan before filling `data/metadata/source_exports/`. Each export should be reviewed for accession identity, Klebsiella relevance, non-phage contamination, duplicate records, and provenance before enabling the corresponding source import.

## Command Sheet

`results/qc/source_query_commands.tsv` and `results/qc/source_query_commands.sh` are generated from this plan after export templates are created. They provide URLs, command hints, and review checklists for creating the reviewed local exports.
