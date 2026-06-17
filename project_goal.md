# Project Goal: Klebsiella Phage Comparative Genomics

## Working Title

Structural pangenomics reveals receptor-binding and counter-defense modules shaping Klebsiella phage host range.

## Study Motivation

Klebsiella phage host range is often discussed through capsule recognition, but receptor binding alone may not explain infection success. This study tests whether host-range prediction improves when receptor-binding/depolymerase modules are analyzed together with bacterial defense systems and phage counter-defense genes.

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

Test whether host defense systems and phage anti-defense genes explain host-range patterns beyond receptor-binding modules.

## Primary Hypotheses

H1. RBP/depolymerase modules predict host K/O association better than phage taxonomy.

H2. Prophages contain an under-sampled reservoir of Klebsiella capsule-recognition proteins.

H3. Broad-host-range phages are enriched for modular RBPs and counter-defense genes.

H4. A combined receptor + defense/counter-defense model predicts host compatibility better than receptor features alone.

H5. Clinically relevant Klebsiella lineages differ in prophage content, defense-system burden, and predicted phage susceptibility.

H6. Novel RBP/depolymerase candidates are enriched in under-sampled sources or singleton species-like phage clusters.

## Definition of Done

The computational study is ready for manuscript drafting when:

- all data inputs are listed in config/samples.tsv;
- all scripts run from a clean checkout;
- all parameters are in config files;
- all major outputs are in results/;
- all major figures have source data;
- docs/methods.md describes the pipeline;
- docs/hypotheses.md maps each hypothesis to a specific test;
- docs/limitations.md separates computational predictions from experimentally validated conclusions.
- docs/claim_ledger.md records supported claims, data-dependent claims, and remaining speculative claims.
