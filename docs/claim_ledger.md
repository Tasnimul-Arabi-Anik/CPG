# Claim Ledger

This ledger controls how results from this repository should be described in a manuscript or presentation. It separates directly observed workflow outputs, computational inferences, testable hypotheses, and claims that remain speculative until experimental validation is added.

## Claim Status Definitions

| Status | Meaning | Allowed manuscript use |
| --- | --- | --- |
| `workflow_supported` | The pipeline produces the required table, figure source, or validation row. | Methods, resource, or framework claims. |
| `data_dependent` | The workflow can test the claim, but real study data are required before biological conclusions are supported. | State as a hypothesis or planned quantitative test. |
| `computational_inference` | The claim can be supported by model, annotation, or association outputs once populated data pass validation. | Use cautious language such as `associated with`, `predicted`, or `prioritized`. |
| `experimental_validation_required` | The claim requires adsorption, infection, plaque, EOP, biochemical, structural, or genetic validation. | Do not present as proven from this workflow alone. |

## Claims

| Claim ID | Linked hypothesis | Claim type | Required evidence | Current evidence source | Current status | Allowed wording | Forbidden wording |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | H1-H6 | Workflow/resource claim | Config-driven run, schema validation, figure source files, and model rows. | `results/validation/workflow_validation_report.tsv`; `results/mock/validation/workflow_validation_report.tsv` | `workflow_supported` for scaffold and mock workflow; real biological conclusions remain data-dependent. | `The repository implements a reproducible framework for testing receptor and defense/counter-defense hypotheses.` | `The study proves Klebsiella phage host range mechanisms before real data are loaded.` |
| C2 | H1 | RBP/depolymerase modules predict K/O tropism or pairwise receptor compatibility better than taxonomy. | Tested positive and negative assay rows, production receptor/module evidence, host K/O evidence, genome-similarity baselines, grouped model evaluation, and held-out-group uncertainty. | `results/production/model_inputs/receptor_layer_pairwise_features.tsv`; `results/production/receptor_features/assay_phage_module_identity_signatures.tsv`; `results/production/models/receptor_layer_model_pooled_summary.tsv`; `results/production/models/receptor_layer_group_bootstrap_delta.tsv`; `results/production/models/receptor_layer_support_diagnostics.tsv` | `data_dependent`; production H1 benchmark exists and exact unordered module identities improve over RBPbase, but module identities do not robustly outperform BLASTN genome-similarity baselines; ordered per-gene architecture proxies were tested and underperform in cold-phage/cold-cluster splits; cold-K results remain fallback-limited. | `Within the PhageHostLearn spot-test benchmark, exact unordered receptor module identities improve over RBPbase and are competitive with BLASTN genome-similarity baselines under cold-phage-cluster evaluation.` | `RBP modules outperform taxonomy for host range` or `module architecture predicts novel K-locus compatibility` unless supported by paired uncertainty, leakage-safe evaluation, and an appropriate novel-receptor representation. |
| C3 | H2 | Prophages are an under-sampled reservoir of capsule-recognition proteins. | Prophage-linked RBP/depolymerase candidates with K/O host associations and novelty tiers. | `results/rbp_depolymerase/novel_candidates.tsv`; `results/models/model_comparison.tsv`; `results/models/hypothesis_summary.tsv` | `data_dependent`; computational candidates require careful interpretation. | `Prophage-derived candidates are prioritized as a potential reservoir.` | `Prophage proteins are functional capsule-recognition enzymes` without experimental evidence. |
| C4 | H3 | Generalist or broad-host-range phages have more modular RBPs and/or counter-defense genes. | Tested host panels with susceptible-host numerator and tested-host denominator plus RBP modularity and anti-defense burden tests. | `results/<profile>/metadata/phage_host_assays.tsv`; `results/<profile>/qc/assay_feature_coverage.tsv`; `results/validation/phage_host_assay_validation.tsv`; future breadth-aware model rows | `data_dependent`; seed spot-test breadth labels exist, but broad-host-range claims remain blocked until production RBP modularity, counter-defense evidence, and panel/lineage-aware analyses are available. | `The workflow now imports seed spot-test breadth labels and defines the additional production evidence needed to test whether modular RBP and counter-defense burden associate with host-range breadth.` | `Broad host range is caused by modular RBPs` from metadata-only comparisons. |
| C5 | H4 | Receptor plus defense/counter-defense models improve productive-infection prediction among receptor-compatible pairs. | Tested pairwise productive-infection, plaque, or EOP outcomes plus receptor, host-defense, and phage counter-defense features. | `results/<profile>/metadata/phage_host_assays.tsv`; `results/validation/phage_host_assay_validation.tsv`; future leakage-safe pairwise model rows | `data_dependent`; currently blocked because productive-infection labels are absent. | `The workflow defines the assay and evidence requirements for evaluating a second-filter defense/counter-defense model.` | `The model predicts infection success` from compatibility features or metadata host links alone. |
| C6 | H5 | Clinically important lineages carry distinctive prophage and defense repertoires. | Host ST/AMR/virulence metadata, prophage links, defense annotations, and lineage-level summaries. | `results/host_features/host_metadata.tsv`; `results/defense_systems/host_defense_systems.tsv`; `results/models/model_comparison.tsv`; `results/models/hypothesis_summary.tsv` | `data_dependent`; public sampling bias must be assessed. | `Lineage-level differences are tested as associations.` | `Clinical lineages are intrinsically phage-resistant` without controlled sampling and infection assays. |
| C7 | H6 | Novel RBP/depolymerase candidates are enriched in under-sampled sources or singleton phage clusters. | Novelty tiers, source metadata, species-like cluster size, and group-rate summaries. | `results/rbp_depolymerase/novel_candidates.tsv`; `results/models/model_comparison.tsv`; `results/models/hypothesis_summary.tsv`; `results/models/hypothesis_summary.tsv`; Figure 6 source data | `computational_inference` only after populated data pass validation. | `Candidates are prioritized for follow-up based on novelty, source, and cluster context.` | `Novel candidates have confirmed capsule specificity` without biochemical or host-range validation. |
| C8 | H1-H6 | Structural or remote-homology evidence identifies RBP/depolymerase function. | Domain and structural evidence plus synteny and confidence scoring. | `results/rbp_depolymerase/candidates.tsv`; `results/rbp_depolymerase/domain_architectures.tsv` | `computational_inference`; structure-informed annotation is not functional proof. | `Structure-informed evidence supports candidate prioritization.` | `Foldseek/Phold-like similarity proves receptor specificity.` |
| C9 | H1-H6 | Translational phage cocktail or therapeutic recommendations. | Safety screen, host-range assays, resistance evolution, genomic safety review, and clinical context. | Not produced by this workflow. | `experimental_validation_required`. | `The workflow prioritizes candidates for experimental follow-up.` | `This workflow recommends a therapeutic cocktail.` |

## Remaining Speculative Claims

The following claims must remain speculative unless new evidence is added:

- Any statement that a candidate RBP/depolymerase binds a specific capsule or O antigen.
- Any statement that a predicted anti-defense gene overcomes a specific host defense system.
- Any statement that model compatibility equals productive infection.
- Any statement that a phage is broad-host-range without explicit host-range assay metadata.
- Any statement that metadata host links are tested infection outcomes.
- Any statement that clinical lineage differences are causal rather than associations.
- Any therapeutic, cocktail, or patient-facing recommendation.

## Required Evidence Before Stronger Claims

Before promoting a claim from `data_dependent` or `computational_inference` to a stronger biological conclusion, add at least one matching evidence source:

- adsorption, plaque, EOP, kill-curve, or infection assay data for host-range claims;
- enzymatic capsule degradation or biochemical assays for depolymerase specificity claims;
- mutational, complementation, or gene-expression evidence for defense/counter-defense claims;
- curated host-range matrices for generalist/specialist claims;
- controlled metadata sampling or sensitivity analyses for clinical-lineage claims.
