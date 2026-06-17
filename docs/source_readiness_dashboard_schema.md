# Source Readiness Dashboard Schema

`scripts/build_source_readiness_dashboard.py` merges source export validation, source enablement planning, enablement dry-run status, and sample-support export preflight into one ranked curation table. It is designed to show the next source rows and fields that must be curated before H1-H6 sample support can pass.

## Command

```bash
python scripts/build_source_readiness_dashboard.py \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --source-export-validation results/qc/source_export_validation.tsv \
  --source-enablement-plan results/qc/source_enablement_plan.tsv \
  --source-enablement-apply results/qc/source_enablement_apply_report.tsv \
  --sample-support-preflight results/qc/sample_support_export_preflight.tsv \
  --dashboard-output results/qc/source_readiness_dashboard.tsv \
  --report-output results/qc/source_readiness_dashboard_report.tsv
```

The config-driven workflow runs this stage after `stage_0_sample_support_export_preflight`.

## `results/qc/source_readiness_dashboard.tsv`

| Column | Description |
| --- | --- |
| `source_id` | Source identifier. |
| `recommended_rank` | Rank from the minimum source curation plan. |
| `record_layer` | Source layer, such as cultured phages, host genomes, prophages, or metagenomic discovery. |
| `required_for_hypotheses` | H1-H6 hypotheses for which this source is part of the minimum source set. |
| `expected_export_path` | Reviewed export path to curate. |
| `export_exists` | Whether the reviewed export file exists. |
| `export_row_count` | Number of reviewed export rows. |
| `validation_status` | Status from source export validation. |
| `enablement_status` | Status from source enablement planning. |
| `enablement_action_status` | Dry-run action result from source enablement apply report. |
| `blocked_metric_count` | Number of sample-support metric/source combinations still blocked. |
| `blocked_metrics` | Semicolon-delimited blocked sample-support metrics. |
| `fields_to_populate` | Union of fields needed to satisfy blocked metrics for this source. |
| `satisfying_row_count_total` | Sum of rows currently satisfying source/metric preflight checks. |
| `curation_priority` | Dashboard-level priority label. |
| `next_action` | Concrete next curation action. |

## `results/qc/source_readiness_dashboard_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `warning`. |
| `item` | Report item name. |
| `message` | Summary counts and curation warning. |

## Interpretation

The dashboard is a curation handoff, not biological evidence. Sources with `populate_reviewed_rows`, `create_reviewed_export`, or `fix_export_validation` must be completed before source import, source enablement, sample support, and hypothesis interpretation can pass.
