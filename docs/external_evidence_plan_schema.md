# External Evidence Plan Schema

`scripts/plan_external_evidence.py` creates a local-only checklist for production evidence tables required by dereplication, annotation, RBP/depolymerase discovery, host feature integration, and defense/counter-defense analysis. It does not run external tools and does not download data.

## Command

```bash
python scripts/plan_external_evidence.py \
  --workflow-config config/workflow.yaml \
  --tool-availability results/qc/tool_availability.tsv \
  --manifest results/qc/phage_genome_manifest.tsv \
  --sequence-qc results/qc/genome_sequence_qc.tsv \
  --plan-output results/qc/external_evidence_plan.tsv \
  --report-output results/qc/external_evidence_report.tsv \
  --root .
```

The direct runner executes this as `stage_1_external_evidence_plan` after sequence QC and before dereplication.

## Plan Output

Default path: `results/qc/external_evidence_plan.tsv`.

| Column | Description |
| --- | --- |
| `evidence_id` | Planned evidence table, for example `pairwise_similarity`, `phage_annotation`, `kaptive_ko_typing`, or `host_defense_systems`. |
| `analysis_layer` | Workflow layer that consumes the evidence. |
| `hypotheses_supported` | Hypotheses that depend on this evidence. |
| `optional_input_key` | `config/workflow.yaml` input key that can provide a precomputed TSV. |
| `configured_input_path` | Current configured optional input path, if any. |
| `configured_input_exists` | Whether the configured input path exists. |
| `configured_input_rows` | Number of data rows in the configured input. |
| `configured_input_schema_status` | `pass`, `fail`, or `not_checked` for the minimum required evidence schema. |
| `configured_input_required_columns` | Semicolon-delimited required columns, including `one_of:` groups for acceptable identifier alternatives. |
| `configured_input_missing_columns` | Missing required columns or missing `one_of:` groups. |
| `required_sequence_scope` | Required sequence-backed records: `phage_like` or `host`. |
| `eligible_sequence_records` | Number of passing sequence-QC records in the required scope. |
| `tool_ids` | Planned tools associated with this evidence. |
| `tool_status` | Availability status from `results/qc/tool_availability.tsv`. |
| `evidence_status` | Current readiness state. |
| `blocking_for_manuscript` | Whether this evidence is required for manuscript-ready claims. |
| `next_action` | Immediate next action. |
| `suggested_command` | Command hint or handoff description. It is not executed by the workflow. |
| `notes` | Why the evidence matters. |

## Minimum Schema Checks

The planner validates only the minimum columns required by downstream scripts. Pairwise similarity requires `genome_id_1`, `genome_id_2`, `identity_percent`, `coverage_percent`, and `method`. Phage annotation requires `genome_id`, `gene_id`, and `product`. RBP domain and structural evidence require their gene identifier plus domain/structural hit identifier and name. Host-feature and defense evidence allow common identifier alternatives through `one_of:` groups so tool-specific exports can be normalized without unnecessary column renaming.

## Status Values

| Status | Meaning |
| --- | --- |
| `provided_input_ready` | A configured optional TSV exists and has data rows. |
| `configured_input_empty` | The configured TSV exists but contains no data rows. |
| `configured_input_missing` | The workflow points to a TSV path that does not exist. |
| `configured_input_schema_invalid` | The configured TSV has rows but lacks required columns for that evidence type. |
| `waiting_for_sequence_data` | No suitable sequence-backed records exist yet. |
| `ready_to_run_external_tool` | Required sequence data exist and at least one planned tool is available. |
| `missing_tool_or_input` | Sequence data exist, but the planned tools are missing and no TSV is configured. |
| `manual_evidence_required` | The evidence must be supplied by a manual or currently unconfigured external analysis. |

## Production Use

Use this table after sequence QC. For final analyses, evidence rows should usually be `provided_input_ready`, meaning a reviewed TSV is configured under `inputs` in `config/workflow.yaml`. Tool commands are advisory because external tool installation, databases, and HPC paths are environment-specific.

## Related Templates

After this plan is generated, `scripts/create_external_evidence_templates.py` writes `results/qc/external_evidence_template_manifest.tsv` and header-only TSVs under `results/qc/external_evidence_templates/` for each planned evidence input.

## Evidence Unlock Planning

`results/qc/external_evidence_unlock_plan.tsv` and `results/qc/external_evidence_unlock_matrix.tsv` map external evidence readiness to H1-H6. They show which evidence TSVs are blocking each hypothesis after source and sequence curation.
