# Source Manifest Import Schema

`scripts/import_source_manifests.py` converts local public-source metadata exports into normalized source-manifest TSVs. It is intentionally local-only: it does not download genomes or metadata and does not modify `data/raw/`.

## Commands

Real-study import preflight:

```bash
python scripts/import_source_manifests.py \
  --config config/source_imports.yaml \
  --report-output results/qc/source_import_report.tsv
```

Mock smoke test import:

```bash
python scripts/import_source_manifests.py \
  --config config/source_imports.mock.yaml \
  --report-output results/mock/qc/source_import_report.tsv
```

The direct workflow runner executes this as `stage_0_source_imports` when `source_imports.enabled: true`.

## Import Config

Real-study config:
- `config/source_imports.yaml`

Fixture config:
- `config/source_imports.mock.yaml`

Top-level field:

| Field | Required | Description |
| --- | --- | --- |
| `imports` | yes | List of local table imports. Disabled imports are reported and skipped. |

Each import entry supports:

| Field | Required | Description |
| --- | --- | --- |
| `import_id` | recommended | Stable import identifier used in reports. |
| `enabled` | no | `false` by default. Set true only after the local input export is reviewed. |
| `input_path` | yes when enabled | Local TSV/CSV metadata export. |
| `output_path` | yes when enabled | Normalized source-manifest TSV to write. |
| `delimiter` | no | `auto`, `tab`, `comma`, or a literal delimiter. |
| `overwrite` | no | `true` by default. Set false to protect an existing output manifest. |
| `source_label` | no | Default `source` value in normalized rows. |
| `record_type_default` | no | Default `record_type`, usually `phage`. |
| `phage_lifestyle_default` | no | Default lifestyle when the source table lacks one. |
| `require_klebsiella` | no | If true, rows must contain `klebsiella` in any source field. |
| `require_phage_keyword` | no | If true, rows must contain a phage/virus keyword in any source field. |
| `include_regex` | no | Optional regular expression that rows must match. |
| `exclude_regex` | no | Optional regular expression that rows must not match. |
| `required_note_review_statuses` | no | Optional list or comma-separated set of accepted `review_status` values parsed from the input `notes` field or a `review_status` column. Rows with other statuses are skipped and reported. |
| `notes` | no | Provenance note appended to normalized rows. |

## Accepted Input Columns

The importer accepts the same canonical sample columns as `config/samples.tsv` plus common public-export aliases. Examples include:

| Output column | Accepted aliases |
| --- | --- |
| `accession` | `public_accession`, `nucleotide_accession`, `genbank_accession`, `refseq_accession`, `sequence_accession`, `accn` |
| `host_species` | `organism`, `species`, `host_organism`, `bacterial_species` |
| `isolation_host` | `host`, `reported_host`, `isolate_host` |
| `genome_length` | `length`, `length_bp`, `genome_size`, `genome_size_bp`, `sequence_length` |
| `gc_percent` | `gc`, `gc_content`, `gc_percentage`, `gc%` |
| `year` | `collection_year`, `collection_date`, `publication_year`, `date` |
| `notes` | `description`, `title`, `definition`, `comment` |

Missing values are filled from import defaults or `NA`. GC fractions less than or equal to 1 are converted to percentages. Year-like dates are reduced to a four-digit year when possible.

## Outputs

Each enabled import writes a normalized source manifest with the columns documented in `docs/metadata_schema.md`. The workflow also writes an import report, usually `results/qc/source_import_report.tsv` or `results/mock/qc/source_import_report.tsv`.

Report columns:

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `import_id` | Import entry identifier. |
| `input_path` | Local source export path. |
| `output_path` | Normalized source-manifest path. |
| `row_number` | Input row number when applicable. |
| `input_identifier` | Accession or row identifier when applicable. |
| `field` | Import field or filter event. |
| `message` | Human-readable import action or issue. |

## Default Real-Study Import Stubs

`config/source_imports.yaml` includes disabled local-export stubs for cultured phages, literature-curated phages, prophages, host genomes, and optional metagenomic discovery contigs. These entries are disabled by default so the workflow cannot accidentally treat placeholder data as production evidence. Populate the configured `data/metadata/source_exports/*.tsv` file, review it locally, then enable the corresponding import.

## Relationship to Source Catalog

The importer writes source manifests. `scripts/audit_source_catalog.py` then audits whether those manifests are ready, and `scripts/build_samples_from_sources.py` merges enabled source manifests into the Stage 1 sample table.

For real data, keep source imports and source catalog entries disabled until the output rows have been reviewed.


## Relationship to Acquisition Planning

`scripts/plan_source_acquisition.py` should be run before and after local imports. It identifies which configured exports are missing, which imports are ready but disabled, which manifests contain rows but are still disabled in the source catalog, and which command should be run next.


## Export Preflight Expectations

The acquisition planner inspects local exports before import. Header-only files, files without a recognized identity column, and files where all rows fail the configured Klebsiella/phage/include/exclude filters remain non-ready. This prevents an empty template from being mistaken for a reviewed production export.
