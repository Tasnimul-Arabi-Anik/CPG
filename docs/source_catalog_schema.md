# Source Catalog Schema

The source catalog describes local metadata manifests that can be merged into a normalized `samples.tsv` table before Stage 1 validation. It makes dataset population reproducible without requiring manual edits to `config/samples.tsv`.

## Config Files

Real-study catalog:
- `config/source_catalog.yaml`

Fixture-backed smoke-test catalog:
- `config/source_catalog.mock.yaml`

## Builder Command

```bash
python scripts/build_samples_from_sources.py \
  --catalog config/source_catalog.yaml \
  --output-samples results/source_builder/samples.tsv \
  --report-output results/source_builder/sample_source_report.tsv
```

The real workflow runs this builder through `scripts/run_workflow.py` and writes generated sample rows to `results/source_builder/samples.tsv`. The mock workflow runs the same builder and writes generated fixture rows to `results/mock/source_builder/samples.tsv`.

## Catalog Fields

Top-level fields:

| Field | Required | Description |
| --- | --- | --- |
| `sources` | yes | List of source manifests to merge. Empty is allowed and produces a header-only sample table. |
| `output_columns` | no | Optional documentation of the final output columns. The script writes the fixed schema from `docs/metadata_schema.md`. |
| `identity_columns_any` | no | List of canonical columns where at least one must be present in a populated source. Default: `genome_id`, `accession`, or `raw_sequence_path`. |

Each source entry supports:

| Field | Required | Description |
| --- | --- | --- |
| `source_id` | recommended | Stable identifier used in the build report. |
| `path` | yes when enabled | TSV source manifest path. Relative paths are resolved from the repository root/current working directory. |
| `enabled` | no | `true` by default. Disabled sources are skipped and reported. |
| `required` | no | If `true`, a missing source path is an error. If `false`, it is a warning. |
| `source_label` | no | Default value for the output `source` column. |
| `record_type_default` | no | Default `record_type` when the source row lacks one. |
| `notes` | no | Text appended to output row notes for provenance. |
| `identity_columns_any` | no | Optional per-source override for the identity rule. Use only when a source has a reliable alternative identifier column that maps to a canonical output column through aliases. |

Any output column can also use a default with `<column>_default`, for example `country_default: USA` or `phage_lifestyle_default: ambiguous`.

## Source Manifest Columns

The builder accepts exact `config/samples.tsv` columns and common aliases. Examples:

| Output column | Accepted aliases |
| --- | --- |
| `genome_id` | `id`, `sample`, `sample_id`, `assembly`, `assembly_id` |
| `accession` | `nucleotide_accession`, `genbank_accession`, `refseq_accession` |
| `source` | `database`, `source_database`, `data_source` |
| `isolation_host` | `host`, `reported_host` |
| `genome_length` | `length`, `length_bp`, `genome_size`, `genome_size_bp` |
| `gc_percent` | `gc`, `gc_content`, `gc_percentage` |
| `K_type` | `k_type`, `capsule_type`, `k_locus` |
| `O_type` | `o_type`, `o_antigen`, `o_locus` |
| `ST` | `st`, `mlst`, `sequence_type` |

Missing non-path values are written as `NA`; missing `raw_sequence_path` is written blank. If `genome_id` is missing, the builder creates a deterministic ID from record type, accession, source ID, and row number.

For populated source manifests, at least one configured identity column must be recognized. By default this means `genome_id`, `accession`, or `raw_sequence_path`. Missing recommended metadata columns are warnings, not fatal errors, because early real-data curation often starts with accession-only or FASTA-only records. Sources with data rows and no recognized identity column are rejected by the builder.

## Outputs

The builder writes:

- normalized sample table, usually `results/source_builder/samples.tsv` or `results/mock/source_builder/samples.tsv`;
- source-build report, usually `results/source_builder/sample_source_report.tsv` or `results/mock/source_builder/sample_source_report.tsv`.

Report columns:

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `source_id` | Source entry identifier. |
| `path` | Source manifest path. |
| `row_number` | Input row number where applicable. |
| `genome_id` | Output genome ID where applicable. |
| `field` | Catalog or row field being reported. |
| `message` | Human-readable issue or provenance note. |


## Real-Study Sample Table Policy

For production runs, do not hand-edit the workflow-generated sample table under `results/source_builder/`. Populate and review the source manifests under `data/metadata/source_manifests/`, set the selected source entries to `enabled: true` in `config/source_catalog.yaml`, and rerun:

```bash
python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_audit stage_0_samples stage_1_manifest
```

`config/samples.tsv` remains a static fallback/template, but the default real workflow now consumes `results/source_builder/samples.tsv` so every sample row has source-manifest provenance.

## Relationship to Stage 1

The builder is a normalization and provenance layer. It does not replace `scripts/00_build_phage_manifest.py`, which remains responsible for validating required sample columns, unique genome IDs, plausible genome sizes, GC values, and raw sequence paths.

## Planned Real-Study Source Manifests

The default real-study catalog contains disabled placeholders for:

- `data/metadata/source_manifests/inphared_klebsiella_phages.tsv`
- `data/metadata/source_manifests/ncbi_virus_klebsiella_phages.tsv`
- `data/metadata/source_manifests/literature_klebsiella_phages.tsv`
- `data/metadata/source_manifests/klebsiella_prophages.tsv`
- `data/metadata/source_manifests/metagenomic_discovery_contigs.tsv`
- `data/metadata/source_manifests/klebsiella_host_genomes.tsv`

Keep entries disabled until the corresponding TSV is populated and reviewed. Enabling an empty template is allowed for dry-run checks but will not populate the biological study.

## Readiness Audit

Run `scripts/audit_source_catalog.py` or the direct workflow runner to generate `source_catalog_readiness.tsv` and `source_catalog_audit_report.tsv`. The audit classifies each planned source as a placeholder, populated but disabled, ready with complete columns, ready with defaults, or invalid.


## Acquisition Plan

`stage_0_source_plan` writes `results/qc/source_acquisition_plan.tsv`, which summarizes source-manifest row counts, import linkage, catalog enablement, and next actions. Use it as the first checklist before turning on a production source.
