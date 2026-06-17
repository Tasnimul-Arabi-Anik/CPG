# Priority Source Preflight Schema

Stage 0 writes priority source export preflight outputs for the highest-ranked source exports in `results/qc/minimum_source_curation_plan.tsv`. By default the workflow checks ranks 1-2, currently INPHARED cultured phages and Klebsiella host genomes.

## `results/qc/priority_source_export_preflight.tsv`

One row per preflighted source. Important columns:

| Column | Description |
| --- | --- |
| `source_id` | Source identifier. |
| `recommended_rank` | Rank from the minimum source curation plan. |
| `record_layer` | Source record layer. |
| `required_for_hypotheses` | H1-H6 hypotheses requiring this source. |
| `expected_export_path` | Reviewed export TSV path to check. |
| `export_exists` | Whether the reviewed export exists. |
| `export_row_count` | Number of data rows if present. |
| `preflight_status` | `missing_export`, `blocking_issues`, `ready_with_warnings`, or `preflight_ready`. |
| `blocking_issue_count` | Number of blocking source/row issues. |
| `warning_count` | Number of non-blocking metadata warnings. |
| `identity_columns_required` | Accepted identity columns. |
| `required_content_checks` | Recommended downstream metadata fields checked for this record layer. |
| `next_action` | Next curation step. |

## `results/qc/priority_source_export_preflight_issues.tsv`

One row per source-level or row-level issue. Important columns:

| Column | Description |
| --- | --- |
| `source_id` | Source identifier. |
| `recommended_rank` | Source priority rank. |
| `row_number` | Export row number, or `NA` for file/header issues. |
| `issue_severity` | `blocking` or `warning`. |
| `issue_code` | Stable issue category. |
| `field` | Affected field or fields. |
| `message` | Human-readable issue description. |

## `results/qc/priority_source_export_preflight_report.tsv`

Run-level summary with number of checked sources, ready sources, blocking issues, warnings, and configured max rank.

## Interpretation

Preflight is intentionally narrower and earlier than full source export validation. It focuses manual curation on the highest-leverage exports before import/catalog enablement. Passing preflight does not replace source export validation, source import review, sequence QC, external evidence generation, or manuscript-readiness checks.
