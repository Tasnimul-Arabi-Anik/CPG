# RBP/Depolymerase Candidate Schema

Stage 4 identifies candidate receptor-binding proteins, tail fibers, tailspikes, and depolymerases from normalized phage annotations. It combines annotation text, PHROG/product clustering, optional domain evidence, optional structural evidence, protein length, and local synteny context.

## Inputs

Primary inputs:
- `results/annotations/phage_annotations.tsv`
- `results/annotations/gene_clusters.tsv`
- `config/thresholds.yaml`

Optional domain evidence:
- TSV with `annotation_gene_id`, `domain_id`, and `domain_name`.
- Recommended extra columns: `start_aa`, `end_aa`, `evalue`, `evidence_source`.

Optional structural evidence:
- TSV with `annotation_gene_id`, `structural_hit_id`, and `structural_hit_name`.
- Recommended extra columns: `tm_score`, `probability`, `evidence_source`.

## Outputs

### `results/rbp_depolymerase/candidates.tsv`

One row per candidate RBP/depolymerase gene. Core columns:

| Column | Description |
| --- | --- |
| `candidate_id` | Stable candidate identifier for this run. |
| `annotation_gene_id` | Gene identifier from Stage 3. |
| `gene_cluster_id` | Stage 3 gene-cluster ID. |
| `module_cluster_id` | Stage 4 RBP/depolymerase module cluster ID. |
| `product` | Product annotation. |
| `sequence_hit` | PHROG/product evidence, when available. |
| `domain_hit` | Domain evidence summary, when supplied. |
| `structural_hit` | Structure-informed evidence summary, when supplied. |
| `synteny_context` | Nearby genes and whether tail-like context is present. |
| `predicted_enzyme_class` | Coarse class such as tail fiber RBP or capsule depolymerase tailspike. |
| `confidence_score` | Evidence score from 0 to 1. |
| `confidence_label` | Low, medium, or high. |
| `novelty_tier` | `tier_1`, `tier_2`, `tier_3`, or `insufficient_novelty_evidence`. |

Novelty tiers are conservative:
- `tier_1`: no sequence-level hit but domain or structural support exists.
- `tier_2`: weak sequence evidence plus domain, structural, or synteny support.
- `tier_3`: known or sequence-clustered RBP/depolymerase family candidate.

Annotation text alone is not considered enough for a novelty claim.

### `results/rbp_depolymerase/domain_architectures.tsv`

One row per candidate with ordered domain architecture where evidence is supplied.

### `results/rbp_depolymerase/module_clusters.tsv`

One row per RBP/depolymerase module cluster. Current grouping follows Stage 3 `gene_cluster_id` and summarizes member genomes, predicted enzyme classes, evidence types, and novelty tiers.

### `results/rbp_depolymerase/novel_candidates.tsv`

Subset of tier 1 or tier 2 candidates whose score meets the configured medium-confidence threshold.

### `results/rbp_depolymerase/rbp_depolymerase_report.tsv`

Run-level validation and provenance messages.

## Current Behavior

This stage is a prioritization layer, not final biochemical annotation. High-confidence candidates should be treated as computational predictions until experimentally validated or supported by stronger structure/function evidence.
