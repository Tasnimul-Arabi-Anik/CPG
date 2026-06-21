# Pilot Report: Klebsiella Phage Comparative Genomics

## Purpose

This pilot audits the current repository data and summarizes real outputs already available from established tools or reviewed external datasets. It does not claim that the full receptor-plus-defense hypothesis is proven.

## Current Data

- Total manifest records: 318.
- Sequence-QC passing records: 308.
- Tested phage-host spot outcomes: 10006 pairs.
- Spot-positive pairs: 333.
- Spot-negative pairs: 9673.
- Productive-infection/plaque/EOP outcomes: 0.
- Assay phages summarized for RBP candidates: 105.
- Assay phages with current candidate RBP/depolymerase rows: 103/105.
- Sequence-backed host records: 201.
- Sequence-backed PhageHostLearn assay hosts: 200/200.

## Real Outputs Inspected

- `results/pilot/data_audit.tsv` audits sequence, host-range, host typing, and inclusion status.
- `results/pilot/host_range_summary.tsv` gives continuous tested-panel spot breadth with Wilson intervals.
- `results/pilot/rbp_candidate_summary.tsv` summarizes current candidate evidence per assay phage.
- `results/pilot/tool_run_summary.tsv` records tool/source status, versions where available, commands, inputs, and outputs.
- `results/pilot/hypothesis_feasibility.tsv` states which hypotheses are currently testable.

## Tool Status

Prodigal and BLASTN are available and have been used for current production evidence. Pharokka `1.9.1` was installed in the `pharokka` conda environment for the 30-phage pilot. Phold `1.2.5` and Foldseek `10.941cd33` were installed in the `phold` conda environment for the structural pilot. Reviewed Kaptive/Kleborate outputs are available, but their executables are not currently on `PATH`. HMMER, DefenseFinder, and PADLOC are not currently available on `PATH`; they should be run directly once installed rather than replaced with custom implementations.

## Scientific Interpretation

The repository now has a real response-variable layer for initial interaction: PhageHostLearn spot tests provide explicit positives and tested negatives. This supports descriptive spot-range and future receptor-layer modeling. It does not support productive-infection prediction because spot clearing is not plaque/EOP/propagation evidence.

Host receptor/background evidence is now strong enough for a pilot: Kaptive K/O rows cover the assay hosts, and Kleborate rows cover most assay hosts. Phage-side evidence is improved but still incomplete: Prodigal CDS calls, exact RBPbase matches, 30-phage Pharokka annotations, and 30-phage Phold/Foldseek outputs can prioritize candidates, but they are not yet a full 105-phage production annotation layer, domain evidence layer, or functional depolymerase validation.

Defense/counter-defense analysis is not currently testable. There are no host-defense calls, no accepted phage anti-defense calls, and no productive-infection outcomes.

## What Can Be Tested Now

- Descriptive spot-test breadth for assay phages.
- Exploratory receptor-layer coverage: host K/O availability plus phage candidate availability.
- Preliminary genome-similarity clustering using the current BLASTN baseline, with clear limitations.

## What Cannot Be Claimed Yet

- RBP/depolymerase modules outperform taxonomy for host-range prediction.
- Defense/counter-defense compatibility explains host-range gaps.
- Any specific candidate binds a capsule or degrades a capsule.
- Spot-test positives represent productive infection.
- The BLASTN baseline replaces VIRIDIC/Mash/skani/ANI for manuscript-grade phage clustering.

## Recommended Next Pilot Step

The 30-phage pilot justified full-set annotation scaling, and both Pharokka and Phold/Foldseek have now completed across all 105 assay phages. A pairwise receptor-layer feature matrix and an initial grouped H1 rate-baseline comparison have also been generated. The next bounded action is to add confidence intervals/permutation checks and a manuscript-grade phage taxonomy/similarity baseline before strengthening any H1 model claim. Do not claim receptor specificity or model superiority from annotation coverage alone.

## Pharokka Pilot

Pharokka `1.9.1` was installed and run on the 30-phage representative pilot selection. Completed runs: 30; failed runs: 0. The pilot produced `580` product-annotation rows matching receptor-binding, tail, structural, depolymerase, or lysis keywords in Pharokka GFF outputs. These rows are standardized annotation evidence for prioritization only; they are not capsule-binding, depolymerase-function, or productive-infection validation.

## Pharokka/RBPbase Comparison

The 30-phage Pharokka pilot was compared with the existing Prodigal/RBPbase candidate layer using coordinate overlap. Completed Pharokka runs compared: 30/30. Pharokka receptor-like rows in the selected set: 67. Phages with concordant Pharokka receptor-like and Prodigal/RBPbase candidate loci: 23. Pharokka-only receptor-like signal: 1. Prodigal/RBPbase-only signal: 0. Coordinate-level overlaps are in `results/pilot/pharokka_prodigal_rbp_overlap.tsv`; phage-level evidence relationships are in `results/pilot/pharokka_rbp_evidence_comparison.tsv`.

Decision: do not claim receptor specificity or model superiority from this comparison. Use it with the Phold/Foldseek pilot to prioritize loci for manual review and possible full-set scaling.

## Phold Structural Pilot

Phold/Foldseek was run on the Pharokka 30-phage pilot using Pharokka GenBank outputs. Completed or reused runs: 30/30; failed runs: 0. Per-CDS rows summarized: 2644. High-confidence annotation rows: 673. Receptor-like keyword rows in Phold outputs: 68; receptor-like rows newly assigned by non-Pharokka methods: 2. Relevant Phold hits are in `results/pilot/phold_relevant_hits.tsv`; run commands and statuses are in `results/pilot/phold_run_summary.tsv`.

Operational note: Phold 1.2.5 failed in the initial smoke test when `--omit_probs` was used, so the pilot runner does not pass that option. The successful smoke test and this pilot used `--cpu --hyps`, meaning Phold focused on Pharokka hypothetical proteins and carried forward existing Pharokka annotations for known CDSs.

Claim boundary: these structural annotations are prioritization evidence only. They do not demonstrate capsule specificity, productive infection, or that RBP/depolymerase features outperform taxonomy.

## Receptor Locus Review Set

A compact review table was built from the 30-phage pilot outputs: `results/pilot/receptor_locus_review.tsv`. It contains 40 priority rows: 2 non-Pharokka Foldseek receptor-like rows and 38 concordant Pharokka/RBPbase receptor-like coordinate overlaps. These rows are manual-review targets, not validated receptor-specificity calls.

Scale decision: `proceed_operationally` in `results/pilot/receptor_locus_scale_decision.tsv`. The current evidence supports scaling the same established Pharokka plus Phold/Foldseek commands to all 105 assay phages as an annotation-production step, but not using the 30-phage pilot as complete model evidence.

## Pharokka Full Assay-Phage Scale-Up

The established Pharokka command was scaled from the 30-phage pilot to all 105 PhageHostLearn assay phages under `results/production/pharokka_assay_phages/`. Outputs are summarized in `results/production/pharokka_assay_phage_run_summary.tsv`, `results/production/pharokka_assay_phage_annotation_summary.tsv`, and `results/production/pharokka_assay_phage_annotation_summary_metrics.tsv`. Completed or reused runs: 105/105; failed runs: 0. Pharokka keyword annotation rows: 1,932 across all 105 phages, including 151 tail-fiber rows, 6 tailspike rows, 3 receptor-binding rows, 1 depolymerase row, and 52 baseplate rows.

Claim boundary: this is production-scale standardized annotation evidence for receptor-candidate prioritization. It still does not validate capsule specificity, depolymerase function, productive infection, or RBP/depolymerase superiority over taxonomy. This step has now been followed by full-set Phold/Foldseek structural annotation and receptor-feature coverage auditing.

## Phold Full Assay-Phage Structural Annotation

Phold/Foldseek was run on the full 105 PhageHostLearn assay-phage set using Pharokka GenBank outputs. Completed or reused runs: 105/105; failed runs: 0. Per-CDS rows summarized: 9570. High-confidence annotation rows: 2315. Receptor-like keyword rows in Phold outputs: 235; receptor-like rows newly assigned by non-Pharokka methods: 23. Relevant hits are in `results/production/phold_assay_phage_relevant_hits.tsv`; run commands and statuses are in `results/production/phold_assay_phage_run_summary.tsv`.

Operational note: Phold 1.2.5 failed in the initial smoke test when `--omit_probs` was used, so this runner does not pass that option. Runs use `--cpu`; with `--hyps`, Phold focuses on Pharokka hypothetical proteins and carries forward existing Pharokka annotations for known CDSs.

Claim boundary: these structural annotations are prioritization evidence only. They do not demonstrate capsule specificity, productive infection, or that RBP/depolymerase features outperform taxonomy.

## Phold Non-Pharokka Receptor Review

A focused full-set review table was built for Phold/Foldseek receptor-like CDSs that were not already annotated by Pharokka: `results/production/receptor_features/phold_non_pharokka_receptor_review.tsv`. It contains 23 CDS rows across 12 assay phages. Feature counts are tail fiber 12, tailspike 5, baseplate 6, receptor-binding 0, and depolymerase 0. Confidence counts are high 14, medium 5, and low 4. High-priority manual-review candidates: 8.

Claim boundary: these rows are structural remote-homology review targets only. They do not demonstrate capsule specificity, depolymerase activity, productive infection, or receptor-feature superiority over genome-similarity baselines.

## Assay-Phage Receptor Feature Coverage

Phage-side receptor feature coverage was summarized from full-set RBPbase candidate rows, Pharokka annotations, and Phold/Foldseek structural annotations. Coverage table: `results/production/receptor_features/assay_phage_receptor_feature_coverage.tsv`. Summary table: `results/production/receptor_features/assay_phage_receptor_feature_summary.tsv`. Assay phages covered by Pharokka and Phold: 105/105. Phages with any receptor-like evidence across RBPbase, Pharokka, or Phold: 105/105. RBPbase exact Prodigal matches: 247; boundary-reviewed RBPbase candidates: 274; Phold receptor-like CDS rows: 235; feature-level receptor-like rows: 236; non-Pharokka Phold receptor-like rows: 23.

Readiness: phage-side receptor features are `available_for_feature_audit`; receptor-layer modeling is `feature_coverage_available_for_pairwise_modeling`. The downstream pairwise matrix and grouped H1 model comparison should be refreshed after receptor-feature coverage changes.

Claim boundary: this audit measures feature coverage. It does not claim that any feature binds a capsule, degrades capsule, or predicts host range better than taxonomy.

## Receptor-Layer Pairwise Feature Matrix

A tested-pair feature matrix was built from reviewed PhageHostLearn spot assays, host K/O/ST evidence, full-set phage receptor-feature coverage, and phage species-cluster labels. Exact RBPbase CDS matches and boundary-reviewed RBPbase candidates are retained as separate feature columns. Matrix: `results/production/model_inputs/receptor_layer_pairwise_features.tsv`. Rows: 10006; spot-positive: 333; spot-negative: 9673. Pair rows with complete host receptor features and phage receptor features: 10006. Pair rows with a phage cluster/taxonomy baseline label: 10006.

Readiness: `matrix_available_for_receptor_layer_modeling`. This matrix is the receptor-layer modeling input. Cold-phage, cold-host, cold-cluster, and study/panel grouping columns are included to prevent naive random-pair leakage.

Claim boundary: this matrix prepares an H1 receptor-layer test. It does not claim RBP/depolymerase features outperform taxonomy, and it does not address productive infection or defense/counter-defense compatibility.

## Receptor Feature Source Reconciliation

Receptor evidence sources were reconciled in `results/production/receptor_features/receptor_source_reconciliation.tsv`. The reviewed PhageHostLearn RBPbase source contains 274 candidate proteins across 105 assay phages. Current Prodigal CDS exact protein matching recovers 247 of those candidates; 27 RBPbase proteins do not exact-match a current Prodigal CDS protein and are listed in `results/production/receptor_features/receptor_source_reconciliation_missing_rbpbase.tsv`.

Pharokka contributes 213 receptor-like keyword rows, while Phold/Foldseek contributes 236 receptor-like feature rows, including 23 non-Pharokka structural remote-homology rows. These counts are evidence-source reconciliation, not additive validated receptor loci.

Claim boundary: RBPbase, Pharokka, and Phold evidence rows are candidate-prioritization signals. They do not prove capsule specificity, depolymerase activity, productive infection, or H1 model superiority.

## Missing RBPbase Exact-Match Review

The 27 RBPbase candidates absent from current exact Prodigal CDS matches were reviewed with BLASTP against current same-phage Prodigal proteins. Review table: `results/production/receptor_features/missing_rbpbase_review/missing_rbpbase_boundary_review.tsv`. BLASTP version: `blastp: 2.12.0+`.

Rows reviewed: 27; high-scoring RBPbase rows (`xgb_score >= 0.9`): 23. Same-phage hit status counts: near-identical 25, strong 2, partial 0, weak 0, no hit 0. Boundary-review statuses: likely start/stop or gene-boundary difference 25; likely minor boundary/sequence difference 2; related current CDS not exact match 0.

Claim boundary: BLASTP review explains why exact-match evidence is incomplete. It does not validate receptor function, and missing exact CDS matches should not be interpreted as biological absence.

## H1 Receptor-Layer Model Comparison

A grouped, interpretable rate-baseline comparison was run from `results/production/model_inputs/receptor_layer_pairwise_features.tsv`. Fold-level metrics: `results/production/models/receptor_layer_model_comparison.tsv`. Out-of-fold predictions: `results/production/models/receptor_layer_out_of_fold_predictions.tsv`. Mean-fold summary metrics: `results/production/models/receptor_layer_model_summary.tsv`. Pooled out-of-fold summary metrics: `results/production/models/receptor_layer_model_pooled_summary.tsv`. Fold-level deltas versus global prevalence: `results/production/models/receptor_layer_model_delta_summary.tsv`. Split strategies: cold phage, cold host, cold K-locus, and cold phage cluster. Models compared: global prevalence, phage marginal rate, host marginal rate, K-type/K/O rates, phage cluster/taxonomy rate, BLASTN nearest-phage genome-similarity rates, exact and boundary-reviewed RBPbase rates, receptor-feature signature rates, receptor plus host K/O rates, genome similarity plus host K/O rate, and combined receptor plus host K/O plus phage cluster rates. Frozen H1 contract: `docs/h1_receptor_layer_analysis_contract.md`. Best pooled average precision by split: cold_K_locus: phage_marginal_rate pooled_AP=0.143466; cold_host: genome_similarity_nearest_phage_host_KO_rate pooled_AP=0.258266; cold_phage: genome_similarity_nearest_phage_host_KO_rate pooled_AP=0.186960; cold_phage_cluster: genome_similarity_nearest_phage_host_KO_rate pooled_AP=0.195850. Fold-level diagnostic average-precision deltas versus global prevalence: cold_K_locus genome_similarity_nearest_phage_host_KO_rate AP_delta=0.133389 CI95=[0.078537, 0.190302] p=0.031250; cold_K_locus genome_similarity_nearest_phage_rate AP_delta=0.133389 CI95=[0.079162, 0.197257] p=0.031250; cold_K_locus taxonomy_cluster_rate AP_delta=0.131061 CI95=[0.080321, 0.187990] p=0.031250; cold_K_locus phage_marginal_rate AP_delta=0.130795 CI95=[0.080757, 0.180556] p=0.031250; cold_K_locus receptor_signature_rate AP_delta=0.063595 CI95=[0.032136, 0.090328] p=0.031250; cold_K_locus combined_receptor_boundary_reviewed_host_taxonomy_rate AP_delta=0.000000 CI95=[0.000000, 0.000000] p=1.000000. Primary pooled receptor-versus-genome baseline comparison: cold_phage: receptor+K/O AP=0.134867, BLASTN-nearest-phage+K/O AP=0.186960; cold_phage_cluster: receptor+K/O AP=0.141067, BLASTN-nearest-phage+K/O AP=0.195850; cold_K_locus: receptor+K/O AP=0.028049, BLASTN-nearest-phage+K/O AP=0.133841; cold_host: receptor+K/O AP=0.108970, BLASTN-nearest-phage+K/O AP=0.258266. Feature-source ablation table: `results/production/models/receptor_layer_feature_source_ablation.tsv`. Group-resampling AP delta table: `results/production/models/receptor_layer_group_bootstrap_delta.tsv`. Cold-cluster receptor-source contrasts: boundary_reviewed_rbpbase_increment_over_exact_rbpbase: delta_AP=0.019078 (rbpbase_boundary_reviewed_plus_host_KO_rate 0.095566 vs rbpbase_plus_host_KO_rate 0.076488); phold_increment_over_rbpbase: delta_AP=0.039730 (phold_plus_host_KO_rate 0.116218 vs rbpbase_plus_host_KO_rate 0.076488); pharokka_phold_increment_over_rbpbase: delta_AP=0.039730 (pharokka_phold_plus_host_KO_rate 0.116218 vs rbpbase_plus_host_KO_rate 0.076488); union_increment_over_rbpbase: delta_AP=0.064579 (receptor_plus_host_KO_rate 0.141067 vs rbpbase_plus_host_KO_rate 0.076488); boundary_reviewed_union_increment_over_exact_union: delta_AP=-0.000427 (receptor_boundary_reviewed_plus_host_KO_rate 0.140640 vs receptor_plus_host_KO_rate 0.141067); boundary_reviewed_union_vs_genome_similarity: delta_AP=-0.055210 (receptor_boundary_reviewed_plus_host_KO_rate 0.140640 vs genome_similarity_nearest_phage_host_KO_rate 0.195850); primary_receptor_union_vs_genome_similarity: delta_AP=-0.054783 (receptor_plus_host_KO_rate 0.141067 vs genome_similarity_nearest_phage_host_KO_rate 0.195850). Primary group-bootstrap contrasts: cold_K_locus: delta_AP=-0.105792 groupCI95=[-0.157985, -0.068145]; cold_phage_cluster: delta_AP=-0.054783 groupCI95=[-0.142571, 0.043107].

Claim boundary: this is an initial quantitative H1 test on spot-test interaction outcomes only. It is not evidence of productive infection and does not address defense/counter-defense compatibility. In the current pilot, receptor-feature summaries do not yet outperform the BLASTN nearest-phage plus host K/O baseline under cold-phage, cold-K-locus, or cold-cluster splits. Fold-level intervals and sign-flip checks are diagnostic only. The held-out-group bootstrap intervals are benchmark-specific and use the current grouped folds, not an independent external validation. Treat any apparent model advantage as provisional until independent validation, leakage checks, and VIRIDIC/Mash-style manuscript-grade phage taxonomy/similarity baselines are added.
