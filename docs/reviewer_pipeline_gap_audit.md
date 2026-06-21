# Reviewer Pipeline Gap Audit

This document separates the current reproducible bridge workflow from the production-grade pipeline needed for a final Genome Biology-level manuscript. The workflow also generates `results/qc/production_evidence_handoff.md` from current evidence audits so these gaps remain synchronized with the repository state, and `results/validation/pipeline_efficiency_audit.tsv` to make staged source scope, dereplication, source-overlap auditing, raw-data boundaries, and bridge-versus-production evidence separation explicit for reviewers.

## Current Position

The repository currently supports reviewed source curation, accession-backed metadata, sequence-fetch review packets, production benchmark receptor evidence for the PhageHostLearn assay phages, host K/O typing evidence for the assay hosts, phage genome-similarity baselines, DefenseFinder host-defense evidence, explicit Phold ACR candidate evidence, figure source generation, and claim audits. The latest cross-PR status is summarized in `docs/current_analysis_status.md`, and the tracked production tool/evidence manifest is `data/metadata/production_evidence/production_tool_run_manifest.tsv`.

The current workflow is useful for controlled development and early real-data unlocks. It is not yet the final standardized comparative-genomics pipeline.

## Reviewer-Sensitive Gaps

| Analysis layer | Current implementation | Reviewer risk | Production-grade expectation | Status |
| --- | --- | --- | --- | --- |
| Source curation | Reviewed INPHARED seed, NCBI seed, one host, one prophage | Dataset is still a seed, not comprehensive | Expand to public-scale cultured phages, host genomes, and prophages with deduplication and source overlap audits | In progress |
| Sequence acquisition | Local FASTA for initial records plus checksum-backed acquisition manifest and review packet | Metadata-only rows and unexpanded seed files cannot support genome-level manuscript claims | Acquire reviewed FASTA files for the expanded dataset, validate checksums, rerun sequence QC, and keep raw data immutable | In progress |
| Genome similarity | BLASTN, fastANI, and skani benchmark similarity baselines for the 105 assay phages | These benchmark baselines are not a public-scale phage atlas clustering run | VIRIDIC or documented all-vs-all Mash/ANI-style comparison across the expanded sequence-backed atlas | Benchmark implemented; atlas-scale analysis pending |
| Annotation | Sequence-backed CDS annotations for 105 assay phages plus receptor-domain and Phold/Foldseek receptor-like evidence | Benchmark evidence is not a comprehensive public-scale reannotation | Standardized Pharokka/PHROGs plus reviewed domain/structural evidence across all sequence-backed phage/prophage genomes | Benchmark implemented; atlas-scale analysis pending |
| RBP/depolymerase evidence | 495 PHROGs/MMseqs receptor-domain rows and 23 Phold/Foldseek receptor-like structural rows for assay phages | Current coarse receptor-source/count summaries did not outperform genome-similarity plus K/O in the primary cold-phage-cluster benchmark; cold-K support diagnostics show asymmetric fallback behavior; full module architecture remains untested | Expand/curate receptor evidence and test external/generalization cohorts before claiming superiority | Benchmark implemented; claim not supported |
| Host K/O/ST/AMR/virulence | 200 Kaptive host rows and 188 Kleborate host rows for the assay benchmark | Benchmark host typing supports H1 benchmarking but not a broad host-population analysis | Public-scale Klebsiella host panel typed with fixed Kleborate/Kaptive versions and source/lineage covariates | Benchmark implemented; public-scale analysis pending |
| Defense/counter-defense | 2,758 DefenseFinder host-defense rows and 7 explicit Phold ACR candidates; annotation-keyword hits remain screening-only | No productive-infection/plaque/EOP outcomes exist, so H4 cannot be tested | Curate productive-infection outcomes before testing whether defense/counter-defense improves prediction | Evidence layer implemented; H4 blocked |
| Statistical modeling | 10,006 spot-test pairs support H1 initial-interaction benchmarking; H3 has descriptive spot breadth; H4 is blocked | Spot tests are not productive infection, and current H1 coarse receptor-source/count summaries do not beat genome-similarity plus K/O baselines | Leakage-safe grouped analyses with appropriate outcomes, uncertainty, and claim audits after each evidence expansion | H1 benchmark implemented; H4 blocked |
| Claims | Claim ledger blocks biological result claims | Strong claims would overstate bridge evidence | Keep only workflow/resource claims until claim-support audit allows stronger wording | Implemented |

## Reviewer-Safe Wording

Allowed current wording:

> The repository implements a reproducible, config-driven benchmark workflow with reviewed spot-test outcomes, production receptor evidence, host K/O typing evidence, genome-similarity baselines, and host defense/phage anti-defense candidate evidence for the PhageHostLearn benchmark.

Not allowed yet:

> RBP/depolymerase and defense/counter-defense features explain Klebsiella phage host range better than taxonomy.

## Next Production Steps

1. Review and merge the current PR stack in order: #12, #13, then #14.
2. After merge, rerun the production workflow and claim audits from the merged `main` state.
3. Curate productive-infection, plaque, propagation, or EOP outcomes before testing H4.
4. Expand beyond the PhageHostLearn benchmark into a public-scale atlas with reviewed source deduplication, sequence acquisition, standardized annotation, and genome-similarity clustering.
5. Re-run H1-H6 model comparisons and claim audits before strengthening manuscript claims.
