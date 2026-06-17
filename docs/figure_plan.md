# Figure Plan

## Figure 1: Dataset and Phage Diversity Atlas

Purpose:
- show cultured phages, prophages, and optional metagenomic viral contigs after QC and dereplication.

Expected source data:
- `results/qc/phage_genome_manifest.tsv`
- `results/clusters/phage_clusters.tsv`

## Figure 2: Klebsiella Phage Pangenome

Purpose:
- show core/accessory gene clusters, genome modules, synteny blocks, and accessory hotspots.

Expected source data:
- `results/annotations/gene_clusters.tsv`
- `results/annotations/pangenome_matrix.tsv`

## Figure 3: RBP/Depolymerase Structural Module Network

Purpose:
- show sequence clusters, structural clusters, predicted depolymerases, and domain sharing between distant phages.

Expected source data:
- `results/rbp_depolymerase/candidates.tsv`
- `results/rbp_depolymerase/domain_architectures.tsv`
- `results/rbp_depolymerase/module_clusters.tsv`

## Figure 4: Host K/O Association Map

Purpose:
- link phage RBP modules or prophage protein clusters to Klebsiella K-loci and O-loci.

Expected source data:
- `results/host_features/host_metadata.tsv`
- `results/host_features/phage_host_links.tsv`
- `results/rbp_depolymerase/module_clusters.tsv`

## Figure 5: Defense/Counter-Defense Compatibility Model

Purpose:
- compare host defense systems, phage counter-defense features, and compatibility predictions.

Expected source data:
- `results/defense_systems/host_defense_systems.tsv`
- `results/defense_systems/phage_antidefense_candidates.tsv`
- `results/defense_systems/compatibility_features.tsv`
- `results/host_features/phage_host_links.tsv`
- `results/models/model_comparison.tsv`

## Figure 6: Novelty and Translational Prioritization

Purpose:
- rank phage clusters and RBP candidates by novelty, host relevance, predicted capsule target, and absence of undesirable genes.

Expected source data:
- `results/rbp_depolymerase/novel_candidates.tsv`
- `results/host_features/host_metadata.tsv`
- `results/host_features/phage_host_links.tsv`
- `results/models/feature_importance.tsv`
- `results/qc/phage_genome_manifest.tsv`
