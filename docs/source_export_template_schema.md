# Source Export Template Schema

`scripts/create_source_export_templates.py` creates header-only TSV templates from `results/qc/source_query_plan.tsv`. Templates are written under `results/` so the workflow does not create fake production exports under `data/metadata/source_exports/`.

## Command

```bash
python scripts/create_source_export_templates.py \
  --query-plan results/qc/source_query_plan.tsv \
  --templates-dir results/qc/source_export_templates \
  --manifest-output results/qc/source_export_template_manifest.tsv \
  --report-output results/qc/source_export_template_report.tsv
```

The direct workflow runner executes this as `stage_0_source_export_templates` after source-query planning.

## Template Directory

Default path: `results/qc/source_export_templates/`.

Each file is named from `query_id` and contains only a header row. The header is the union of `expected_columns` and `identity_columns_required` from the source query plan.

## Manifest Output

Default path: `results/qc/source_export_template_manifest.tsv`.

| Column | Description |
| --- | --- |
| `query_id` | Query identifier from the source query plan. |
| `source_id` | Matching source catalog identifier. |
| `record_layer` | Study layer represented by the source. |
| `target_database` | Public database, local export, or manual source. |
| `template_path` | Header-only TSV template under `results/`. |
| `expected_export_path` | Reviewed production export path expected by source imports. |
| `expected_export_exists` | Whether the production export path already exists. |
| `expected_export_row_count` | Number of rows currently present in the production export. |
| `header_columns` | Columns written to the template. |
| `identity_columns_required` | Identity columns required by the query/import handoff. |
| `identity_columns_in_template` | Required identity columns present in the generated template. |
| `missing_identity_columns` | Required identity columns missing from the generated template. |
| `review_priority` | Priority from the query plan. |
| `template_status` | Current template status. |
| `next_action` | Concrete action for moving from template to reviewed export. |
| `notes` | Query-plan notes. |

## Status Values

| Status | Meaning |
| --- | --- |
| `template_ready` | Template has required identity headers and awaits reviewed data rows. |
| `export_already_populated` | Expected production export already exists with data rows. |
| `template_missing_identity_column` | Query config needs correction before template use. |

## Production Use

The template files are not production inputs. Populate reviewed exports at the `expected_export_path` listed in the manifest, then run source import and source acquisition planning. This separation avoids accidentally treating empty templates as biological data.

## Related Validation

After templates are generated and reviewed exports are populated, `scripts/validate_source_exports.py` writes `results/qc/source_export_validation.tsv` to check headers, identity values, and duplicate identities before import.

## Column Dictionary

`results/qc/source_export_column_dictionary.tsv` is generated from the template manifest. It explains source/template columns, identity requirements, expected formats, missing-value policy, and downstream validation notes for each reviewed export.
