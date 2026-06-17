# Goal Completion Audit Schema

`scripts/11_audit_goal_completion.py` audits the original project objective against current workflow evidence. It runs after workflow validation, study readiness, and readiness action planning.

## Command

```bash
python scripts/11_audit_goal_completion.py \
  --root . \
  --results-dir results \
  --audit-output results/validation/goal_completion_audit.tsv \
  --report-output results/validation/goal_completion_report.tsv
```

## `goal_completion_audit.tsv`

Columns:

- `requirement_id`: stable objective-level requirement ID.
- `objective_requirement`: completion requirement derived from the active project goal.
- `evidence_paths`: files used as direct evidence.
- `evidence_summary`: quantitative summary of the evidence.
- `status`: `pass`, `warn`, or `fail`.
- `blocking_for_goal`: whether the row blocks marking the full goal complete.
- `next_action`: concrete action needed when incomplete.

Current requirements check that the workflow runs from config, outputs are under `results/` with valid schemas, H1-H6 have passing quantitative tests, audited sample support is sufficient, study readiness has no blocking rows, and documentation/claims/limitations/figures pass validation.

## `goal_completion_report.tsv`

Columns:

- `severity`: `info` or `warning`.
- `item`: report item.
- `message`: pass/warn/fail/blocking summary.

## Interpretation

This audit is intentionally stricter than workflow validation. A scaffold can pass script/schema validation while this audit still fails because real data, sample support, external evidence, or H1-H6 ok rows are missing. The active goal should only be marked complete when every objective-level row passes and `blocking_for_goal` is `false` for all rows.
