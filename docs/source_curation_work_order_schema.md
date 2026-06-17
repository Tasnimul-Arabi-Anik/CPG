# Source Curation Work Order Schema

`scripts/build_source_curation_work_order.py` converts the ranked source readiness dashboard and sample-support summary into concrete source-curation work orders. Each work order identifies the reviewed export to fill, the minimum number of rows needed for the current configured thresholds, the required fields, and the validation command to rerun after curation.

## Command

```bash
python scripts/build_source_curation_work_order.py \
  --dashboard results/qc/source_readiness_dashboard.tsv \
  --sample-support-summary results/qc/sample_support_summary.tsv \
  --work-order-output results/qc/source_curation_work_order.tsv \
  --report-output results/qc/source_curation_work_order_report.tsv
```

The config-driven workflow runs this stage after `stage_0_source_readiness_dashboard`.

## `results/qc/source_curation_work_order.tsv`

| Column | Description |
| --- | --- |
| `work_order_id` | Stable work-order identifier for the current run. |
| `source_id` | Source to curate. |
| `recommended_rank` | Rank from the source readiness dashboard. |
| `record_layer` | Source layer. |
| `expected_export_path` | Reviewed export path to fill. |
| `required_for_hypotheses` | H1-H6 hypotheses affected by the source. |
| `curation_priority` | Priority label inherited from the source readiness dashboard. |
| `blocked_metrics` | Sample-support metrics this source can help satisfy. |
| `required_fields` | Fields that must be populated in reviewed rows. |
| `minimum_rows_to_add` | Minimum number of reviewed rows needed under current sample-support thresholds. |
| `current_export_rows` | Current row count in the reviewed export. |
| `current_satisfying_rows` | Current number of metric-satisfying rows across preflight checks. |
| `completion_check` | How to confirm the work order has been resolved. |
| `validation_command` | Focused workflow command to rerun after curation. |
| `next_action` | Human-readable next action from the dashboard. |

## `results/qc/source_curation_work_order_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `warning`. |
| `item` | Report item name. |
| `message` | Count summary and first recommended work order. |

## Interpretation

Work orders are operational curation tasks, not biological evidence. Completing a work order requires adding reviewed source rows, rerunning validation/import/enablement/sample-support checks, and confirming the source no longer appears with the same curation blocker.
