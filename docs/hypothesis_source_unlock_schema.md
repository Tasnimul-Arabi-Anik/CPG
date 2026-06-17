# Hypothesis Source Unlock Schema

Stage 0 writes `results/qc/hypothesis_source_unlock_plan.tsv` to connect real-data source curation to the H1-H6 hypothesis tests. It answers which reviewed exports are required before each hypothesis can move from scaffolded tests to populated evidence.

## Inputs

- `results/qc/source_curation_tasks.tsv`

## Outputs

### `results/qc/hypothesis_source_unlock_plan.tsv`

One row per hypothesis. Important columns:

- `hypothesis`: H1-H6 identifier.
- `hypothesis_question`: short hypothesis question.
- `required_source_ids`: source exports required for a minimum real-data test.
- `optional_source_ids`: source exports that strengthen or broaden the analysis but are not required for the first pass.
- `ready_required_sources`: required sources currently ready for sample building.
- `blocking_required_sources`: required sources still blocking the hypothesis.
- `minimum_unlock_status`: `minimum_sources_ready` or `blocked_missing_required_sources`.
- `next_action`: source-level action needed to unlock the hypothesis.
- `analysis_outputs_unlocked`: downstream outputs that become meaningful once minimum sources are ready.

### `results/qc/hypothesis_source_unlock_matrix.tsv`

One row per hypothesis/source pair. It records whether a source is required or optional, its current curation status, export/template paths, and next action.

### `results/qc/hypothesis_source_unlock_report.tsv`

Run-level summary with hypothesis, ready, blocked, and matrix row counts.

## Interpretation

This is a planning artifact. It does not replace populated source exports or downstream model outputs. A hypothesis is still biologically unsupported until source data, sequences, evidence tables, and model/figure outputs are populated and validated.
