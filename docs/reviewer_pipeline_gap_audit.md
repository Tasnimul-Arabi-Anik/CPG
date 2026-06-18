# Reviewer Pipeline Gap Audit

This document separates the current reproducible bridge workflow from the production-grade pipeline needed for a final Genome Biology-level manuscript. The workflow also generates `results/qc/production_evidence_handoff.md` from current evidence audits so these gaps remain synchronized with the repository state, and `results/validation/pipeline_efficiency_audit.tsv` to make staged source scope, dereplication, source-overlap auditing, raw-data boundaries, and bridge-versus-production evidence separation explicit for reviewers.

## Current Position

The repository currently supports reviewed source curation, accession-backed metadata, sequence-fetch review packets, GenBank CDS bridge annotations, provisional pangenome tables, RBP/depolymerase candidate prioritization, defense/counter-defense feature tables, model-comparison scaffolds, figure source generation, and claim audits.

The current workflow is useful for controlled development and early real-data unlocks. It is not yet the final standardized comparative-genomics pipeline.

## Reviewer-Sensitive Gaps

| Analysis layer | Current implementation | Reviewer risk | Production-grade expectation | Status |
| --- | --- | --- | --- | --- |
| Source curation | Reviewed INPHARED seed, NCBI seed, one host, one prophage | Dataset is still a seed, not comprehensive | Expand to public-scale cultured phages, host genomes, and prophages with deduplication and source overlap audits | In progress |
| Sequence acquisition | Local FASTA for initial records; NCBI accessions have fetch commands and review packet | Metadata-only rows cannot support genome-level claims | Acquire reviewed FASTA files, rerun sequence QC, and keep raw data immutable | In progress |
| Genome similarity | Local BLASTN pairwise baseline | BLASTN baseline is not the standard species-like phage clustering method | VIRIDIC or documented all-vs-all Mash/ANI-style comparison across sequence-backed phages/prophages | Planned |
| Annotation | GenBank CDS product bridge evidence | GenBank submitter annotations are heterogeneous | Standardized Pharokka/PHROGs annotation on all sequence-backed phage/prophage genomes | Planned |
| RBP/depolymerase evidence | Keyword, synteny, length, and provisional gene-cluster evidence | Product keywords alone are weak for novelty/function | Add domain/profile evidence and structural/remote-homology evidence such as Phold/Foldseek-style annotations | Planned |
| Host K/O/ST/AMR/virulence | One reviewed host row with K/O/ST metadata | Insufficient host diversity for H1/H2/H5 | Public-scale Klebsiella host panel typed with Kleborate/Kaptive or reviewed equivalent outputs | In progress |
| Defense/counter-defense | Phage anti-defense inferred from annotation keywords; host defense table empty | Intracellular compatibility claims are weak without host defense calls | DefenseFinder/PADLOC host defense calls and curated phage anti-defense evidence | Planned |
| Statistical modeling | H3/H4 are explicit blocked rows pending assay outcomes; H1/H2/H5/H6 remain scaffold/proxy tests | Host-range breadth and productive infection cannot be tested without an assay matrix | Import tested phage-host matrices, then model K/O receptor compatibility and productive-infection outcomes with grouped splits | In progress |
| Claims | Claim ledger blocks biological result claims | Strong claims would overstate bridge evidence | Keep only workflow/resource claims until claim-support audit allows stronger wording | Implemented |

## Reviewer-Safe Wording

Allowed current wording:

> The repository implements a reproducible, curation-first comparative-genomics framework and early real-data bridge evidence for testing receptor-binding plus defense/counter-defense hypotheses in Klebsiella phages.

Not allowed yet:

> RBP/depolymerase and defense/counter-defense features explain Klebsiella phage host range better than taxonomy.

## Next Production Steps

1. Acquire reviewed FASTA files for the NCBI seed phages through the sequence fetch review packet.
2. Replace or supplement GenBank CDS bridge evidence with standardized Pharokka/PHROGs output.
3. Generate production all-vs-all genome similarity using VIRIDIC, Mash, or another documented method.
4. Add RBP/depolymerase domain and structural evidence.
5. Add public-scale Klebsiella host genomes with Kleborate/Kaptive and host-defense calls.
6. Re-run H1-H6 model comparisons and claim audits before strengthening manuscript claims.
