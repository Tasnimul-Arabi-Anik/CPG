# Reviewer Pipeline Gap Audit

This document separates the current reproducible bridge workflow from the production-grade pipeline needed for a final Genome Biology-level manuscript. The workflow also generates `results/qc/production_evidence_handoff.md` from current evidence audits so these gaps remain synchronized with the repository state, and `results/validation/pipeline_efficiency_audit.tsv` to make staged source scope, dereplication, source-overlap auditing, raw-data boundaries, and bridge-versus-production evidence separation explicit for reviewers.

## Current Position

The repository currently supports reviewed source curation, accession-backed metadata, sequence-fetch review packets, GenBank CDS bridge annotations, provisional pangenome tables, RBP/depolymerase candidate prioritization, defense/counter-defense feature tables, model-comparison scaffolds, figure source generation, and claim audits.

The current workflow is useful for controlled development and early real-data unlocks. It is not yet the final standardized comparative-genomics pipeline.

## Reviewer-Sensitive Gaps

| Analysis layer | Current implementation | Reviewer risk | Production-grade expectation | Status |
| --- | --- | --- | --- | --- |
| Source curation | Reviewed INPHARED seed, NCBI seed, one host, one prophage | Dataset is still a seed, not comprehensive | Expand to public-scale cultured phages, host genomes, and prophages with deduplication and source overlap audits | In progress |
| Sequence acquisition | Local FASTA for initial records plus checksum-backed acquisition manifest and review packet | Metadata-only rows and unexpanded seed files cannot support genome-level manuscript claims | Acquire reviewed FASTA files for the expanded dataset, validate checksums, rerun sequence QC, and keep raw data immutable | In progress |
| Genome similarity | Production BLASTN pairwise baseline across 107 sequence-QC-passing phage-like records; Mash, fastANI, and skani robustness baselines across 105 assay phages | BLASTN/Mash/fastANI/skani baselines are useful for reproducible benchmarking but are not final public-scale species-like phage clustering methods | VIRIDIC or documented phage-appropriate all-vs-all comparison across the expanded sequence-backed phage/prophage set | Baselines available; public-scale manuscript taxonomy still planned |
| Annotation | GenBank CDS product bridge evidence | GenBank submitter annotations are heterogeneous | Standardized Pharokka/PHROGs annotation on all sequence-backed phage/prophage genomes | Planned |
| RBP/depolymerase evidence | Sequence-backed Prodigal CDS predictions for 105/105 assay phages; 247 exact RBPbase ML candidate matches across 103/105 phages; PHROGs/MMseqs receptor-domain evidence for 242 proteins; partial mapped Phold/Foldseek structural evidence for 12/105 assay phages | RBPbase, PHROGs/MMseqs, and Phold/Foldseek rows are candidate evidence, not functional receptor-specificity proof; the PHROGs expansion increases review burden and must not be treated as activity validation | Manually review domain/structural candidates for confidence, coverage, synteny, product specificity, and overlap with RBPbase/Pharokka before biological claims | Candidate, domain, and partial structural evidence available |
| Host K/O/ST/AMR/virulence | Reviewed PhageHostLearn production Kaptive K/O result rows for 200/200 assay hosts (Typeable K 196/200; Typeable O 191/200) and Kleborate KpSC rows for 188/200 assay hosts | Host receptor features are now available for the benchmark panel, but 12 hosts lack Kleborate ST/AMR/virulence rows and host raw-sequence paths remain unverified in the manifest | Resolve remaining host ST gaps if needed and preserve Kaptive/Kleborate confidence during receptor modeling | Partial production evidence |
| Defense/counter-defense | Annotation-keyword phage anti-defense screening is available only as non-accepted review candidates; host defense table empty | Intracellular compatibility claims are blocked without accepted host defense calls and explicit phage anti-defense evidence | DefenseFinder/PADLOC host defense calls and curated phage anti-defense evidence | Planned |
| Statistical modeling | PhageHostLearn spot-test outcomes support initial-interaction and descriptive panel-breadth audits; candidate-level RBPbase, PHROGs/MMseqs domain, and partial Phold/Foldseek structural evidence are available for the benchmark phages; H4 productive-infection models remain blocked | Spot breadth and receptor candidate features are available, but counter-defense evidence, final public-scale taxonomy, and productive-infection labels are still absent | Keep grouped receptor modeling exploratory; H4 still requires plaque, EOP, propagation, or productive-infection outcomes | In progress |
| Claims | Claim ledger blocks biological result claims | Strong claims would overstate bridge evidence | Keep only workflow/resource claims until claim-support audit allows stronger wording | Implemented |

## Reviewer-Safe Wording

Allowed current wording:

> The repository implements a reproducible, curation-first comparative-genomics framework and early real-data bridge evidence for testing receptor-binding plus defense/counter-defense hypotheses in Klebsiella phages.

Not allowed yet:

> RBP/depolymerase and defense/counter-defense features explain Klebsiella phage host range better than taxonomy.

## Next Production Steps

1. Use the production Prodigal CDS/protein table, exact RBPbase candidate matches, PHROGs/MMseqs domain evidence, and partial Phold/Foldseek structural evidence for candidate-level receptor analyses.
2. Manually review the expanded domain/structural candidate set before treating any row as a publishable receptor-module discovery.
3. Supplement the current BLASTN/Mash/fastANI/skani assay benchmark baselines with VIRIDIC or another documented public-scale phage species-like similarity method before final taxonomy claims.
4. Resolve remaining benchmark host ST gaps if lineage analyses require complete ST/AMR/virulence coverage.
5. Add host-defense and phage counter-defense evidence only after preserving its claim boundary; H4 still needs productive-infection labels.
6. Re-run H1-H6 model comparisons and claim audits before strengthening manuscript claims.
