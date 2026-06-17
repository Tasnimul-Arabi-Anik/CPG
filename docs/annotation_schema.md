# Annotation and Pangenome Schema

Stage 3 normalizes gene-level phage annotations and produces a simple gene-cluster pangenome matrix. It is designed to accept Pharokka/PHROGs-style tabular output later, while still allowing schema validation before those tools are installed.

## Inputs

Primary inputs:
- `results/qc/phage_genome_manifest.tsv`
- `results/clusters/phage_clusters.tsv`

Optional annotation input:
- TSV with at least `genome_id`, `gene_id`, and `product` columns.

Recommended annotation columns:
- `genome_id`
- `gene_id`
- `contig_id`
- `start`
- `end`
- `strand`
- `product`
- `protein_id`
- `protein_sequence`
- `protein_length_aa`
- `phrog_id`
- `phrog_category`
- `functional_category`
- `evidence`
- `tool`

Rows whose `genome_id` is not present in Stage 2 clusters are skipped with a warning.

## Outputs

### `results/annotations/phage_annotations.tsv`

One row per retained gene annotation. Important columns:

| Column | Description |
| --- | --- |
| `genome_id` | Genome identifier from the manifest. |
| `species_cluster_id` | Stage 2 species-like cluster. |
| `annotation_gene_id` | Globally unique gene ID, formatted as `genome_id|gene_id`. |
| `protein_id` | Protein accession or source identifier when available. |
| `protein_sequence` | Amino acid sequence preserved for external domain/profile and structural annotation runs. |
| `product` | Product annotation, preserving hypothetical proteins. |
| `phrog_id` | PHROG or homologous group ID when available. |
| `module_hint` | Coarse module inferred from product/category keywords. |
| `gene_cluster_id` | Stage 3 gene-cluster ID. |
| `gene_cluster_key` | Deterministic clustering key. |
| `gene_cluster_source` | Evidence source for the gene-cluster key. |

### `results/annotations/gene_clusters.tsv`

One row per gene cluster. Clustering precedence is:

1. `phrog_id` when available;
2. informative product name;
3. protein sequence hash;
4. singleton fallback.

This is not a final orthology method. It is a reproducible schema and merge layer until MMseqs2/Proteinortho/pangenome tooling is added.

### `results/annotations/pangenome_matrix.tsv`

Wide count matrix with one row per gene cluster and one column per clustered genome. Values are gene counts, not binary presence/absence.

### `results/annotations/annotation_report.tsv`

Run-level validation and provenance messages.

## Current Behavior

If no annotation input is supplied, Stage 3 emits empty schema-valid annotation, gene-cluster, and pangenome tables. This keeps downstream stages restartable without pretending annotations exist.
