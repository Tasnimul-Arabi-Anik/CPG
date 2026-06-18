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

One row per model, quantitative group summary, or explicit assay-dependent blocker. Core rows currently include:

- `predict_K_type`: tests whether phage taxonomy or RBP/depolymerase modules predict capsule type as a K/O association proxy.
- `predict_O_type`: analogous O-type association proxy.
- `prophage_rbp_module_reservoir_summary`: H2 group summary for record type versus RBP module presence.
- `host_background_defense_summary`: H5 group summary for ST versus defense burden.
- `source_novelty_enrichment_summary`: H6 exploratory source/database provenance versus RBP/depolymerase novelty tiers.
- `cluster_novelty_enrichment_summary`: H6 singleton/shared species-like cluster versus RBP/depolymerase novelty status.
- `test_host_range_breadth_association`: H3 blocker row until explicit assay panels provide tested-host denominators and susceptible-host numerators.
- `predict_productive_infection_result`: H4 blocker row until productive-infection, plaque, or EOP outcomes are curated.

The workflow no longer treats `compatibility_feature_status` or `matched_counterdefense_status` as H4 biological targets, because those labels are derived from receptor/defense feature availability rather than observed infection outcomes.

Important status values:

- `ok`: enough classes and samples for the simple baseline.
- `single_class_uninformative`: labels exist but only one class is present.
- `too_few_samples_interpret_with_caution`: labels exist but sample size is very small.
- `no_labeled_samples`: no usable labeled samples for that task.
- `insufficient_groups_for_rate_test`: group summary lacks enough groups or classes.
- `blocked_no_host_range_breadth_labels`: H3 cannot be tested until assay panels provide host-range breadth labels.
- `blocked_no_productive_infection_labels`: H4 cannot be tested until productive-infection, plaque, or EOP labels exist.

### `results/models/feature_importance.tsv`

Feature contribution is reported as leave-one-feature-out delta accuracy for model rows. For group summaries, it records group counts and top-label fractions.

### `results/models/prediction_errors.tsv`

One row per leave-one-out prediction with true label, predicted label, fallback status, and feature values used.

### `results/models/hypothesis_summary.tsv`

One row per main hypothesis H1-H6. This table is the manuscript-facing bridge between the detailed model outputs and the claim ledger. It records the primary question, required test, matching model rows, ok/limited row counts, sample support, primary metric, comparison metric, effect size, summary status, claim status, interpretation guardrail, and next action.

### `results/models/model_report.tsv`

Run-level validation and provenance messages.

## Current Behavior

These models are transparent scaffolds, not final host-range predictors. Accuracy values from tiny, metadata-biased, or single-class datasets should be interpreted as pipeline checks rather than biological conclusions. H3 and H4 blocked rows are deliberate scientific safeguards, not software failures.
