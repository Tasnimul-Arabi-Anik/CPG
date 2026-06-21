# Production receptor evidence handoff

## Scope

This branch is PR A for the H1 receptor-layer work. It contains production receptor-evidence inputs and review scripts for the PhageHostLearn 2024 Klebsiella assay phages. It deliberately does not contain H1 model-comparison code, pairwise prediction outputs, genome-similarity baseline tables, host-defense evidence, phage anti-defense evidence, or H4 analyses.

The purpose is to freeze phage-side receptor evidence before any benchmark model comparison is reviewed.

## Included evidence

Tracked production evidence tables are wired in `config/workflow.production.yaml` through `inputs.annotation_input`, `inputs.domain_evidence`, and `inputs.structural_evidence`. Pairwise similarity, host typing, host-defense, and phage anti-defense inputs remain intentionally unset in this PR.

| Evidence layer | File | Rows | Claim boundary |
| --- | --- | ---: | --- |
| Baseline sequence-backed CDS annotations | `data/metadata/production_evidence/phagehostlearn_prodigal_cds_annotations.tsv` | 8,393 | Gene calls and product/RBPbase metadata only; not receptor specificity. |
| CDS annotation review | `data/metadata/production_evidence/phagehostlearn_prodigal_cds_annotations_review.tsv` | 10 | Run/review metadata, not biological evidence by itself. |
| PHROGs/MMseqs receptor-domain input | `data/metadata/production_evidence/phrogs_profile_receptor_domain_input.tsv` | 495 | Computational profile evidence only. |
| Normalized RBP domain evidence | `data/metadata/production_evidence/rbp_domain_evidence.tsv` | 495 | Candidate receptor-domain support only; not function validation. |
| Phold/Foldseek structural input | `data/metadata/production_evidence/phold_foldseek_receptor_structural_input.tsv` | 23 | Remote structural-homology candidates only. |
| Normalized RBP structural evidence | `data/metadata/production_evidence/rbp_structural_evidence.tsv` | 23 | Candidate structural support only; not capsule binding or depolymerase activity. |

Generated local review outputs are under ignored `results/` and can be regenerated. The current local Phold-only review contains 23 non-Pharokka receptor-like CDS rows across 12 assay phages: 8 computationally triaged as `strong_structure_informed_rbp_candidate`, 5 as `possible_tail_or_receptor_associated_protein`, 6 as `generic_structural_protein`, and 4 as `insufficiently_specific`. All are `computational_triage_needs_manual_confirmation`.

## Reproduction commands

Commands used or expected for this PR-A evidence layer:

```bash
python scripts/build_phagehostlearn_phage_cds_annotations.py
python scripts/run_pharokka_pilot.py
python scripts/run_phold_pilot.py
python scripts/build_phold_foldseek_structural_evidence.py
python scripts/build_phold_non_pharokka_receptor_review.py
python scripts/build_phrogs_profile_domain_evidence.py --min-qcov 0.10   --output data/metadata/production_evidence/phrogs_profile_receptor_domain_input.tsv   --report-output data/metadata/production_evidence/phrogs_profile_receptor_domain_input_report.tsv
python scripts/normalize_rbp_external_evidence.py   --domain-input data/metadata/production_evidence/phrogs_profile_receptor_domain_input.tsv   --domain-format generic_tsv   --domain-tool MMseqs2   --domain-tool-version 18.8cc5c   --domain-database "PHROGs profile database"   --domain-database-version phrog_annot_v4_local_pharokka_db   --domain-output data/metadata/production_evidence/rbp_domain_evidence.tsv   --structural-output data/metadata/production_evidence/rbp_structural_evidence.tsv   --report-output data/metadata/production_evidence/rbp_domain_evidence_normalization_report.tsv
python scripts/reconcile_receptor_feature_sources.py
python scripts/review_missing_rbpbase_exact_matches.py --threads 16
python scripts/summarize_assay_phage_receptor_features.py
```

External tools used for evidence generation include Prodigal 2.6.3, Pharokka 1.9.1, Phold 1.2.5, Foldseek 10.941cd33, and MMseqs2 18.8cc5c. These scripts are glue around established tools and reviewed outputs; they do not implement replacement annotation, clustering, structure-search, or receptor-prediction algorithms.

## Exclusions

This branch intentionally excludes:

- `scripts/build_receptor_layer_pairwise_matrix.py`
- `scripts/run_receptor_layer_model_comparison.py`
- BLASTN/Mash/fastANI/skani model-baseline evidence tables
- host-defense and phage-counter-defense evidence
- H4 productive-infection analysis
- any claim that receptor features outperform taxonomy or genome similarity

Those belong in later PRs after this evidence layer is reviewed and frozen.

## Claim boundary

Allowed wording for this branch:

> Production-scale phage receptor-candidate evidence has been generated for the PhageHostLearn assay phages using sequence-backed CDS calls, established phage annotation tools, PHROGs/MMseqs profile evidence, and Phold/Foldseek structural evidence.

Not allowed from this branch:

- any candidate binds a specific capsule;
- any candidate has validated depolymerase activity;
- receptor features predict host range better than taxonomy or genome similarity;
- spot-test positives prove productive infection;
- defense/counter-defense compatibility explains host-range gaps.

## Next PR

PR B should consume these frozen evidence inputs, add the fixed H1 benchmark contract, build pairwise spot-test feature matrices, run grouped cold-host/cold-K-locus/cold-phage/cold-cluster comparisons, and report pooled out-of-fold average precision plus held-out-group bootstrap deltas against strong baselines.
