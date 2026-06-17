---
name: klebsiella-phage-cpg
description: Use this skill for Klebsiella phage comparative genomics, including phage genome curation, RBP/depolymerase discovery, prophage mining, K/O host association, defense/counter-defense analysis, statistical model comparison, and publication-ready figure planning.
---

# Klebsiella Phage Comparative Genomics Skill

## Purpose

Use this workflow to build or extend a novelty-focused Klebsiella phage comparative genomics study.

Core hypothesis:

Klebsiella phage host range is shaped by two genomic filters:
1. receptor compatibility: RBP/depolymerase modules versus capsule/LPS type;
2. intracellular compatibility: bacterial defense systems versus phage anti-defense genes.

## Default Workflow

When invoked, first identify which stage the repository is currently in:

1. Dataset curation
2. Phage dereplication and genome similarity
3. Phage annotation and pangenome
4. RBP/depolymerase prediction
5. Host K/O/ST/AMR/virulence annotation
6. Defense/counter-defense annotation
7. Statistical modeling
8. Figure generation
9. Manuscript methods and interpretation

Then propose or implement the smallest useful next step, depending on the user's request.

## Required Outputs by Stage

### Stage 1: Dataset Curation

Outputs:
- `config/samples.tsv`
- `results/qc/phage_genome_manifest.tsv`
- `results/qc/manifest_validation_report.tsv`
- `results/qc/excluded_genomes.tsv`

Check:
- accessions are unique when available;
- `genome_id` values are unique;
- genome lengths are plausible;
- raw data paths are never modified;
- metadata columns are documented.

### Stage 2: Dereplication and Similarity

Outputs:
- `results/clusters/phage_ani.tsv`
- `results/clusters/phage_clusters.tsv`
- `results/clusters/representatives.tsv`

Check:
- thresholds are recorded in `config/thresholds.yaml`;
- representative genomes are selected reproducibly.

### Stage 3: Annotation and Pangenome

Outputs:
- `results/annotations/phage_annotations.tsv`
- `results/annotations/gene_clusters.tsv`
- `results/annotations/pangenome_matrix.tsv`

Check:
- annotation tool versions are recorded;
- hypothetical proteins are retained, not discarded.

### Stage 4: RBP/Depolymerase Discovery

Outputs:
- `results/rbp_depolymerase/candidates.tsv`
- `results/rbp_depolymerase/domain_architectures.tsv`
- `results/rbp_depolymerase/module_clusters.tsv`
- `results/rbp_depolymerase/novel_candidates.tsv`

Check:
- candidate evidence columns include sequence homology, domain evidence, structural or remote-homology evidence if available, synteny, and confidence;
- BLAST-only novelty claims are not allowed.

### Stage 5: Host Annotation

Outputs:
- `results/host_features/host_metadata.tsv`
- `results/host_features/kaptive_results.tsv`
- `results/host_features/kleborate_results.tsv`

Check:
- K/O calls are linked to host genome identifiers;
- missing host metadata is explicitly marked.

### Stage 6: Defense/Counter-Defense

Outputs:
- `results/defense_systems/host_defense_systems.tsv`
- `results/defense_systems/phage_antidefense_candidates.tsv`
- `results/defense_systems/compatibility_features.tsv`

Check:
- bacterial defense systems and phage counter-defense features are not mixed into one ambiguous column;
- each prediction has a tool/source column.

### Stage 7: Modeling

Outputs:
- `results/models/model_comparison.tsv`
- `results/models/feature_importance.tsv`
- `results/models/prediction_errors.tsv`
- `results/models/hypothesis_summary.tsv`

Compare and summarize H1-H6 evidence status:
- taxonomy-only model;
- whole-genome similarity model;
- RBP/depolymerase model;
- host K/O model;
- host defense model;
- combined receptor plus defense/counter-defense model.

### Stage 8: Figures

Outputs:
- `results/figures/figure_1_dataset_atlas.*`
- `results/figures/figure_2_phage_pangenome.*`
- `results/figures/figure_3_rbp_module_network.*`
- `results/figures/figure_4_k_o_association.*`
- `results/figures/figure_5_defense_counterdefense.*`
- `results/figures/figure_6_novelty_prioritization.*`

Check:
- each figure has source data;
- axes and legends are interpretable;
- figure files are reproducible from scripts.

### Stage 9: Manuscript Support

Outputs:
- `docs/methods.md`
- `docs/hypotheses.md`
- `docs/figure_plan.md`
- `docs/limitations.md`
- `docs/manuscript_outline.md`

Check:
- novelty claims are supported by analyses;
- limitations are explicit;
- experimental validation needs are clearly separated from computational predictions.

## Reporting Format

After each task, report:

1. What was done
2. Files changed
3. Commands run
4. Outputs generated
5. Checks passed or failed
6. Remaining uncertainty
7. Next best step
