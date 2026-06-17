# Sample Support Source Bridge Schema

`scripts/plan_sample_support_sources.py` maps failed sample-support metrics to source exports that can satisfy them. It is a curation handoff: it does not create biological records and does not replace source review.

## Command

```bash
python scripts/plan_sample_support_sources.py \
  --sample-support-summary results/qc/sample_support_summary.tsv \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --column-dictionary results/qc/source_export_column_dictionary.tsv \
  --bridge-output results/qc/sample_support_source_bridge.tsv \
  --report-output results/qc/sample_support_source_bridge_report.tsv
```

The direct workflow runner executes this after `stage_0_sample_support`.

## `sample_support_source_bridge.tsv`

Columns:

- `metric`: sample-support metric, such as `min_cultured_phages` or `min_k_typed_records`.
- `current_value`: observed count from `sample_support_summary.tsv`.
- `threshold`: configured threshold from `config/thresholds.yaml`.
- `metric_status`: `pass` or `fail`.
- `source_id`: source export that can satisfy the metric.
- `recommended_rank`: rank from `minimum_source_curation_plan.tsv`.
- `record_layer`: source layer, such as `cultured_phages`, `host_genomes`, or `prophages`.
- `expected_record_type`: normalized sample `record_type` expected after import.
- `expected_export_path`: reviewed export path to populate.
- `starter_template_path`: fillable source template.
- `starter_readme_path`: source-specific curation instructions.
- `fields_to_populate`: fields that are most directly relevant to the metric.
- `required_for_hypotheses`: H1-H6 hypotheses that require the source in the minimum source plan.
- `support_rationale`: why this source/field set addresses the metric.
- `next_action`: source-specific curation action.

## `sample_support_source_bridge_report.tsv`

Columns:

- `severity`: `info` or `warning`.
- `item`: report item.
- `message`: run-level summary.

## Interpretation

Use this bridge when `sample_support_by_hypothesis.tsv` has blocked hypotheses. It tells the curator which reviewed exports and columns are expected to repair each missing sample-support metric. Passing this bridge only means the handoff exists; manuscript interpretation still requires populated exports, sequence/evidence generation, quantitative model rows, and readiness passing.
