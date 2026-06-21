# Remote AI Evaluation Handoff

## Purpose

This repository is being built into a reproducible Klebsiella phage comparative genomics study. The main scientific question is whether phage-host spot-test host range is better explained by receptor-layer features, especially RBP/depolymerase module architecture plus host K/O type, than by whole-genome phage taxonomy or genome similarity alone.

The broader long-term hypothesis has two filters:

1. Receptor compatibility: phage RBP/depolymerase features versus host capsule/LPS K/O features.
2. Intracellular compatibility: bacterial defense systems versus phage counter-defense genes.

Current real quantitative work is focused on the first filter. The second-filter H4 defense/counter-defense analysis remains blocked because productive-infection/plaque/EOP outcomes and accepted defense/counter-defense evidence are not yet available.

## Current Data Layer

- Assay source: PhageHostLearn 2024 benchmark.
- Tested spot-assay pairs: 10,006.
- Spot-positive pairs: 333.
- Spot-negative pairs: 9,673.
- Assay phages: 105.
- Assay hosts: 200.
- Endpoint: spot-test initial interaction.
- Productive infection: not measured.

Important interpretation boundary: spot-positive does not prove productive infection.

## Current Feature Evidence

Host receptor/background features:

- Kaptive K/O evidence covers the assay host layer.
- Kleborate host features cover most assay hosts.
- These features support receptor-layer exploratory modeling, not therapeutic claims.

Phage receptor-side evidence:

- PhageHostLearn RBPbase source candidates: 274 proteins across 105 assay phages.
- Current Prodigal exact CDS matches to RBPbase candidates: 247 proteins across 103 assay phages.
- Missing exact RBPbase matches: 27 proteins across 24 phages.
- BLASTP review of the 27 missing exact matches:
  - 25 near-identical same-phage hits.
  - 2 strong same-phage hits.
  - 23 have RBPbase `xgb_score >= 0.9`.
  - Interpretation: mostly start/stop or gene-boundary differences, not biological absence.
- Boundary-reviewed RBPbase feature count used in regenerated local matrix: 274 candidates.
- Exact and boundary-reviewed RBPbase features are kept as separate model columns.
- Pharokka receptor-like keyword rows: 213.
- Phold/Foldseek receptor-like feature rows: 236.
- Non-Pharokka Phold/Foldseek receptor-like rows: 23.
- High-priority non-Pharokka Phold/Foldseek manual-review candidates: 8.

Important interpretation boundary: RBPbase, Pharokka, and Phold/Foldseek rows are candidate-prioritization evidence. They do not prove capsule specificity, depolymerase activity, or infection success.

## Current H1 Modeling Result

A grouped, interpretable rate-baseline H1 benchmark has been run on the 10,006 spot-test pairs.

Split strategies:

- Cold phage.
- Cold host.
- Cold phage cluster.
- Cold K-locus.

Model families include:

- Global prevalence.
- Phage marginal rate.
- Host marginal rate.
- Host K/K-O rates.
- Phage taxonomy/cluster rate.
- BLASTN nearest-phage genome-similarity rates.
- Mash nearest-phage genome-similarity rates in a separate robustness run.
- RBPbase/Pharokka/Phold receptor-feature rate models.
- Receptor plus host K/O models.
- Combined receptor plus host K/O plus cluster models.

Primary current comparison:

- Model: receptor plus host K/O rate.
- Baseline: BLASTN nearest-phage plus host K/O rate.
- Primary split: cold phage cluster.
- Metric: tie-aware pooled out-of-fold average precision.

Current result after adding boundary-reviewed RBPbase features:

- Boundary-reviewed RBPbase vs exact RBPbase:
  - Cold phage delta AP: +0.020282, group CI95 [0.007731, 0.044222].
  - Cold phage cluster delta AP: +0.019078, group CI95 [0.001008, 0.054781].
  - Cold host delta AP: -0.004975, group CI95 [-0.019879, 0.007144].
  - Cold K-locus delta AP: 0.000000.
- Boundary-reviewed receptor union vs exact receptor union:
  - Cold phage cluster delta AP: -0.000427, group CI95 [-0.025381, 0.023545].
  - Cold phage delta AP: +0.008034, group CI95 [-0.014805, 0.028508].
  - No robust improvement over exact-union receptor features.
- Boundary-reviewed receptor union vs BLASTN nearest-phage plus host K/O:
  - Cold phage cluster delta AP: -0.055210, group CI95 [-0.136977, 0.025160].
  - Cold K-locus delta AP: -0.105792, group CI95 [-0.159033, -0.071987].
  - Cold host delta AP: -0.160134, group CI95 [-0.211350, -0.103932].
  - Cold phage delta AP: -0.044059, group CI95 [-0.117824, 0.037105].

Current interpretation:

Boundary review corrects RBPbase undercounting and modestly improves the RBPbase-only feature in cold-phage and cold-cluster splits. It does not make the receptor-feature union outperform the BLASTN nearest-phage plus host K/O baseline in the PhageHostLearn spot-test benchmark. This remains an exploratory benchmark result, not an independent external validation.

Mash robustness check:

- Mash version: 2.3 via the `pharokka` conda environment.
- Mash settings: k=21, sketch size=10,000, 105 assay phage FASTAs, 5,460 pairwise rows.
- Mash nearest-phage plus host K/O AP values:
  - Cold phage: 0.173394.
  - Cold phage cluster: 0.171850.
  - Cold K-locus: 0.108173.
  - Cold host: 0.241952.
- Boundary-reviewed receptor union vs Mash nearest-phage plus host K/O:
  - Cold phage delta AP: -0.030493, group CI95 [-0.105525, 0.048526].
  - Cold phage cluster delta AP: -0.031210, group CI95 [-0.112510, 0.046527].
  - Cold K-locus delta AP: -0.080124, group CI95 [-0.116660, -0.053539].
  - Cold host delta AP: -0.143820, group CI95 [-0.192475, -0.094618].
- Interpretation: Mash is a weaker nearest-phage baseline than the current BLASTN table in AP, but the receptor union still does not robustly outperform Mash nearest-phage plus host K/O.

## Locally Generated Outputs

Generated outputs are under `results/`, which is ignored by Git. Key local outputs include:

- `results/production/model_inputs/receptor_layer_pairwise_features.tsv`
- `results/production/models/receptor_layer_model_comparison.tsv`
- `results/production/models/receptor_layer_out_of_fold_predictions.tsv`
- `results/production/models/receptor_layer_model_pooled_summary.tsv`
- `results/production/models/receptor_layer_feature_source_ablation.tsv`
- `results/production/models/receptor_layer_group_bootstrap_delta.tsv`
- `results/production/phage_similarity/mash_pairwise_similarity.tsv`
- `results/production/models/mash_similarity/receptor_layer_model_pooled_summary.tsv`
- `results/production/models/mash_similarity/receptor_layer_group_bootstrap_delta.tsv`
- `results/production/models/mash_similarity/mash_vs_blastn_similarity_baseline_summary.tsv`
- `results/production/receptor_features/receptor_source_reconciliation.tsv`
- `results/production/receptor_features/receptor_source_reconciliation_missing_rbpbase.tsv`
- `results/production/receptor_features/receptor_source_reconciliation_summary.tsv`
- `results/production/receptor_features/phold_non_pharokka_receptor_review.tsv`
- `results/production/receptor_features/phold_non_pharokka_receptor_review_summary.tsv`
- `results/production/receptor_features/missing_rbpbase_review/missing_rbpbase_boundary_review.tsv`
- `results/production/receptor_features/missing_rbpbase_review/missing_rbpbase_boundary_review_summary.tsv`
- `results/production/receptor_features/missing_rbpbase_review/missing_rbpbase_vs_prodigal_blastp.tsv`

Because `results/` is ignored, remote reviewers should reproduce outputs from scripts or request an artifact bundle if they need exact generated tables.

## Commands Recently Validated

```bash
python scripts/build_phold_non_pharokka_receptor_review.py
python scripts/reconcile_receptor_feature_sources.py
python scripts/review_missing_rbpbase_exact_matches.py --threads 16
python scripts/build_mash_pairwise_similarity.py --threads 16
python -m py_compile scripts/*.py
git diff --check
```

Additional H1 model commands used locally:

```bash
python scripts/build_receptor_layer_pairwise_matrix.py
python scripts/run_receptor_layer_model_comparison.py
python scripts/run_receptor_layer_model_comparison.py --genome-similarity results/production/phage_similarity/mash_pairwise_similarity.tsv --model-output results/production/models/mash_similarity/receptor_layer_model_comparison.tsv --summary-output results/production/models/mash_similarity/receptor_layer_model_summary.tsv --prediction-output results/production/models/mash_similarity/receptor_layer_out_of_fold_predictions.tsv --pooled-summary-output results/production/models/mash_similarity/receptor_layer_model_pooled_summary.tsv --ablation-output results/production/models/mash_similarity/receptor_layer_feature_source_ablation.tsv --group-bootstrap-output results/production/models/mash_similarity/receptor_layer_group_bootstrap_delta.tsv --delta-output results/production/models/mash_similarity/receptor_layer_model_delta_summary.tsv --readiness-output results/production/models/mash_similarity/receptor_layer_model_readiness.tsv --report-output results/production/models/mash_similarity/receptor_layer_model_report.md
```

## What Should Be Reviewed Next

1. Review whether boundary-reviewed RBPbase candidate counts should become the default RBPbase feature for H1, while preserving exact-match columns for auditability.
2. Add a more publication-standard phage taxonomy/similarity baseline such as VIRIDIC or skani/ANI. Mash has now been added as a k-mer robustness baseline, but it is not VIRIDIC.
3. Review the 8 high-priority non-Pharokka Phold/Foldseek receptor-like candidates manually for confidence, coverage, synteny, product specificity, and overlap with RBPbase/Pharokka evidence.
4. Keep H4 blocked until productive-infection outcomes and accepted defense/counter-defense evidence exist.
5. Add accepted host-defense and phage-counter-defense evidence only after the receptor-layer benchmark is stable and the endpoint question is explicit.

## Unsupported Claims

Do not claim yet:

- RBP/depolymerase modules outperform taxonomy or genome similarity.
- Any candidate binds a specific capsule or degrades capsule.
- Spot-test positives prove productive infection.
- Defense/counter-defense compatibility explains host-range gaps.
- The workflow recommends therapeutic phages.

Allowed current claim:

Within the PhageHostLearn spot-test benchmark, the repository now supports an exploratory receptor-layer comparison with grouped splits and conservative claim boundaries. Current receptor summaries do not robustly outperform the BLASTN nearest-phage plus host K/O baseline.

