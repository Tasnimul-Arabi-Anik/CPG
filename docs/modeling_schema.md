# Model Comparison Schema

Stage 7 compares interpretable feature sets for the study hypotheses. It is deliberately conservative: it uses pure-Python leave-one-out exact-match baselines and group summaries so the workflow can run before larger datasets and specialized modeling dependencies are available.

## Inputs

Primary inputs:
- `results/qc/phage_genome_manifest.tsv`
- `results/clusters/phage_clusters.tsv`
- `results/rbp_depolymerase/candidates.tsv`
- `results/host_features/phage_host_links.tsv`
- `results/defense_systems/compatibility_features.tsv`

## Outputs

### `results/models/model_comparison.tsv`

One row per model or quantitative hypothesis summary. Core model rows compare feature sets for:

- `predict_K_type`: tests whether phage taxonomy or RBP/depolymerase modules predict capsule type.
- `predict_O_type`: analogous O-type prediction.
- `predict_compatibility_feature_status`: compares receptor, defense, counter-defense, and combined feature sets.
- `predict_matched_counterdefense_status`: tests whether combined defense/counter-defense features identify matched counter-defense targets.

- `source_novelty_enrichment_summary`: tests whether source strata are associated with RBP/depolymerase novelty tiers.
- `cluster_novelty_enrichment_summary`: tests whether singleton/shared species-like clusters differ in RBP/depolymerase novelty status.

Additional group summaries track H2, H3, H5, and H6 as quantitative scaffold tests.

Important status values:

- `ok`: enough classes and samples for the simple baseline.
- `single_class_uninformative`: labels exist but only one class is present.
- `too_few_samples_interpret_with_caution`: labels exist but sample size is very small.
- `no_labeled_samples`: no usable labeled samples for that task.
- `insufficient_groups_for_rate_test`: group summary lacks enough groups or classes.

### `results/models/feature_importance.tsv`

Feature contribution is reported as leave-one-feature-out delta accuracy for model rows. For group summaries, it records group counts and top-label fractions.

### `results/models/prediction_errors.tsv`

One row per leave-one-out prediction with true label, predicted label, fallback status, and feature values used.

### `results/models/hypothesis_summary.tsv`

One row per main hypothesis H1-H6. This table is the manuscript-facing bridge between the detailed model outputs and the claim ledger. It records the primary question, required test, matching model rows, ok/limited row counts, sample support, primary metric, comparison metric, effect size, summary status, claim status, interpretation guardrail, and next action.

### `results/models/model_report.tsv`

Run-level validation and provenance messages.

## Current Behavior

These models are transparent scaffolds, not final host-range predictors. Accuracy values from tiny, metadata-biased, or single-class datasets should be interpreted as pipeline checks rather than biological conclusions.
