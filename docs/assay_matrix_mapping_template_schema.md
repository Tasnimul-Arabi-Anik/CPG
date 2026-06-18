# Assay Matrix Mapping Template Schema

`scripts/create_assay_matrix_mapping_templates.py` extracts phage and host source identifiers from reviewed host-by-phage assay matrices and prepares curation templates for the source-to-canonical ID maps used by `scripts/normalize_assay_matrix.py`.

The script is intentionally conservative. It can prefill candidate canonical IDs when a source identifier exactly or uniquely matches a current canonical ID, but it writes those rows with `review_status=pending`. Pending rows are not accepted evidence and are ignored by the matrix normalizer. A reviewer must change `review_status` to `reviewed`, `accepted`, or `approved` before a mapping can be used to emit canonical assay rows.

## Inputs

- `--config`: assay matrix source config, usually `config/assay_matrix_sources.yaml`.
- `--phage-manifest`: canonical phage/host manifest, usually `results/seed/qc/phage_genome_manifest.tsv`.
- `--host-metadata`: canonical host metadata, usually `results/seed/host_features/host_metadata.tsv`.
- `--include-disabled`: process disabled sources when their local matrix files exist. This is useful for curation before enabling a source.
- `--update-maps`: append missing source IDs to the configured map files as pending rows. Without this flag, the script writes only a report.

## Mapping Files

Configured mapping files use:

```text
source_id	canonical_id	review_status	notes
```

Existing reviewed rows are preserved. Missing source IDs are appended only in `--update-maps` mode. The script never marks rows reviewed. Duplicate `source_id` values in a map are blocking.

## Report

The report columns are:

```text
source_id	entity_type	source_identifier	mapping_status	existing_canonical_id	existing_review_status	candidate_count	candidate_ids	map_action	notes
```

`mapping_status` distinguishes already reviewed mappings, existing pending mappings, exact candidate matches, unique normalized candidates, ambiguous candidates, and missing candidates.

## Example

```bash
python scripts/create_assay_matrix_mapping_templates.py \
  --config config/assay_matrix_sources.yaml \
  --only-source phagehostlearn_2024_interaction_matrix \
  --include-disabled \
  --update-maps \
  --report-output results/qc/phagehostlearn_2024_mapping_template_report.tsv \
  --root .
```

After reviewing and approving map rows, run `scripts/normalize_assay_matrix.py`, then `scripts/import_phage_host_assays.py`.
