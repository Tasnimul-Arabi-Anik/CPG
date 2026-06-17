# External Evidence Template Schema

`scripts/create_external_evidence_templates.py` creates header-only TSV templates from `results/qc/external_evidence_plan.tsv`. Templates are written under `results/` and are not treated as production evidence inputs.

## Command

```bash
python scripts/create_external_evidence_templates.py \
  --evidence-plan results/qc/external_evidence_plan.tsv \
  --templates-dir results/qc/external_evidence_templates \
  --manifest-output results/qc/external_evidence_template_manifest.tsv \
  --report-output results/qc/external_evidence_template_report.tsv \
  --root .
```

The direct workflow runner executes this as `stage_1_external_evidence_templates` after external-evidence planning.

## Template Directory

Default path: `results/qc/external_evidence_templates/`.

Each template is named from `evidence_id` and contains only a header row. Required `one_of:` groups are expanded to include all acceptable column names, so the reviewer can retain the column that matches the upstream tool output and leave unused alternatives blank or remove them before final schema validation.

## Manifest Output

Default path: `results/qc/external_evidence_template_manifest.tsv`.

| Column | Description |
| --- | --- |
| `evidence_id` | Evidence identifier from the external evidence plan. |
| `analysis_layer` | Workflow layer supported by the evidence. |
| `hypotheses_supported` | Hypotheses supported by the evidence. |
| `optional_input_key` | Workflow config key that will receive the final evidence TSV path. |
| `configured_input_path` | Currently configured evidence path, if any. |
| `configured_input_exists` | Whether the configured evidence path exists. |
| `configured_input_rows` | Row count of the configured evidence input. |
| `template_path` | Header-only template path under `results/`. |
| `required_columns_spec` | Required column specification copied from the evidence plan. |
| `header_columns` | Columns written to the template. |
| `one_of_groups` | Required alternative column groups. |
| `evidence_status` | Current evidence status from the evidence plan. |
| `template_status` | `template_ready` or `configured_input_ready`. |
| `next_action` | Concrete action to populate/configure evidence. |
| `notes` | Evidence-plan notes. |

## Production Use

Populate a real evidence TSV using the relevant template, save it outside `results/qc/external_evidence_templates/`, and set the matching `inputs.<optional_input_key>` path in `config/workflow.yaml`. The existing external evidence planner then validates row count and minimum schema before downstream analysis uses it.
