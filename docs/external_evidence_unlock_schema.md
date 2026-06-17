# External Evidence Unlock Schema

Stage 1 writes `results/qc/external_evidence_unlock_plan.tsv` to connect downstream external evidence tables to H1-H6. It starts from the external evidence plan and template manifest, then reports which evidence TSVs are still blocking each hypothesis after source and sequence curation.

## Inputs

- `results/qc/external_evidence_plan.tsv`
- `results/qc/external_evidence_template_manifest.tsv`

## Outputs

### `results/qc/external_evidence_unlock_plan.tsv`

One row per hypothesis. Important columns:

- `hypothesis`: H1-H6 identifier.
- `required_evidence_ids`: evidence tables required for a minimum production analysis.
- `ready_required_evidence`: required evidence currently provided and schema-valid.
- `blocking_required_evidence`: required evidence still missing, invalid, waiting for sequence data, or waiting for tools.
- `minimum_unlock_status`: `minimum_evidence_ready` or `blocked_missing_required_evidence`.
- `next_action`: evidence tables to generate/configure next.
- `analysis_layers_unlocked`: downstream workflow layers supported by the evidence set.

### `results/qc/external_evidence_unlock_matrix.tsv`

One row per hypothesis/evidence pair. It records analysis layer, optional workflow input key, evidence status, eligible sequence count, tool status, template path, configured input path, and next action.

### `results/qc/external_evidence_unlock_report.tsv`

Run-level summary with hypothesis, ready, blocked, and matrix row counts.

## Interpretation

This is a planning artifact. Evidence rows are not considered ready until the configured TSV exists, has data rows, and passes schema checks. Sequence-dependent evidence will remain blocked until local genome files pass sequence QC.
