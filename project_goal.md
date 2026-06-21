# Project Goal: Klebsiella Phage Comparative Genomics

## Working Title

A comparative-genomics framework for receptor-binding and counter-defense modules shaping Klebsiella phage host range.

## Study Motivation

Klebsiella phage host range is often discussed through capsule recognition, but receptor binding alone may not explain infection success. The broader biological program asks whether host-range prediction improves when receptor-binding/depolymerase modules are analyzed together with bacterial defense systems and phage counter-defense genes. Pairwise host-range and productive-infection claims require explicit tested phage-host assay outcomes, including tested negatives; metadata host links alone are not response variables.

## Scope and Completion Endpoint

Current completion endpoint: a reproducible dry-lab benchmark and evidence resource for receptor-layer spot-test interaction analysis, with exploratory secondary analyses for prophage coverage, spot-breadth associations, host-defense burden, and source/cluster novelty. This endpoint is complete when the workflow runs from config, writes outputs under `results/`, preserves claim boundaries, and explicitly records unsupported endpoints.

Extended biological endpoint: testing whether defense/counter-defense improves productive-infection prediction among receptor-compatible pairs. This remains future work because the current PhageHostLearn benchmark contains spot-test outcomes but no plaque, EOP, propagation, or productive-infection labels. H4 is therefore a non-blocking limitation for the current dry-lab endpoint and remains blocked for any productive-infection claim.

## Central Hypothesis

Klebsiella phage host range is jointly predicted by:
1. phage RBP/depolymerase module architecture;
2. host K/O surface antigen type;
3. host antiviral defense-system burden;
4. phage anti-defense and DNA-modification genes.

## Specific Aims

### Aim 1: Build a Curated Klebsiella Phage Atlas

Create a dereplicated dataset of cultured Klebsiella phages and, if host genomes are available, Klebsiella prophages.

### Aim 2: Discover Receptor-Binding and Depolymerase Modules

Identify candidate RBPs, tailspikes, tail fibers, and depolymerases using sequence, domain, synteny, and structure-informed evidence.

### Aim 3: Link Phage Modules to Host K/O/ST/AMR/Virulence Background

Use host genomic features to test whether receptor-binding modules associate with specific capsule or LPS types.

### Aim 4: Add Defense/Counter-Defense Compatibility

For the current dry-lab endpoint, provide host-defense and phage anti-defense candidate evidence as a coverage/resource layer and keep productive-infection interpretation blocked. The extended biological test is whether host defense systems and phage anti-defense genes explain productive-infection outcomes beyond receptor-binding modules once plaque, EOP, propagation, or productive-infection labels are curated.

## Primary Hypotheses

H1. RBP/depolymerase modules predict K/O tropism among known positives and, once assay matrices are curated, pairwise receptor compatibility better than phage taxonomy.

H2. Prophages contain an under-sampled reservoir of Klebsiella capsule-recognition proteins.

H3. Broad-host-range phages are enriched for modular RBPs and counter-defense genes.

H4. Among receptor-compatible or initial-interaction-positive tested pairs, defense/counter-defense features improve productive-infection prediction beyond receptor features alone.

H5. Clinically relevant Klebsiella lineages differ in prophage content and defense-system burden; any predicted phage susceptibility claims require separate validated assay models.

H6. Novel RBP/depolymerase candidates are enriched in under-sampled sources or singleton species-like phage clusters.

## Definition of Done

The computational study is ready for manuscript drafting when:

- all data inputs are listed in config/samples.tsv and assay outcome inputs are tracked in data/metadata/phage_host_assays.tsv when host-range claims are made;
- all scripts run from a clean checkout;
- all parameters are in config files;
- all major outputs are in results/;
- assay feature coverage is audited so missing biological evidence is not treated as feature absence;
- all major figures have source data;
- docs/methods.md describes the pipeline;
- docs/hypotheses.md maps each hypothesis to a specific test and marks productive-infection H4 claims blocked until valid outcomes exist, while treating the H4 endpoint gap as a documented non-blocking limitation for the current dry-lab benchmark/resource endpoint;
- docs/limitations.md separates computational predictions from experimentally validated conclusions.
- docs/claim_ledger.md records supported claims, data-dependent claims, and remaining speculative claims.
