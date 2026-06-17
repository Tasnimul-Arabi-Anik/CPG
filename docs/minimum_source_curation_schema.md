# Minimum Source Curation Schema

Stage 0 writes minimum source curation plans after source-export starter-kit generation and H1-H6 source unlock planning. These files rank reviewed source exports by how many hypotheses they unblock and record the exact minimum source set for each hypothesis.

## `results/qc/minimum_source_curation_plan.tsv`

One row per configured source. Important columns:

| Column | Description |
| --- | --- |
| `source_id` | Source export identifier. |
| `recommended_rank` | Suggested curation order; lower ranks unblock more required H1-H6 source sets. |
| `record_layer` | Cultured phages, prophages, host genomes, literature-curated phages, or optional discovery. |
| `review_priority` | Source priority from query/source configuration. |
| `curation_status` | Current source curation status. |
| `required_for_hypotheses` | H1-H6 hypotheses for which this source is required. |
| `optional_for_hypotheses` | H1-H6 hypotheses where this source is useful but not minimum-required. |
| `required_hypothesis_count` | Number of minimum hypothesis source sets containing this source. |
| `starter_readme_path` | Per-source curation instructions. |
| `starter_template_path` | Fillable source export header. |
| `expected_export_path` | Reviewed export path to populate. |
| `identity_columns_required` | Identity columns accepted by validation. |
| `validation_command` | Command to rerun after population. |
| `recommended_action` | Source-specific next step. |
| `rationale` | Why this source has its rank. |

## `results/qc/minimum_hypothesis_source_plan.tsv`

One row per hypothesis. It records the minimum required source set, still-missing sources, starter READMEs, expected export paths, unlock status, and analysis outputs affected.

## `results/qc/minimum_source_curation_report.tsv`

Run-level summary of source count, required source count, hypothesis count, and blocked hypothesis count.

## Interpretation

This plan prioritizes manual source curation. It does not reduce the final study scope and does not support biological claims until reviewed exports, sequences, external evidence, models, and figures are populated and validated.
