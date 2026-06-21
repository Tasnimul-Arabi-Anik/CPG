# H1 receptor-layer analysis contract

## Scope

This contract freezes the next H1 benchmark comparison for the PhageHostLearn 2024 Klebsiella spot-test matrix. It applies to the current benchmark layer only and does not make claims about productive infection, plaque formation, EOP, therapy, or defense/counter-defense compatibility.

## Freeze and PR Boundary

The H1 work must stay split into two reviewable scopes.

PR A is production phage receptor evidence only. It may contain run manifests, tool/database versions, commands, feature extraction, per-phage completion summaries, receptor-feature tables, and manual review of Phold-only candidates. It must not tune or report model performance.

PR B is the frozen H1 benchmark analysis. It must consume immutable feature inputs from PR A, use the fixed cohort and split rules below, and write out-of-fold predictions plus paired held-out-group uncertainty. It must not change annotation rules, receptor candidate definitions, feature extraction thresholds, or Phold candidate classification after model results are inspected.

Any later change to feature definitions must return to PR A/evidence-review scope and then rerun PR B from frozen inputs.

## Outcome

Primary outcome: observed spot-test interaction from reviewed assay rows.

Positive label: `spot_result=positive`.

Negative label: `spot_result=negative`.

Excluded labels: untested cells, unsupported matrix values, and rows without a reviewed spot outcome.

Current reviewed outcome support:

- tested spot pairs: 10,006
- spot-positive pairs: 333
- spot-negative pairs: 9,673
- productive-infection outcomes: 0

## Data Provenance and Fixed Cohort

Host K/O features are newly generated production evidence from Kaptive 3.2.1 run on the reviewed PhageHostLearn host genome archive. They are not Locibase bridge metadata. The reviewed Kaptive table records database names, commands, archive SHA-256, K/O output checksums, and review status in `data/metadata/production_evidence/kaptive_ko_typing.tsv`.

Host species/ST/AMR/virulence features are generated production evidence from Kleborate 3.2.4 run on the same reviewed host archive and recorded in `data/metadata/production_evidence/kleborate_host_features.tsv`.

The fixed H1 benchmark cohort is the 10,006 reviewed spot-test interactions with explicit positive or tested-negative labels. The current receptor-layer pairwise matrix reports 10,006/10,006 rows with host K/O, 10,006/10,006 rows with assessed phage receptor features, and 10,006/10,006 rows with phage taxonomy/cluster labels. The earlier 9,806-row taxonomy-baseline discrepancy must be treated as resolved only for this fixed matrix; if any future feature table reintroduces missing labels, all direct model comparisons must use a documented common complete-case cohort and identical folds.

## Primary comparison

Primary split: `cold_phage_cluster`.

Rationale: this is the most conservative current split for evaluating whether receptor-layer features generalize beyond close phage lineages. It is still not an independent external-study validation.

Required receptor holdout: `cold_K_locus` remains a required secondary split because cold host is not necessarily cold receptor. Interpret `cold_host` as a new-strain split, `cold_K_locus` as a new receptor-group split, `cold_phage` as a new-phage split, and `cold_phage_cluster` as a new-phage-lineage split.

Primary model: `receptor_plus_host_KO_rate`.

Primary baseline: `genome_similarity_nearest_phage_host_KO_rate` using the reviewed BLASTN whole-genome similarity table.

Primary metric: tie-aware pooled out-of-fold average precision. Mean fold AP remains a descriptive diagnostic; pooled out-of-fold predictions are emitted to `results/production/models/receptor_layer_out_of_fold_predictions.tsv`, and compact fallback/support summaries are emitted to `results/production/models/receptor_layer_support_diagnostics.tsv`.

Primary contrast: `AP(receptor_plus_host_KO_rate) - AP(genome_similarity_nearest_phage_host_KO_rate)` under `cold_phage_cluster`.

Required Phold incremental contrast: `AP(pharokka_phold_plus_host_KO_rate) - AP(pharokka_plus_host_KO_rate)`. This contrast tests whether structure-informed Phold/Foldseek evidence adds predictive value beyond Pharokka-style receptor annotation. It must be evaluated on the same rows and folds as the primary comparison.

Current pilot result direction from pooled AP: the original coarse receptor-source/count union plus K/O does not outperform the BLASTN nearest-phage plus K/O baseline under the frozen primary cold-phage-cluster split. An exploratory exact domain+structural module-identity contrast improves over RBPbase plus K/O and is competitive with genome-similarity baselines, but its paired bootstrap intervals versus genome similarity overlap zero. This is not a definitive test of full RBP/depolymerase domain-order architecture or novel-K generalization.

## Secondary comparisons

Secondary splits:

- `cold_phage`
- `cold_host`
- `cold_K_locus`

Secondary models and baselines:

- global prevalence
- phage marginal positive rate
- host marginal positive rate
- host K-type rate
- host K/O rate
- phage species-cluster rate
- BLASTN nearest-phage rate
- RBPbase plus host K/O rate
- Pharokka plus host K/O rate
- Phold/Foldseek plus host K/O rate
- Phold/Foldseek non-Pharokka-only plus host K/O rate
- Pharokka plus Phold/Foldseek plus host K/O rate
- union receptor-feature signature rate
- union receptor plus host K/O rate
- BLASTN nearest-phage plus host K/O rate
- combined receptor plus host K/O plus phage cluster rate

Secondary metrics:

- ROC AUC
- balanced accuracy at training prevalence
- Brier score
- hit-rate metrics for cold-host ranking, not yet implemented

## Feature rules

Host receptor features come from reviewed Kaptive/Kleborate production evidence.

Phage receptor features include RBPbase support, Pharokka annotations, Phold/Foldseek annotations, and exact PHROGs/MMseqs domain IDs plus Phold/Foldseek structural hit IDs as module-identity signatures. These module signatures are more informative than source/count bins, but they still do not encode domain order, catalytic-domain boundaries, C-terminal receptor-recognition architecture, or experimentally validated capsule specificity. These sources must remain separated in ablation before claiming that Phold-derived structural annotation or module identity adds value.

Current feature source labels are exploratory. The current ablation output is `results/production/models/receptor_layer_feature_source_ablation.tsv` and compares:

- host K/O only
- RBPbase plus host K/O
- Pharokka plus host K/O
- Phold/Foldseek plus host K/O
- Phold/Foldseek non-Pharokka-only plus host K/O
- Pharokka plus Phold/Foldseek plus host K/O
- exact PHROGs/MMseqs domain module identities plus host K/O
- exact Phold/Foldseek structural module identities plus host K/O
- combined exact domain+structural module identities plus host K/O
- union receptor features plus host K/O
- whole-genome similarity/taxonomy baselines

Current cold-phage-cluster pooled AP findings are exploratory. Exact domain+structural module identity signatures plus host K/O outperform RBPbase plus host K/O (AP 0.203203 versus 0.071841; delta 0.131362; held-out-group bootstrap CI [0.068376, 0.209580]). Against genome-similarity plus host K/O baselines, the same module signature is competitive but not robustly superior: delta AP is 0.016243 versus BLASTN, 0.014295 versus fastANI, and 0.002716 versus skani, with all paired held-out-group bootstrap intervals overlapping zero. Under cold_K_locus, receptor feature plus host K/O and module plus host K/O models do not improve over the global baseline, while phage marginal and nearest-phage genome-similarity baselines retain signal. Because cold_K_locus deliberately withholds exact K-locus labels used in the receptor-plus-K/O composite key, the current support diagnostics show that receptor-plus-K/O and module-plus-K/O use global fallback for all cold-K-locus predictions, while genome-similarity plus K/O falls back to nearest-phage marginal rates when direct K/O support is unavailable. This split therefore requires a future host-locus feature representation before it can be interpreted as novel-receptor generalization. The current pilot supports module-identity signal over RBPbase, but not a robust claim that module identities outperform whole-genome similarity.

## Manual Phold-Only Candidate Review

The 23 non-Pharokka Phold/Foldseek receptor-like candidates are not automatically novel RBPs. Before manuscript claims, each candidate must be manually classified using Phold confidence, Foldseek E-value, query coverage, target coverage, annotation specificity, protein length, tail-module synteny, RBPbase overlap, and Pharokka context. Allowed review categories are `strong_structure_informed_rbp_candidate`, `possible_tail_or_receptor_associated_protein`, `generic_structural_protein`, and `insufficiently_specific`.

Only reviewed candidates in the first two categories may be used as candidate-discovery examples. None of these categories proves capsule binding, depolymerase activity, productive infection, or therapeutic value.

## Cluster and baseline rules

Species-like phage clusters are taken from `results/production/clusters/phage_clusters.tsv`, generated with the configured 95 percent identity and 85 percent coverage thresholds from the production BLASTN similarity evidence.

All models in a direct comparison must use the same reviewed spot-assay rows and the same grouped folds.

The current BLASTN nearest-phage baseline is the primary local sequence-similarity baseline. fastANI and skani robustness baselines are also available. These benchmark-scale baselines are useful for H1 robustness checks, but VIRIDIC or another reviewed public-scale phage intergenomic similarity analysis is still needed for final taxonomy claims in the comprehensive study.

## Uncertainty rules

Do not bootstrap individual assay rows because rows are dependent through repeated phages and hosts.

Current uncertainty output: `results/production/models/receptor_layer_group_bootstrap_delta.tsv`. This table resamples the held-out grouping unit for each split:

- cold host: held-out hosts
- cold phage: held-out phages
- cold phage cluster: held-out phage clusters
- cold K-locus: held-out K-locus groups

Permutation tests must preserve the tested-pair mask and relevant grouping structure. If that cannot be implemented compactly and correctly, omit permutation p-values.

## Claim boundary

Allowed current claim:

Within the PhageHostLearn spot-test benchmark, exact receptor module identity signatures improve over RBPbase and are competitive with genome-similarity baselines under cold-phage-cluster evaluation, but do not yet robustly outperform genome similarity.

Not allowed yet:

- RBP/depolymerase module architecture has been adequately tested
- cold-K-locus results prove novel-receptor generalization under the current exact K/O fallback design
- receptor features outperform whole-genome similarity
- general Klebsiella host-range prediction
- productive-infection prediction
- capsule specificity for any candidate protein
- defense/counter-defense compatibility
- therapeutic phage recommendation
