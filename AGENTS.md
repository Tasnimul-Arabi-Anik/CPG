# AGENTS.md

## Project Identity

This repository is for a Klebsiella phage comparative genomics study.

The study prioritizes novelty. Avoid framing the project as only "we sequenced and annotated new phages." The main scientific angle is:

Klebsiella phage host range is shaped by two genomic filters:
1. receptor compatibility: RBP/depolymerase modules versus capsule/LPS type;
2. intracellular compatibility: bacterial defense systems versus phage anti-defense genes.

## Main Hypotheses

H1. RBP/depolymerase module architecture predicts host K/O association better than whole-genome phage taxonomy.

H2. Klebsiella prophages encode an under-sampled reservoir of capsule-recognition proteins.

H3. Broad-host-range phages are enriched for modular RBPs, recombination signatures, and/or anti-defense genes.

H4. Host defense/counter-defense compatibility explains host-range gaps that receptor-binding predictions alone cannot explain.

H5. Clinically important Klebsiella lineages differ in prophage content, defense-system burden, and predicted phage susceptibility.

H6. Novel RBP/depolymerase candidates are enriched in under-sampled ecological sources or singleton species-like phage clusters.

## Preferred Analysis Layers

Always organize the analysis into these layers:

1. Dataset curation
   - Collect cultured Klebsiella phages.
   - Collect Klebsiella prophages if host genomes are available.
   - Keep metagenomic viral contigs separate unless explicitly asked to merge them.
   - Record source, accession, host, isolation metadata, genome size, GC, completeness, and lifestyle.

2. Phage genome comparison
   - QC and remove poor-quality genomes.
   - Dereplicate genomes.
   - Compute ANI or intergenomic similarity.
   - Build gene-sharing networks.
   - Compare synteny and modular genome organization.

3. RBP/depolymerase discovery
   - Predict tail fibers, tailspikes, receptor-binding proteins, and depolymerases.
   - Use both sequence-based and structure-informed annotation when possible.
   - Segment multidomain proteins where possible.
   - Do not rely on BLAST alone for novelty claims.

4. Host annotation
   - Assign Klebsiella species complex member where possible.
   - Assign MLST, K-locus, O-locus, AMR genes, and virulence markers.
   - Keep host metadata linked to phage or prophage records.

5. Defense/counter-defense analysis
   - Annotate bacterial antiviral defense systems.
   - Annotate phage anti-defense and DNA-modification genes.
   - Test whether defense/counter-defense features improve host-range prediction.

6. Statistical modeling
   - Compare taxonomy-only, whole-genome similarity, RBP/depolymerase, host K/O, host defense, and combined models.
   - Prefer interpretable models before complex models.
   - Always report assumptions and missing metadata.

7. Figures and manuscript outputs
   - Produce publication-ready tables and figures.
   - Keep figure source data in results/.
   - Update docs/methods.md when tools or thresholds change.

## Execution Guardrails

No infrastructure-only PRs. Do not add new planners, audits, schemas, dashboards, wrappers, or workflow layers unless a current real-data analysis cannot proceed without them.

Prioritize, in order:

1. accepted external-tool evidence;
2. scientifically valid comparisons;
3. new outcome or validation data;
4. compact reviewable results.

When evidence comes from PHROGs/MMseqs profile matches, describe it as profile-family or homology-fingerprint evidence unless overlapping hits have been resolved into non-overlapping biological domains. Do not call current ordered profile-hit strings true RBP architecture.

## Coding Rules

- Use Python for data tables, parsing, statistics, and figure source generation.
- Use Snakemake or Nextflow for reproducible workflow orchestration.
- Use conda/mamba environment files where possible.
- Never hard-code file paths that should be in config/.
- Never modify files in data/raw/.
- Write outputs to results/.
- Write logs to logs/.
- Keep scripts modular and restartable.
- Prefer TSV/CSV/Parquet outputs with clear schemas.

## Documentation Rules

Whenever adding or changing an analysis step, update:
- docs/methods.md
- docs/hypotheses.md if the change affects a hypothesis
- docs/figure_plan.md if the change affects a figure
- README.md if the command to run the workflow changes

## Validation Rules

Before saying a step is complete, check:
- the script runs on a small test input or dry run;
- output files are created where expected;
- column names are documented;
- assumptions are stated;
- failures are logged clearly.

## Novelty Standard

Do not claim novelty merely because a genome is newly assembled or annotated.

Prefer novelty claims based on:
- novel RBP/depolymerase modules;
- remote structural homologs missed by sequence annotation;
- prophage-derived receptor-binding candidates;
- combined receptor plus defense/counter-defense prediction;
- under-sampled host K/O types;
- clinically relevant Klebsiella lineages;
- reproducible prioritization of phages for experimental testing.

## Response Style

When reporting progress:
- summarize what changed;
- list files edited;
- list commands run;
- list outputs generated;
- list remaining uncertainties;
- suggest the next concrete step.
