# Source Export Validation Schema

`scripts/validate_source_exports.py` checks reviewed source export files before they are imported into normalized source manifests. Missing exports are reported as warnings so the scaffold can still run. Populated exports with invalid headers, missing identity values, duplicate identity values, or malformed controlled/numeric row values are blocking errors.

## Command

```bash
python scripts/validate_source_exports.py \
  --query-plan results/qc/source_query_plan.tsv \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --validation-output results/qc/source_export_validation.tsv \
  --report-output results/qc/source_export_validation_report.tsv \
  --root .
```

The direct workflow runner executes this as `stage_0_source_export_validation` after template generation and before source import.

## Validation Output

Default path: `results/qc/source_export_validation.tsv`.

| Column | Description |
| --- | --- |
| `query_id` | Query identifier from `source_query_plan.tsv`. |
| `source_id` | Source catalog identifier. |
| `record_layer` | Study layer represented by the source. |
| `target_database` | Database or manual source. |
| `expected_export_path` | Reviewed export path expected by source import. |
| `export_exists` | Whether the reviewed export exists. |
| `export_row_count` | Number of rows in the export when present. |
| `header_columns` | Header columns observed in the export. |
| `expected_columns` | Expected query-plan columns. |
| `missing_expected_columns` | Expected columns absent from the export. |
| `identity_columns_required` | Identity columns from the query plan. |
| `identity_columns_present` | Required identity columns present in the export header. |
| `identity_columns_missing` | Required identity columns missing from the export header. |
| `rows_missing_all_identity` | Rows where all present identity columns are blank or missing. |
| `duplicate_identity_columns` | Identity columns containing duplicate non-missing values. |
| `duplicate_identity_values` | Up to 50 duplicate identity values, encoded as `column:value`. |
| `row_format_issue_count` | Number of row-level format issues for supported fields. |
| `row_format_issues` | Up to 50 row-level format issues, encoded as `rowN:column:value`. |
| `provenance_warning_count` | Number of populated rows with an empty `notes` field when `notes` is present. |
| `provenance_warnings` | Up to 50 provenance warnings, encoded as `rowN:notes_missing`. |
| `validation_status` | Export validation status. |
| `blocking_issue` | Whether the status should block source import. |
| `next_action` | Concrete action to resolve or advance the export. |

## Status Values

| Status | Meaning |
| --- | --- |
| `export_missing` | Expected export path does not exist yet. Non-blocking for scaffold runs. |
| `no_export_path_configured` | Query has no export path and must be manually handled or reconfigured. |
| `export_empty` | Export exists but has no data rows. Non-fatal for scaffold runs but not sufficient for source import, sample support, or H1-H6. |
| `export_missing_expected_columns` | Export lacks one or more expected columns. Blocking. |
| `export_missing_identity_columns` | Export lacks all required identity columns. Blocking. |
| `export_rows_missing_identity` | One or more rows have no identity value. Blocking. |
| `export_duplicate_identity` | One or more identity columns contain duplicate values within the export. Blocking. |
| `export_row_format_invalid` | One or more populated rows contain malformed `year`, `genome_length`, `gc_percent`, or `phage_lifestyle` values. Blocking. |
| `export_ready` | Export exists, has rows, has expected columns, and passes identity and row-format checks. |

## Report Output

Default path: `results/qc/source_export_validation_report.tsv`.

Columns: `severity`, `item`, and `message`.

## Production Use

Run this stage before enabling imports. It prevents malformed reviewed exports from entering source manifests, while allowing the repository to remain runnable before real public data are supplied. Row-level QA currently validates numeric `year`, `genome_length`, and `gc_percent` fields, controlled `phage_lifestyle` values, and missing row provenance in `notes`.

## Scaffold behavior

Header-only skeleton exports are reported as `export_empty` warnings, not fatal validation errors. They are still not ready for import, source enablement, sample support, or H1-H6 interpretation. Populated exports with schema or identity problems remain blocking validation errors.
