# Source Work-Order Acceptance Schema

`scripts/check_source_work_order_acceptance.py` checks whether reviewed source exports satisfy the current source curation work orders. It verifies that the export exists, required columns are present, and enough rows contain the required fields. This is an acceptance check for curation tasks, not a biological result.

## Command

```bash
python scripts/check_source_work_order_acceptance.py \
  --work-orders results/qc/source_curation_work_order.tsv \
  --acceptance-output results/qc/source_work_order_acceptance.tsv \
  --report-output results/qc/source_work_order_acceptance_report.tsv \
  --root .
```

The config-driven workflow runs this stage after `stage_0_source_work_order_packets`.

## `results/qc/source_work_order_acceptance.tsv`

| Column | Description |
| --- | --- |
| `work_order_id` | Work-order identifier. |
| `source_id` | Source being checked. |
| `expected_export_path` | Reviewed export path checked. |
| `export_exists` | Whether the export file exists. |
| `export_row_count` | Number of reviewed export rows. |
| `minimum_rows_to_add` | Minimum rows required by the work order. |
| `required_fields` | Required fields for this work order. |
| `missing_required_columns` | Missing required columns, or `NA`. |
| `satisfying_row_count` | Rows with enough populated values for this work order. |
| `acceptance_status` | `accepted`, `missing_export`, `export_empty`, `missing_required_columns`, or `insufficient_reviewed_rows`. |
| `blocking_issue` | Whether this work order still blocks source curation. |
| `next_action` | Next curation or workflow action. |

## `results/qc/source_work_order_acceptance_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `warning`. |
| `item` | Report item name. |
| `message` | Work-order counts and blocker summary. |

## Interpretation

An accepted work order means the reviewed export appears to satisfy the row and field requirements for that curation task. It does not mean the full project goal is complete. Source export validation, manifest import, source enablement, sample support, external evidence, models, figures, and H1-H6 traceability still need to pass.
