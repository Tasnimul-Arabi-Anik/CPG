# Source Curation Issue Body Schema

`scripts/create_source_curation_issue_bodies.py` converts `results/qc/source_curation_work_order.tsv` into GitHub-ready Markdown issue bodies. The generated files are handoff artifacts only; the script does not call GitHub and does not create or modify source exports.

## Command

```bash
python scripts/create_source_curation_issue_bodies.py \
  --work-orders results/qc/source_curation_work_order.tsv \
  --issue-dir results/qc/github_issue_bodies \
  --manifest-output results/qc/source_curation_issue_manifest.tsv \
  --commands-output results/qc/source_curation_issue_commands.tsv \
  --shell-output results/qc/source_curation_issue_commands.sh \
  --report-output results/qc/source_curation_issue_report.tsv
```

Use `--max-issues 1` to render only the highest-ranked current work order.

## `results/qc/source_curation_issue_manifest.tsv`

| Column | Description |
| --- | --- |
| `work_order_id` | Source curation work-order identifier. |
| `source_id` | Source being curated. |
| `issue_title` | Suggested GitHub issue title. |
| `issue_body_path` | Markdown issue body path under `results/`. |
| `labels` | Suggested labels. |
| `expected_export_path` | Reviewed export path to populate. |
| `required_for_hypotheses` | H1-H6 hypotheses affected by the source. |
| `minimum_rows_to_add` | Minimum reviewed rows requested by the work order. |
| `required_fields` | Fields that must be populated for acceptance. |

## `results/qc/source_curation_issue_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `warning`. |
| `item` | Report item name. |
| `message` | Rendered issue count summary. |

## Interpretation

Generated issue bodies are operational curation handoffs. They are not biological evidence and do not authorize host-range, receptor-specificity, anti-defense, or therapeutic claims.
