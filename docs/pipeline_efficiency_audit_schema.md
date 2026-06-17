# Pipeline Efficiency Audit Schema

`scripts/audit_pipeline_efficiency.py` writes a reviewer-facing audit of production-scope and computational-efficiency safeguards. The audit is intended to answer whether the workflow avoids naive public-data scraping, redundant counting, uncontrolled raw-data writes, and bridge-evidence overclaiming.

Default outputs:

- `results/validation/pipeline_efficiency_audit.tsv`
- `results/validation/pipeline_efficiency_report.tsv`

## `pipeline_efficiency_audit.tsv`

| Column | Description |
| --- | --- |
| `check_id` | Stable audit check identifier. |
| `area` | Pipeline area being audited. |
| `reviewer_question` | Reviewer-facing concern addressed by the check. |
| `evidence_path` | Config, plan, or output used as evidence. |
| `evidence_summary` | Compact summary of the observed state. |
| `status` | `pass`, `warn`, or `fail`. |
| `blocking_for_efficiency` | Whether the issue blocks an efficiency/scope claim. |
| `recommendation` | Next action or guardrail to preserve. |

## `pipeline_efficiency_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item, usually `pipeline_efficiency`. |
| `message` | Summary count of pass, warn, and fail checks. |

## Interpretation

A passing audit supports a workflow-design claim that the project uses staged reviewed source curation, dereplication, source-overlap auditing, and externalized production evidence. It does not support biological conclusions. Biological claims still require populated source rows, sequence-backed records, production external evidence, model support, and claim-support audit approval.
