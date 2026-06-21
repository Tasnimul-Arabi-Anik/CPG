# Assay Feature Coverage Schema

`results/<profile>/qc/assay_feature_coverage.tsv` is written by Stage 7 (`scripts/06_compare_feature_models.py`). It audits whether reviewed phage-host assay outcomes have the biological feature evidence needed for H1b, H3, and H4 interpretation.

## Columns

| Column | Description |
| --- | --- |
| `metric` | Coverage metric, such as `host_K_type`, `rbp_candidates`, `receptor_layer_feature_completeness`, or `spot_breadth_continuous`. |
| `entity_level` | Denominator level: `unique_phage`, `unique_host`, `pair`, or `phage_panel`. |
| `numerator` | Count with the metric present, or spot-positive count for `spot_breadth_continuous`. |
| `denominator` | Count eligible for the metric, or tested-host count for `spot_breadth_continuous`. |
| `coverage_fraction` | `numerator / denominator`, formatted to three decimals. |
| `evidence_state` | Evidence interpretation: `not_assessed`, `assessed_positive`, `assessed_zero_detected`, `evidence_rejected`, or `descriptive_breadth_available`. Missing analysis must not be interpreted as biological zero. |
| `blocking_hypotheses` | Hypotheses blocked or informed by the metric. |
| `next_action` | Concrete action needed to improve coverage or interpretation. |
| `study_id`, `panel_id`, `phage_id`, `host_id` | Optional identifiers for per-panel or pair-specific rows. |
| `tested_host_count` | Number of tested hosts in a phage-panel breadth row. |
| `spot_positive_host_count` | Number of spot-positive hosts in a phage-panel breadth row. |
| `spot_positive_fraction` | Continuous spot-positive fraction for a phage-panel breadth row. |
| `spot_positive_fraction_ci95_low` | Wilson 95% confidence interval lower bound for the observed tested-panel spot-positive proportion. |
| `spot_positive_fraction_ci95_high` | Wilson 95% confidence interval upper bound for the observed tested-panel spot-positive proportion. |

## Interpretation

The table is an analysis-readiness audit, not a result claim. For the PhageHostLearn benchmark, spot-test outcomes are real initial-interaction observations, and the production profile now has reviewed host K/O result rows, partial ST context, baseline Prodigal CDS predictions for assay phages, and exact RBPbase ML candidate matches for 103/105 assay phages. Domain/structural evidence, defense/counter-defense evidence, verified host raw-sequence paths, and productive-infection evidence remain separately gated; missing phage-side functional or defense analysis must not be interpreted as feature absence.
