# Source Post-Acceptance Transition Schema

`scripts/plan_source_post_acceptance.py` converts source work-order acceptance and source enablement state into the next downstream action for each source. It answers what should happen after reviewed export rows satisfy a work order: enable import, run import, enable catalog, or rerun sample support.

## Command

```bash
python scripts/plan_source_post_acceptance.py \
  --acceptance results/qc/source_work_order_acceptance.tsv \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --enablement-apply results/qc/source_enablement_apply_report.tsv \
  --plan-output results/qc/source_post_acceptance_plan.tsv \
  --report-output results/qc/source_post_acceptance_report.tsv
```

The config-driven workflow runs this stage after `stage_0_source_work_order_acceptance`.

## `results/qc/source_post_acceptance_plan.tsv`

| Column | Description |
| --- | --- |
| `source_id` | Source identifier. |
| `work_order_ids` | Work orders associated with the source. |
| `acceptance_statuses` | Current acceptance statuses. |
| `accepted_work_orders` | Count of accepted work orders. |
| `blocking_work_orders` | Count of work orders still blocking source transition. |
| `enablement_status` | Source enablement status. |
| `import_enabled` | Whether the import config is enabled. |
| `catalog_enabled` | Whether the source catalog entry is enabled. |
| `manifest_row_count` | Current source manifest rows. |
| `transition_status` | Current transition state. |
| `next_command` | Suggested next command, or `NA`. |
| `next_action` | Human-readable action. |

## Transition Statuses

- `waiting_for_work_order_acceptance`: reviewed export rows still do not satisfy work orders.
- `ready_to_enable_import`: accepted rows exist and import config can be enabled.
- `ready_to_run_import`: import is enabled but manifest rows have not yet been generated.
- `ready_to_enable_catalog`: manifest rows exist and the catalog source can be enabled after review.
- `ready_for_sample_support_rerun`: source is enabled and downstream sample support should be rerun.
- `waiting_for_enablement_plan_update`: validation or enablement state needs regeneration.

## Interpretation

This table is an operational transition plan. It does not modify YAML files and does not claim biological support. It helps keep the path from reviewed rows to source manifests, sample support, and H1-H6 tests reproducible.
