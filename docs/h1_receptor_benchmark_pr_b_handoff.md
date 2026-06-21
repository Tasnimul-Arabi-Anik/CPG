# H1 receptor benchmark handoff

## Scope

This branch is PR B for the H1 receptor-layer benchmark. It is stacked on PR A (`prA-production-receptor-evidence`) and consumes the frozen phage receptor evidence from that branch.

The benchmark endpoint is the reviewed PhageHostLearn 2024 spot-test interaction matrix:

- tested spot pairs: 10,006
- spot-positive pairs: 333
- spot-negative pairs: 9,673
- productive-infection outcomes: 0

Spot-test positivity is treated as initial interaction/clearing evidence only. It is not plaque formation, EOP, propagation, or productive-infection evidence.

## Included evidence and scripts

Tracked H1 benchmark evidence in this branch:

| Evidence layer | File | Rows | Purpose |
| --- | --- | ---: | --- |
| Host K/O typing | `data/metadata/production_evidence/kaptive_ko_typing.tsv` | 200 | Host receptor labels from reviewed Kaptive 3.2.1 runs. |
| Host species/ST/AMR/virulence features | `data/metadata/production_evidence/kleborate_host_features.tsv` | 188 | Host background metadata from reviewed Kleborate 3.2.4 runs. |
| Primary phage genome-similarity baseline | `data/metadata/production_evidence/phage_genome_similarity.tsv` | 5,671 | BLASTN pairwise similarity baseline. |
| fastANI robustness baseline | `data/metadata/production_evidence/phage_fastani_similarity.tsv` | 5,460 | ANI-style robustness baseline for benchmark phages. |
| skani robustness baseline | `data/metadata/production_evidence/phage_skani_similarity.tsv` | 5,460 | skani robustness baseline for benchmark phages. |

Added H1 benchmark scripts:

- `scripts/build_phagehostlearn_host_typing_evidence.py`
- `scripts/build_blastn_pairwise_similarity.py`
- `scripts/build_fastani_pairwise_similarity.py`
- `scripts/build_skani_pairwise_similarity.py`
- `scripts/build_receptor_layer_pairwise_matrix.py`
- `scripts/run_receptor_layer_model_comparison.py`

The production profile is wired to the H1 inputs needed here: pairwise phage similarity, phage annotation/domain/structural receptor evidence from PR A, and host Kaptive/Kleborate evidence. Host-defense and phage anti-defense inputs remain intentionally unset in this branch.

## Frozen analysis contract

`docs/h1_receptor_layer_analysis_contract.md` freezes the current benchmark comparison before further H1 tuning. The primary comparison is:

- outcome: `spot_result=positive` versus `spot_result=negative`
- primary split: `cold_phage_cluster`
- required receptor holdout: `cold_K_locus`
- primary metric: pooled out-of-fold average precision
- primary model: `receptor_plus_host_KO_rate`
- primary baseline: `genome_similarity_nearest_phage_host_KO_rate`
- primary contrast: `AP(receptor_plus_host_KO_rate) - AP(genome_similarity_nearest_phage_host_KO_rate)`

The contract also requires source ablations so Phold/Foldseek signal is not conflated with RBPbase or Pharokka evidence. The current PR B feature representation is deliberately limited to coarse receptor-source/count signatures plus host K/O labels; it is not yet a domain-level or structural module-architecture representation of RBP/depolymerase proteins.

## Reproduction commands

```bash
python scripts/build_phagehostlearn_host_typing_evidence.py
python scripts/build_blastn_pairwise_similarity.py
python scripts/build_fastani_pairwise_similarity.py --threads 64
python scripts/build_skani_pairwise_similarity.py --threads 64 --skani-command /tmp/cpg_skani_env/bin/skani   --output data/metadata/production_evidence/phage_skani_similarity.tsv   --report-output data/metadata/production_evidence/phage_skani_similarity_report.tsv
python scripts/build_receptor_layer_pairwise_matrix.py
python scripts/run_receptor_layer_model_comparison.py
```

Large generated model outputs remain ignored and should be regenerated for review, especially `results/production/model_inputs/receptor_layer_pairwise_features.tsv` and `results/production/models/receptor_layer_out_of_fold_predictions.tsv`. PR B now tracks only compact frozen review artifacts under `results/production/` so reviewers can inspect the headline benchmark tables without checking in native tool directories or the 760,456-row prediction table.

## Local validation results

The H1 matrix and grouped benchmark scripts were rerun locally on this branch.

Generated large ignored outputs:

- `results/production/model_inputs/receptor_layer_pairwise_features.tsv`: 10,006 rows
- `results/production/models/receptor_layer_model_comparison.tsv`: 380 fold-level rows
- `results/production/models/receptor_layer_out_of_fold_predictions.tsv`: 760,456 prediction rows

Tracked compact review outputs:

- `results/production/receptor_features/assay_phage_receptor_feature_coverage.tsv`: 105 rows
- `results/production/receptor_features/assay_phage_cluster_assignments.tsv`: 105 rows
- `results/production/models/receptor_layer_model_pooled_summary.tsv`: 76 rows
- `results/production/models/receptor_layer_support_diagnostics.tsv`: 380 rows
- `results/production/models/receptor_layer_feature_source_ablation.tsv`: 44 rows
- `results/production/models/receptor_layer_group_bootstrap_delta.tsv`: 44 rows
- `results/production/models/benchmark_run_manifest.tsv`: checksum manifest for the compact review artifacts

Primary cold-phage-cluster contrast, `receptor_plus_host_KO_rate - genome_similarity_nearest_phage_host_KO_rate`:

| Similarity baseline | Receptor AP | Baseline AP | Delta AP | Held-out-group bootstrap 95% CI |
| --- | ---: | ---: | ---: | --- |
| BLASTN | 0.118254 | 0.195850 | -0.077596 | [-0.171900, 0.014083] |
| fastANI | 0.118254 | 0.188858 | -0.070604 | [-0.158084, 0.010668] |
| skani | 0.118254 | 0.199395 | -0.081141 | [-0.169619, -0.002116] |

Cold-K-locus receptor holdout is more strongly negative across these same baselines. Because the current receptor-plus-K/O model uses exact categorical K/O composite keys, all cold-K-locus receptor-plus-K/O predictions in this run collapse to global prevalence by construction. The support diagnostics show that the genome-similarity plus K/O model also lacks direct same-K/O support in cold-K-locus folds, but it uses an intermediate nearest-phage marginal-rate fallback rather than global prevalence. The current benchmark therefore supports only this narrow statement: coarse receptor-source/count summaries did not outperform genome-similarity baselines. It does not falsify the stronger module-architecture hypothesis.

## Claim boundary

Allowed wording for this branch:

> Within the PhageHostLearn spot-test benchmark, receptor-layer and genome-similarity features can be evaluated under grouped cold-host, cold-K-locus, cold-phage, and cold-phage-cluster splits.

Not allowed from this branch:

- RBP/depolymerase module architecture outperforms genome similarity; this branch currently tests coarse receptor-source/count summaries, not module architectures;
- receptor features outperform genome similarity unless the paired held-out-group uncertainty supports that contrast;
- spot-test positives prove productive infection;
- any candidate protein binds a specific capsule or has validated depolymerase activity;
- defense/counter-defense compatibility explains host-range gaps;
- general Klebsiella host-range prediction beyond this benchmark.

H4 remains blocked because productive-infection, plaque, propagation, or EOP outcomes are absent.
