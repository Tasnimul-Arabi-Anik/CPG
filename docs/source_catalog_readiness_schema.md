# Source Catalog Readiness Schema

`scripts/audit_source_catalog.py` checks whether configured source manifests are ready to contribute records to `config/samples.tsv`.
It is a preflight curation audit, separate from the sample builder and Stage 1 manifest validation.

## Command

```bash
python scripts/audit_source_catalog.py \
  --catalog config/source_catalog.yaml \
  --readiness-output results/qc/source_catalog_readiness.tsv \
  --report-output results/qc/source_catalog_audit_report.tsv
```

The direct workflow runner executes this as `stage_0_source_audit` when `source_audit.enabled: true`.

## Outputs

### `source_catalog_readiness.tsv`

| Column | Description |
| --- | --- |
| `source_id` | Source entry identifier from the catalog. |
| `path` | Source manifest path. |
| `enabled` | Whether the sample builder will include this source. |
| `required` | Whether a missing source path is treated as required. |
| `exists` | Whether the source manifest exists. |
| `row_count` | Number of data rows in the source manifest. |
| `recognized_columns` | Output sample columns recognized directly or through aliases. |
| `identity_columns_present` | Configured identity columns found in the source manifest. At least one is required for populated sources. |
| `missing_identity_columns` | Configured identity columns not found in the source manifest. This is informational if at least one identity column is present. |
| `missing_recommended_columns` | Sample columns not recognized in the source manifest. Defaults may still fill some values. |
| `duplicate_genome_ids` | Duplicate IDs detected within the source. |
| `ready_status` | Readiness category. |
| `suggested_action` | Concrete next curation action. |
| `notes` | Catalog notes. |

### `source_catalog_audit_report.tsv`

A short report with `severity`, `item`, and `message` columns.

## Readiness Status Values

| Status | Meaning |
| --- | --- |
| `planned_placeholder` | File exists but has no rows and is disabled. This is expected for planned sources. |
| `populated_disabled` | File has rows but is disabled. Review and enable when ready. |
| `ready_enabled` | File has rows, no duplicate IDs, all recommended columns are recognized, and it is enabled. It will be included by the builder. |
| `ready_with_defaults` | File has rows and at least one identity column, but some recommended metadata columns are missing. The builder can use defaults or `NA`; review before final analysis. |
| `populated_disabled_with_defaults` | File has rows and at least one identity column, but some recommended columns are missing and the source is disabled. |
| `enabled_empty` | File is enabled but contains no rows. Populate or disable it. |
| `missing_identity_columns` | File has rows but lacks all configured identity columns. Add at least one of `genome_id`, `accession`, or `raw_sequence_path` unless overridden in the catalog. |
| `duplicate_ids` | Duplicate genome IDs must be resolved before enabling. |
| `missing_optional` | Optional source path is missing. |
| `missing_required` | Required source path is missing. |
| `invalid_catalog_entry` | Catalog entry is malformed. |

The real scaffold can pass workflow validation while readiness rows are `planned_placeholder`; biological completion still requires populated enabled sources.
