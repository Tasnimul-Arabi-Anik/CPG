# Sample Support Export Preflight Schema

`scripts/preflight_sample_support_exports.py` checks reviewed source exports against the metric-specific requirements listed in `results/qc/sample_support_source_bridge.tsv`. It runs after the bridge stage and before downstream manifest generation.

## Command

```bash
python scripts/preflight_sample_support_exports.py \
  --bridge results/qc/sample_support_source_bridge.tsv \
  --preflight-output results/qc/sample_support_export_preflight.tsv \
  --report-output results/qc/sample_support_export_preflight_report.tsv \
  --root .
```

## `sample_support_export_preflight.tsv`

Columns:

- `metric`: sample-support metric being checked.
- `source_id`: reviewed export source.
- `recommended_rank`: source rank from the minimum source curation plan.
- `expected_export_path`: reviewed export TSV path.
- `export_exists`: whether the export file exists.
- `export_row_count`: number of data rows in the export.
- `fields_to_populate`: metric-critical fields from the source bridge.
- `missing_fields`: metric-critical fields absent from the export header.
- `satisfying_row_count`: rows with enough populated fields to satisfy this metric/source combination.
- `preflight_status`: `missing_export`, `missing_metric_fields`, `empty_export`, `no_metric_supporting_rows`, or `metric_support_ready`.
- `blocking_issue`: `true` when the metric/source combination cannot yet support sample generation.
- `next_action`: concrete curation action.

## `sample_support_export_preflight_report.tsv`

Columns:

- `severity`: `info` or `warning`.
- `item`: report item.
- `message`: run-level summary.

## Interpretation

This preflight is stricter and more targeted than the generic source export preflight. It asks whether the reviewed exports contain fields and values that can repair failed sample-support metrics. Passing this preflight does not replace source export validation, import review, sequence QC, external evidence generation, or manuscript-readiness checks.
