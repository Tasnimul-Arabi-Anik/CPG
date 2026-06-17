# Host Feature Integration Schema

Stage 5 integrates Klebsiella host metadata from the project manifest with optional Kleborate- and Kaptive-style outputs. It preserves missingness: phages without host genomes are retained in `phage_host_links.tsv` and marked as metadata-only or unresolved rather than discarded.

## Inputs

Primary inputs:
- `results/qc/phage_genome_manifest.tsv`
- `results/clusters/phage_clusters.tsv`

Optional Kleborate input:
- A TSV with a sample/genome identifier column such as `sample`, `genome_id`, `host_genome_id`, `strain`, or `assembly`.
- Recommended columns include `species`, `ST`, `AMR_markers`, `virulence_markers`, `ybt`, `iuc`, `iro`, `rmpA`, and `rmpA2`.

Optional Kaptive input:
- A TSV with a sample/genome identifier column such as `sample`, `genome_id`, `host_genome_id`, `strain`, or `assembly`.
- Recommended columns include `K_locus`, `K_type`, `K_confidence`, `O_locus`, `O_type`, and `O_confidence`.

## Outputs

### `results/host_features/host_metadata.tsv`

One row per host genome or metadata-only host placeholder. Important columns:

| Column | Description |
| --- | --- |
| `host_genome_id` | Host genome ID, or a stable `metadata_host_*` placeholder if no genome is linked. |
| `host_record_type` | `host_genome` or `metadata_only_host`. |
| `K_locus`, `K_type` | Kaptive-derived or manifest-derived capsule information. |
| `O_locus`, `O_type` | Kaptive-derived or manifest-derived O-locus information. |
| `ST` | Kleborate/MLST or manifest sequence type. |
| `AMR_markers` | AMR markers from Kleborate or manifest metadata. |
| `virulence_markers` | Virulence markers from Kleborate or manifest metadata. |
| `linked_phage_like_records` | Semicolon-delimited phage/prophage/metagenomic records linked to this host. |
| `linked_species_clusters` | Semicolon-delimited Stage 2 species-like phage clusters linked to this host. |

### `results/host_features/kaptive_results.tsv`

Normalized Kaptive-style K/O calls.

### `results/host_features/kleborate_results.tsv`

Normalized Kleborate-style species, ST, AMR, and virulence calls.

### `results/host_features/phage_host_links.tsv`

One row per phage-like record. Link statuses include:

- `source_matches_host_genome_id`: the phage/prophage `source` field matches a host genome ID.
- `host_species_strain_exact_match`: host species and strain match one manifest host record.
- `metadata_only_host_no_genome`: host metadata exists but no host genome is linked.
- `ambiguous_host_species_strain_match`: multiple manifest hosts match the same species and strain.
- `no_host_metadata`: no usable host metadata exists.

### `results/host_features/host_feature_report.tsv`

Run-level validation and provenance messages.

## Current Behavior

This stage does not run Kleborate or Kaptive directly. It normalizes their tabular outputs when supplied and otherwise emits schema-valid empty tool tables. This keeps host feature integration reproducible before specialized tools are installed.
