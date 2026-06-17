# Hypothesis-to-Analysis Map

## H1: RBP/Depolymerase Modules Predict K/O Association Better Than Taxonomy

Input data:
- dereplicated phage clusters;
- RBP/depolymerase candidate modules;
- host K/O metadata.

Required features:
- phage taxonomy or genome-similarity cluster;
- RBP/depolymerase gene cluster or domain architecture;
- host K type and O type.

Primary test:
- compare predictive models using taxonomy-only, whole-genome similarity, RBP/depolymerase modules, and combined features.

Expected result:
- RBP/depolymerase module features outperform taxonomy-only features for K/O association.

Alternative explanation:
- host metadata may be biased toward well-studied capsule types or clinical lineages.

Output:
- `results/models/model_comparison.tsv`
- Figure 4 or Figure 5.

## H2: Prophages Are an Under-Sampled Reservoir of Capsule-Recognition Proteins

Input data:
- prophage sequences from Klebsiella host genomes;
- host K/O calls;
- RBP/depolymerase candidate annotations.

Required features:
- prophage-host linkage;
- candidate RBP/depolymerase evidence;
- K/O calls.

Primary test:
- enrichment or association between prophage RBP modules and host K/O types.

Expected result:
- prophage-derived candidates include modules absent from cultured phage catalogs.

Alternative explanation:
- some prophage proteins may be nonfunctional remnants or incorrectly predicted RBPs.

Output:
- `results/rbp_depolymerase/novel_candidates.tsv`
- `results/models/model_comparison.tsv` (`record_type_vs_rbp_modules` summary)
- Figure 3 or Figure 4.

## H3: Broad-Host-Range Phages Are Enriched for Modular RBPs and Counter-Defense Genes

Input data:
- phage host-range metadata where available;
- RBP domain architectures;
- anti-defense candidate genes.

Required features:
- host-range breadth estimate;
- RBP modularity metrics;
- anti-defense gene counts or categories.

Primary test:
- compare modularity and anti-defense burden between broad-range and narrow-range phages.

Expected result:
- broad-range phages show more modular RBPs and/or more counter-defense genes.

Alternative explanation:
- broad host range may reflect laboratory testing depth rather than biology.

Output:
- `results/models/feature_importance.tsv`
- `results/models/model_comparison.tsv` (`rbp_modules_vs_counterdefense` summary)
- Figure 3 or Figure 5.

## H4: Receptor Plus Defense/Counter-Defense Models Improve Compatibility Prediction

Input data:
- RBP/depolymerase features;
- host K/O features;
- host defense-system features;
- phage anti-defense features.

Required features:
- receptor compatibility indicators;
- defense-system burden or categories;
- phage counter-defense candidates.

Primary test:
- compare receptor-only models with receptor plus defense/counter-defense models.

Expected result:
- combined models explain host-range gaps better than receptor features alone.

Alternative explanation:
- missing adsorption or infection assay data may limit validation.

Output:
- `results/models/model_comparison.tsv`
- Figure 5.

## H5: Clinically Important Klebsiella Lineages Have Distinct Prophage and Defense Repertoires

Input data:
- host ST, AMR, virulence, and species-complex annotations;
- prophage carriage;
- defense-system predictions.

Required features:
- ST and clinical marker categories;
- prophage counts and module classes;
- defense-system categories.

Primary test:
- lineage-level association tests between host background, prophage content, and defense burden.

Expected result:
- high-risk lineages differ in prophage and defense-system profiles.

Alternative explanation:
- public genome collections may overrepresent outbreaks or specific surveillance projects.

Output:
- `results/host_features/host_metadata.tsv`
- `results/defense_systems/host_defense_systems.tsv`
- `results/models/model_comparison.tsv` (`st_vs_defense_status` summary)
- Figure 6.


## H6: Novel RBP Candidates Are Enriched in Under-Sampled Sources or Singleton Clusters

Input data:
- phage source metadata from the manifest;
- dereplicated species-like cluster assignments;
- RBP/depolymerase novelty tiers.

Required features:
- source or source-group metadata;
- singleton versus multi-genome species-like cluster status;
- RBP/depolymerase novelty status.

Primary test:
- group-rate summaries comparing source strata and species-like cluster size bins against RBP/depolymerase novelty status.

Expected result:
- under-sampled or singleton-cluster phages are enriched for tier 1 or tier 2 RBP/depolymerase candidates.

Alternative explanation:
- apparent source enrichment may reflect metadata bias or uneven annotation depth rather than true ecological enrichment.

Output:
- `results/rbp_depolymerase/novel_candidates.tsv`
- `results/models/model_comparison.tsv` (`source_vs_rbp_novelty` and `cluster_size_vs_rbp_novelty` summaries)
- Figure 6.

## Source Unlock Planning

`results/qc/hypothesis_source_unlock_plan.tsv` maps H1-H6 to the reviewed source exports required for a minimum real-data test. `results/qc/hypothesis_source_unlock_matrix.tsv` records the source-by-hypothesis curation state. These files are planning aids; biological claims still require populated downstream outputs and validation.
