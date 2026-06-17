# Local Source Exports

Place reviewed local metadata exports here before enabling entries in `config/source_imports.yaml`.

This directory is for small TSV/CSV metadata exports from sources such as INPHARED, NCBI Virus/GenBank, or manually curated literature tables. Raw genome FASTA/GenBank files should remain under `data/raw/` and should not be overwritten by workflow scripts.

## Expected export filenames

The default import configuration looks for these reviewed local exports:

- `inphared_klebsiella_phages.tsv`
- `ncbi_virus_klebsiella_phages.tsv`
- `literature_klebsiella_phages.tsv`
- `klebsiella_prophages.tsv`
- `metagenomic_discovery_contigs.tsv`
- `klebsiella_host_genomes.tsv`

## Preflight checks

`stage_0_source_plan` inspects any export that exists here. A file is only considered import-ready when it has at least one data row, at least one recognized identity column such as `genome_id`, `accession`, or `raw_sequence_path`, and at least one row passing the configured source filters. Header-only files are treated as placeholders, not reviewed exports.
