# Source Overlap Audit Schema

Stage 0 writes source-overlap audit outputs after source sample building. The audit identifies duplicate `genome_id`, `accession`, and `raw_sequence_path` groups in the built sample table before downstream manifest, dereplication, and model stages.

## `results/qc/source_overlap_groups.tsv`

One row per duplicate key group. Important columns:

| Column | Description |
| --- | --- |
| `overlap_key_type` | `genome_id`, `accession`, or `raw_sequence_path`. |
| `overlap_key` | Shared identity/path value. |
| `record_count` | Number of sample rows sharing the key. |
| `source_count` | Number of source labels represented. |
| `sources` | Source labels involved. |
| `record_types` | Record types represented. |
| `genome_ids` | Genome IDs in the group. |
| `accessions` | Accessions in the group. |
| `raw_sequence_paths` | Raw sequence paths in the group. |
| `overlap_status` | Duplicate category. |
| `recommended_action` | Review guidance before final atlas counts or claims. |

## `results/qc/source_overlap_summary.tsv`

One row per source label with record count, record types, unique identity counts, and duplicate key count.

## `results/qc/source_overlap_report.tsv`

Run-level summary with sample row count, overlap group count, and source count.

## Interpretation

This audit does not remove duplicates. It makes source overlap explicit so public-source redundancy can be reviewed before manuscript-level atlas counts. Genome-level dereplication remains a separate downstream analysis.
