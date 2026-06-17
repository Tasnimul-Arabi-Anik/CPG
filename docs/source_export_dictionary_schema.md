# Source Export Column Dictionary Schema

Stage 0 writes `results/qc/source_export_column_dictionary.tsv` from the reviewed-export template manifest. It explains the meaning, expected format, missing-value policy, and validation role of each source export column.

## Inputs

- `results/qc/source_export_template_manifest.tsv`

## Outputs

### `results/qc/source_export_column_dictionary.tsv`

One row per source/template column. Important columns:

- `source_id`: source catalog identifier.
- `query_id`: query/export identifier.
- `record_layer`: study layer for the source.
- `target_database`: source database or curation context.
- `template_path`: generated reviewed-export template path.
- `expected_export_path`: reviewed export path to populate.
- `column_name`: export column.
- `column_role`: identity, metadata, provenance, host feature, or sequence/QC role.
- `required_for_identity`: whether the column is required to identify/import rows for that source.
- `recommended_for_layer`: whether the column is recommended for that source layer.
- `description`: meaning of the column.
- `expected_format`: expected value shape.
- `missing_value_policy`: how missing values should be represented.
- `validation_notes`: downstream validation or modeling implications.

### `results/qc/source_export_column_dictionary_report.tsv`

Run-level summary with source, dictionary-row, unique-column, and identity-row counts.

## Interpretation

This dictionary is a curation guide for reviewed local exports. It does not replace the source templates; instead, it explains how to fill them consistently before source import and sample generation.
