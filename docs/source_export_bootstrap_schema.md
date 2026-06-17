# Source Export Bootstrap Schema

`scripts/bootstrap_source_exports.py` creates non-overwriting header-only TSV skeletons at configured reviewed-export paths, usually under `data/metadata/source_exports/`. This is an explicit curation aid, not an analysis stage and not biological evidence. It never modifies `data/raw/` and does not download records.

## Command

```bash
python scripts/bootstrap_source_exports.py \
  --query-plan results/qc/source_query_plan.tsv \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --report-output results/qc/source_export_bootstrap_report.tsv \
  --root .
```

Use `--sources SOURCE_ID ...` to create only selected source skeletons. Use `--force` only before manual curation, because it overwrites existing export files.

## `results/qc/source_export_bootstrap_report.tsv`

| Column | Description |
| --- | --- |
| `source_id` | Configured source identifier. |
| `query_id` | Source-query identifier that supplied the expected export path and columns. |
| `expected_export_path` | Export TSV path created or inspected. |
| `status` | `created_skeleton`, `overwrote_skeleton`, `existing_export_empty`, `existing_export_with_rows`, or skipped status. |
| `header_columns` | Semicolon-delimited columns written to the skeleton. |
| `template_path` | Planning template path used as context, when available. |
| `next_action` | Manual curation or validation action to take next. |

## Interpretation

A created skeleton is not a reviewed source export and should not be interpreted as source support. It only changes the source-curation state from missing file to fillable-but-empty file. Real H1-H6 interpretation still requires reviewed rows, source validation, manifest import, source enablement, sample-support audit, sequence/evidence generation, and model reruns.

The source export validator treats these header-only files as warnings so the config-driven workflow can still run end to end; downstream preflight, sample-support, readiness, and goal-completion audits keep them blocking for biological interpretation.
