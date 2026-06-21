# Hypothesis-to-Analysis Map

This map separates metadata associations from tested phage-host outcomes. Host-range prediction, broad-host-range breadth, and productive-infection claims require curated rows in `results/<profile>/metadata/phage_host_assays.tsv`. Isolation host, reported host, prophage resident host, and predicted host relationships are tracked separately in `results/<profile>/metadata/phage_host_relationships.tsv` and are not infection labels.

## H1a: RBP/Depolymerase Modules Predict K/O Tropism Among Known Positive Associations

Input data:
- dereplicated phage clusters;
- RBP/depolymerase candidate modules;
- curated positive host associations or assay-positive phage-host rows;
- host K/O metadata.

Required features:
- phage taxonomy or genome-similarity cluster;
- RBP/depolymerase gene cluster or domain architecture;
- host K type and O type;
- evidence tier distinguishing assay-positive, reported-host, and metadata-only links.

Primary test:
- compare taxonomy-only, genome-similarity, RBP/depolymerase, and combined feature sets for K/O tropism among curated positive associations.

Current readiness:
- reviewed spot-positive assay rows exist in the seed profile, but H1a remains blocked for claim use until the corresponding host K/O metadata and production RBP/depolymerase evidence are available.

Output:
- `results/models/model_comparison.tsv`
- Figure 4 or Figure 5.

## H1b: RBP/Depolymerase Modules Predict Pairwise Receptor Compatibility

Input data:
- `results/<profile>/metadata/phage_host_assays.tsv` with tested positive and tested negative pairs;
- host K/O metadata;
- RBP/depolymerase candidate modules.

Required features:
- explicit `tested=true` pairwise rows;
- adsorption, spot, plaque, EOP, or other initial-interaction outcome labels;
- phage taxonomy, genome similarity, and RBP/depolymerase features;
- host K/O or other receptor features.

Primary test:
- compare receptor-feature models against taxonomy and genome-similarity baselines under grouped train/test splits.

Current readiness:
- seed profile contains 10,006 reviewed PhageHostLearn spot-test pairs, so H1b has an initial-interaction endpoint;
- Stage 7 reports assay-feature coverage and keeps RBPbase/Locibase bridge metadata as seed metadata coverage only;
- this readiness step does not emit pair-level H1b model-performance rows from bridge metadata;
- receptor-feature interpretation remains conservative until grouped cold-host/cold-phage/cold-study evaluation with uncertainty analysis supports a specific claim. The production PhageHostLearn host layer now provides K/O result rows for 200/200 assay hosts (Typeable K 196/200; Typeable O 191/200) and ST calls for 188/200 assay hosts. The production phage layer provides baseline Prodigal CDS predictions for 105/105 assay phages, 247 exact RBPbase ML candidate matches across 103/105 assay phages, PHROGs/MMseqs receptor-domain evidence for 242 proteins, and partial accepted Phold/Foldseek structural evidence for 12/105 assay phages and 1,048/10,006 tested pairs. These remain candidate-level receptor, domain-profile, and structural-homology features, not functional receptor-specificity evidence.

Output:
- `results/<profile>/qc/assay_feature_coverage.tsv` H1b coverage rows;
- `results/models/hypothesis_summary.tsv` H1 row.

## H2: Prophages Are an Under-Sampled Reservoir of Capsule-Recognition Proteins

Input data:
- prophage sequences from Klebsiella host genomes;
- host K/O calls;
- RBP/depolymerase candidate annotations;
- domain or structure-informed evidence when available.

Required features:
- prophage-host resident relationship;
- candidate RBP/depolymerase evidence;
- K/O calls;
- controls for prophage length, protein count, genome completeness, and annotation depth when the cohort is large enough.

Primary test:
- association between prophage RBP modules and host K/O types, with novelty prioritization for candidates missed by sequence-only annotation.

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
- explicit tested host panels from `results/<profile>/metadata/phage_host_assays.tsv`;
- RBP domain architectures;
- anti-defense candidate genes.

Required features:
- tested-host denominator for each phage;
- susceptible-host numerator for each phage;
- breadth across hosts, K types, and lineages;
- RBP modularity metrics;
- anti-defense gene counts or categories.

Primary test:
- first retain continuous panel breadth values (`tested_host_count`, `spot_positive_host_count`, `spot_positive_fraction`, Wilson interval for the observed tested-panel spot-positive proportion, `study_id`, and `panel_id`); then compare modularity and anti-defense burden only after feature coverage is actually assessed and minimum group-size thresholds are satisfied.

Current readiness:
- panel-based spot-test breadth values are available from the reviewed PhageHostLearn subset in the seed profile; these represent initial-interaction breadth only.
- Stage 7 reports `descriptive_breadth_available` and keeps feature associations claim-blocked unless the relevant assay-phage features have actually been assessed.
- biological H3 claims remain blocked until production RBP/depolymerase modularity, domain/structural support where needed, broader explicit phage counter-defense evidence, and panel-aware association tests are available for the assay phages. Current Phold ACR anti-CRISPR evidence covers only 7/105 assay phages.

Alternative explanation:
- broad host range may reflect laboratory testing depth rather than biology.

Output:
- `results/<profile>/qc/assay_feature_coverage.tsv` rows `spot_breadth_continuous`, RBP coverage, and counter-defense coverage;
- `results/models/model_comparison.tsv` rows `spot_breadth_descriptive`, `spot_breadth_vs_rbp_candidates`, and `spot_breadth_vs_counterdefense_candidates`;
- Figure 3 or Figure 5.

## H4: Defense/Counter-Defense Improves Productive-Infection Prediction Among Receptor-Compatible Pairs

Input data:
- tested phage-host assay outcomes;
- receptor compatibility features;
- host defense-system features;
- phage counter-defense features.

Required features:
- receptor compatibility or initial-interaction labels;
- productive-infection, plaque, EOP, or explicitly curated infection labels;
- host defense-system burden or categories;
- phage counter-defense candidates with evidence tiers.

Primary test:
- compare receptor-only, defense-only, counter-defense-only, receptor-plus-defense, and receptor-plus-defense/counter-defense models against observed assay outcomes.

Current readiness:
- host DefenseFinder evidence is available for 200/200 assay hosts, and sparse Phold ACR anti-CRISPR evidence is available for 7/105 assay phages. H4 remains blocked until productive-infection labels exist and counter-defense coverage is sufficient for the tested pairs. `compatibility_feature_status` and `matched_counterdefense_status` are not biological outcomes because they are constructed from the same features being modeled.

Expected result:
- defense/counter-defense features may explain some receptor-compatible failures, but a robust null result is allowed.

Alternative explanation:
- adsorption-related factors may dominate; defense-system annotations may be incomplete or condition-specific.

Output:
- future leakage-safe pairwise model rows in `results/models/model_comparison.tsv`
- Figure 5.

## H5: Clinically Important Klebsiella Lineages Have Distinct Prophage and Defense Repertoires

Input data:
- host ST, AMR, virulence, and species-complex annotations;
- prophage carriage;
- defense-system predictions.

Required features:
- ST and clinical marker categories;
- prophage counts and module classes;
- defense-system categories;
- sampling source and genome-quality covariates when available.

Primary test:
- lineage-level association tests between host background, prophage content, and defense burden.

Current readiness:
- production PhageHostLearn host typing provides K/O result rows for 200/200 assay hosts (Typeable K 196/200; Typeable O 191/200) and ST calls for 188/200 assay hosts;
- H5 has benchmark host-defense evidence from DefenseFinder, but remains blocked for biological interpretation because broader host-population sampling, prophage carriage, and lineage/source controls are not yet available;
- separate host-population analysis; not a phage infectivity claim.

Alternative explanation:
- public genome collections may overrepresent outbreaks or specific surveillance projects.

Output:
- `results/host_features/host_metadata.tsv`
- `results/defense_systems/host_defense_systems.tsv`
- `results/models/model_comparison.tsv` (`st_vs_defense_status` summary)
- Figure 6.

## H6: Novel RBP Candidates Are Enriched in Under-Sampled Ecological Sources or Singleton Clusters

Input data:
- ecological source metadata from curated sources;
- dereplicated species-like cluster assignments;
- RBP/depolymerase novelty tiers.

Required features:
- ecological source, not only database provenance;
- singleton versus multi-genome species-like cluster status;
- RBP/depolymerase novelty status;
- controls for sequence completeness, annotation depth, genome size, protein count, and sampling effort.

Primary test:
- group-rate summaries comparing ecological source strata and species-like cluster size bins against RBP/depolymerase novelty status.

Current readiness:
- exploratory until ecological source is normalized separately from database source.

Alternative explanation:
- apparent source enrichment may reflect metadata bias or uneven annotation depth rather than true ecological enrichment.

Output:
- `results/rbp_depolymerase/novel_candidates.tsv`
- `results/models/model_comparison.tsv` (`source_vs_rbp_novelty` and `cluster_size_vs_rbp_novelty` summaries)
- Figure 6.

## Source Unlock Planning

`results/qc/hypothesis_source_unlock_plan.tsv` maps H1-H6 to the reviewed source exports required for a minimum real-data test. `results/qc/hypothesis_source_unlock_matrix.tsv` records the source-by-hypothesis curation state. These files are planning aids; biological claims still require populated downstream outputs, assay outcomes where relevant, and validation.
