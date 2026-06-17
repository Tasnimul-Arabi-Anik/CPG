# Metadata Schema

The primary metadata table is `config/samples.tsv`. It records phage, prophage, metagenomic viral contig, and host genome records in one place so downstream joins are reproducible.

## Required Columns

| Column | Description |
| --- | --- |
| `record_type` | One of `phage`, `prophage`, `metagenomic_viral_contig`, or `host`. |
| `genome_id` | Stable project identifier. Must be unique and non-empty. |
| `accession` | Public accession when available. Use `NA` if absent. |
| `source` | Source database or study, for example GenBank, RefSeq, INPHARED, literature, or local. |
| `isolation_host` | Reported host used for phage isolation, if known. |
| `host_species` | Host species or species complex member, if known. |
| `host_strain` | Host strain identifier, if known. |
| `country` | Country or region, if known. |
| `year` | Isolation or publication year, if known. |
| `phage_lifestyle` | `virulent`, `temperate`, `ambiguous`, or `NA`. |
| `genome_length` | Genome length in base pairs, if known. |
| `gc_percent` | GC percentage, if known. |
| `K_type` | Capsule type or K-locus call, if known. |
| `O_type` | O antigen or O-locus call, if known. |
| `ST` | Sequence type, if known. |
| `AMR_markers` | Semicolon-delimited AMR genes or `NA`. |
| `virulence_markers` | Semicolon-delimited virulence markers or `NA`. |
| `raw_sequence_path` | Relative or absolute path to FASTA/GenBank input, if already downloaded. |
| `notes` | Free-text notes and unresolved metadata issues. |

## Missing Values

Use `NA` for known missing values. Leave `raw_sequence_path` blank if no local sequence file exists yet.

## Validation Outputs

`scripts/00_build_phage_manifest.py` writes:

- `results/qc/phage_genome_manifest.tsv`: normalized records plus validation status.
- `results/qc/manifest_validation_report.tsv`: one row per validation message.
- `results/qc/excluded_genomes.tsv`: records that should not enter downstream analyses yet.

## Building the Table From Source Manifests

Use `scripts/build_samples_from_sources.py` with `config/source_catalog.yaml` to construct this table reproducibly from one or more local metadata manifests. The source catalog schema is documented in `docs/source_catalog_schema.md`.
