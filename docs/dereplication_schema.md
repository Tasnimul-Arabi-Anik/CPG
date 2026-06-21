# Dereplication and Similarity Schema

Stage 2 converts validated phage-like records into species-like genome clusters. It is intentionally split from external ANI/VIRIDIC/Mash execution so the repository can validate schemas before large genome downloads or specialized tools are installed.

## Inputs

Primary input:
- `results/qc/phage_genome_manifest.tsv`

Optional inputs:
- pairwise similarity TSV with columns `genome_id_1`, `genome_id_2`, `identity_percent`, `coverage_percent`, and `method`.
- Stage 1 sequence QC TSV, usually `results/qc/genome_sequence_qc.tsv`.

Thresholds:
- `config/thresholds.yaml` under `dereplication.species_like_identity_percent` and `dereplication.species_like_coverage_percent`.
- `config/thresholds.yaml` under `genome_qc.exclude_failed_local_sequence_qc_from_clustering` controls whether records with local sequence QC failures are excluded before clustering. Metadata-only records with no `raw_sequence_path` remain eligible and are explicitly marked with `sequence_qc_status=no_sequence_provided`.

Eligible records:
- `record_type` in `phage`, `prophage`, or `metagenomic_viral_contig`;
- `validation_status` is `pass` or absent;
- if a local FASTA was supplied and sequence QC failed, the record is excluded when `exclude_failed_local_sequence_qc_from_clustering: true`.

## Outputs

### `results/clusters/phage_ani.tsv`

Normalized pairwise similarity rows. Required columns:

| Column | Description |
| --- | --- |
| `genome_id_1` | First genome identifier. |
| `genome_id_2` | Second genome identifier. |
| `identity_percent` | Pairwise identity or intergenomic similarity percentage. |
| `coverage_percent` | Aligned or covered genome fraction percentage. |
| `method` | Tool or source, for example VIRIDIC, Mash, fastANI, or mock. |
| `passes_threshold` | Whether identity and coverage pass configured thresholds. |
| `included_in_clustering` | Whether the row was used for union-find clustering. |
| `notes` | Validation notes. |

### `results/clusters/phage_clusters.tsv`

One row per eligible genome. Required columns:

| Column | Description |
| --- | --- |
| `genome_id` | Genome identifier from the manifest. |
| `record_type` | Phage-like record type. |
| `cluster_id` | Species-like cluster identifier. |
| `representative_id` | Selected representative genome for the cluster. |
| `cluster_size` | Number of genomes in the cluster. |
| `identity_threshold_percent` | Identity threshold used. |
| `coverage_threshold_percent` | Coverage threshold used. |
| `sequence_qc_status` | Stage 1 sequence QC status used during clustering eligibility. |
| `passes_sequence_qc` | Whether local sequence QC passed, `false` for metadata-only rows, or `NA` if no QC table was supplied. |
| `clustering_basis` | Per-cluster basis: `pairwise_similarity_threshold`, `singleton_no_threshold_pairwise_link`, or `singleton_no_pairwise_similarity`. |
| `notes` | Validation notes. |

### `results/clusters/representatives.tsv`

One row per cluster. Required columns:

| Column | Description |
| --- | --- |
| `cluster_id` | Species-like cluster identifier. |
| `representative_id` | Selected representative genome. |
| `cluster_size` | Number of genomes in the cluster. |
| `member_genome_ids` | Semicolon-delimited member IDs. |
| `representative_reason` | Deterministic selection rationale. |
| `representative_sequence_qc_status` | Sequence QC status for the selected representative. |
| `identity_threshold_percent` | Identity threshold used. |
| `coverage_threshold_percent` | Coverage threshold used. |

### `results/clusters/dereplication_report.tsv`

Run-level validation and provenance messages.

## Current Behavior

If no pairwise similarity table is supplied, each eligible genome is emitted as a singleton cluster. This is deliberate: it keeps downstream stages schema-stable while clearly marking that clustering is based on missing pairwise evidence, not biological distinctness. If a pairwise table is supplied but a genome has no threshold-passing link, its singleton cluster is labeled `singleton_no_threshold_pairwise_link`.

When a sequence QC table is supplied, local FASTA-backed records with QC failures are excluded before pairwise rows are evaluated if `exclude_failed_local_sequence_qc_from_clustering` is true. Records without local sequence files remain eligible during early metadata curation, but their cluster rows carry `sequence_qc_status=no_sequence_provided`.

`build_blastn_pairwise_similarity.py` accepts ordinary FASTA paths and reviewed ZIP-member locators of the form `archive.zip::member.fasta` from the sequence-QC table. ZIP members are extracted only into a temporary BLASTN workspace and are not written to `data/raw/`.
