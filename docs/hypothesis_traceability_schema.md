# Hypothesis Traceability Schema

`scripts/12_build_hypothesis_traceability.py` builds an end-to-end H1-H6 matrix that links source readiness, external evidence readiness, sample support, model status, claim status, figures, and readiness state.

## Command

```bash
python scripts/12_build_hypothesis_traceability.py \
  --source-plan results/qc/minimum_hypothesis_source_plan.tsv \
  --evidence-plan results/qc/external_evidence_unlock_plan.tsv \
  --sample-support results/qc/sample_support_by_hypothesis.tsv \
  --hypothesis-summary results/models/hypothesis_summary.tsv \
  --hypothesis-coverage results/validation/hypothesis_coverage.tsv \
  --figure-manifest results/figures/figure_manifest.tsv \
  --readiness results/validation/study_readiness.tsv \
  --trace-output results/validation/hypothesis_traceability.tsv \
  --report-output results/validation/hypothesis_traceability_report.tsv
```

## `hypothesis_traceability.tsv`

Columns:

- `hypothesis`: H1-H6.
- `primary_question`: manuscript-facing hypothesis question.
- `source_unlock_status`: source curation status for the hypothesis.
- `missing_sources`: required sources still missing.
- `external_evidence_status`: external evidence unlock status.
- `missing_evidence`: evidence IDs still missing.
- `sample_support_status`: minimum sample-support status.
- `model_summary_status`: model or quantitative summary status.
- `claim_status`: claim wording status from the model summary.
- `figure_ids`: planned figures associated with the hypothesis.
- `figure_statuses`: current figure source statuses.
- `readiness_status`: overall hypothesis-test readiness row status.
- `overall_trace_status`: `ready`, `limited`, or `blocked`.
- `next_action`: combined next actions from upstream evidence.

## Interpretation

Use this matrix to see why a hypothesis is or is not interpretable. It is stricter than the presence of model rows: source, evidence, sample support, model status, and claim guardrails must align before a hypothesis is considered ready for manuscript-level interpretation.
